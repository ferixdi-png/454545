"""FSM guard middleware.

Goals:
- Prevent "silence" when user is stuck in a stale/broken FSM state.
- Auto-reset stale states after a configurable TTL.
- Add correlation-friendly logs without leaking message content.

This middleware is intentionally lightweight and safe for production.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

def _ttl_seconds() -> int:
    # Default: 45 minutes (Render-friendly, avoids week-long zombie states)
    try:
        return int(os.getenv("FSM_STATE_TTL_S", "2700"))
    except Exception:
        return 2700

class FSMGuardMiddleware(BaseMiddleware):
    """Auto-reset stale FSM states and mark fresh timestamps."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # aiogram v3 injects FSMContext into data["state"]
        ctx: Optional[FSMContext] = data.get("state")  # type: ignore[assignment]
        if not ctx:
            return await handler(event, data)

        try:
            state_name = await ctx.get_state()
        except Exception:
            state_name = None

        if not state_name:
            return await handler(event, data)

        now = int(time.time())
        ttl = _ttl_seconds()
        uid = None
        try:
            ev_update = event if isinstance(event, Update) else None
            if ev_update and ev_update.event_from_user:
                uid = ev_update.event_from_user.id
        except Exception:
            uid = None

        try:
            st_data = await ctx.get_data()
        except Exception:
            st_data = {}

        # Timestamp bookkeeping (do NOT require handler changes)
        ts = st_data.get("_fsm_ts")
        if not isinstance(ts, int):
            # First time we see this state, mark timestamp
            try:
                await ctx.update_data(_fsm_ts=now)
            except Exception:
                pass
            return await handler(event, data)

        # Auto-reset stale state
        age = now - ts
        if age > ttl:
            try:
                await ctx.clear()
            except Exception:
                # If clear fails, try setting to None
                try:
                    await ctx.set_state(None)
                except Exception:
                    pass

            logger.warning(
                "[iid=%s uid=%s state=%s ttl_s=%s age_s=%s] fsm_reset_stale",
                data.get("instance_id") or os.environ.get("INSTANCE_ID") or "-",
                uid or "-",
                state_name,
                ttl,
                age,
            )
            # After reset, continue handler with cleared state
        return await handler(event, data)
