from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.database.services import DatabaseService, UserService
from app.utils.logger import get_logger
from app.utils.config import REFERRAL_FREE_USES_PER_INVITE, REFERRAL_MAX_RUB

logger = get_logger(__name__)


_REF_PATTERNS = (
    re.compile(r"\bref[_:=](\d{3,20})\b", re.IGNORECASE),
    re.compile(r"\b(\d{3,20})\b"),
)


def _parse_referrer_id(start_text: str) -> Optional[int]:
    """Extract referrer id from /start payload.

    Supported examples:
      /start ref_123
      /start ref:123
      /start ref=123
      /start 123
    """
    if not start_text:
        return None
    parts = start_text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload:
        return None
    for rx in _REF_PATTERNS:
        m = rx.search(payload)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


@dataclass
class ReferralApplyResult:
    applied: bool
    referrer_id: Optional[int] = None
    granted_uses: int = 0
    max_rub: float = float(REFERRAL_MAX_RUB)
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "applied": self.applied,
            "referrer_id": self.referrer_id,
            "granted_uses": self.granted_uses,
            "max_rub": float(self.max_rub),
            "reason": self.reason,
        }


async def apply_referral_from_start(
    db_service: DatabaseService,
    new_user_id: int,
    start_text: str,
) -> Dict[str, Any]:
    """Apply referral if /start payload contains a referrer id.

    Rules:
    - only first referral counts (if user already has referrer_id -> ignore)
    - cannot refer yourself
    - referrer must exist (we auto-create user rows for both sides)
    - grant free uses to referrer (metadata.referral_free_uses)
    """

    referrer_id = _parse_referrer_id(start_text)
    if not referrer_id:
        return ReferralApplyResult(applied=False, reason="no_payload").as_dict()
    if referrer_id == new_user_id:
        return ReferralApplyResult(applied=False, referrer_id=referrer_id, reason="self_ref").as_dict()

    user_service = UserService(db_service)
    # Ensure both users exist
    await user_service.get_or_create(new_user_id)
    await user_service.get_or_create(referrer_id)

    # Check if already referred
    meta = await user_service.get_metadata(new_user_id)
    if meta.get("referrer_id"):
        return ReferralApplyResult(applied=False, referrer_id=int(meta.get("referrer_id")), reason="already_set").as_dict()

    # Apply referral
    granted = int(REFERRAL_FREE_USES_PER_INVITE)
    await user_service.set_metadata(new_user_id, {"referrer_id": referrer_id})

    ref_meta = await user_service.get_metadata(referrer_id)
    invites = int(ref_meta.get("referral_invites", 0)) + 1
    free_uses = int(ref_meta.get("referral_free_uses", 0)) + granted
    await user_service.set_metadata(
        referrer_id,
        {
            "referral_invites": invites,
            "referral_free_uses": free_uses,
        },
    )
    logger.info(
        "Referral applied",
        extra={
            "new_user_id": new_user_id,
            "referrer_id": referrer_id,
            "granted_uses": granted,
            "referrer_free_uses": free_uses,
        },
    )
    return ReferralApplyResult(
        applied=True,
        referrer_id=referrer_id,
        granted_uses=granted,
        max_rub=float(REFERRAL_MAX_RUB),
    ).as_dict()


async def consume_referral_free_use_if_possible(
    db_service: DatabaseService,
    user_id: int,
    estimated_cost_rub: float,
) -> Dict[str, Any]:
    """Attempt to consume a referral free use.

    We only allow using referral free uses for generations up to REFERRAL_MAX_RUB
    to protect the Kie.ai credits budget.
    """
    if estimated_cost_rub <= 0:
        return {"used": False, "reason": "free_or_zero"}
    if estimated_cost_rub > float(REFERRAL_MAX_RUB):
        return {"used": False, "reason": "too_expensive", "max_rub": float(REFERRAL_MAX_RUB)}

    user_service = UserService(db_service)
    meta = await user_service.get_metadata(user_id)
    remaining = int(meta.get("referral_free_uses", 0))
    if remaining <= 0:
        return {"used": False, "reason": "none"}

    await user_service.set_metadata(user_id, {"referral_free_uses": remaining - 1})
    return {"used": True, "remaining": remaining - 1, "max_rub": float(REFERRAL_MAX_RUB)}


async def refund_referral_free_use(
    db_service: DatabaseService,
    user_id: int,
) -> None:
    user_service = UserService(db_service)
    meta = await user_service.get_metadata(user_id)
    remaining = int(meta.get("referral_free_uses", 0))
    await user_service.set_metadata(user_id, {"referral_free_uses": remaining + 1})
