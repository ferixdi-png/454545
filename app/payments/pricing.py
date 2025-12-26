"""app.payments.pricing

Единый модуль ценообразования.

Правило:
  - В source_of_truth цены должны храниться БЕЗ наценки (Kie.ai base cost).
  - Итоговая цена пользователю = base_cost_rub * PRICING_MARKUP.

Источники base cost:
  1) Фактическая стоимость из ответа Kie.ai (если есть usage/credits/cost)
  2) pricing внутри модели (usd/rub/credits per use)
  3) fallback (только чтобы не ломать UI; в логах помечаем как WARNING)

Курс USD→RUB берём из app.pricing.fx (ЦБ РФ). Это соответствует логам старта.

Важно:
  - Здесь НЕТ "магии" с двойной наценкой: base_cost_rub считается БЕЗ markup.
  - Markup берётся из ENV PRICING_MARKUP (default 2.0) или Config.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.pricing import fx

logger = logging.getLogger(__name__)


# --- Defaults / fallbacks ---

DEFAULT_USD_FALLBACK = float(os.getenv("DEFAULT_MODEL_PRICE_USD", "10"))

# Kie.ai credits conversion (если ответы/прайс в credits)
# По документации у вас в проекте это было $0.005 за кредит.
KIE_CREDITS_TO_USD = float(os.getenv("KIE_CREDITS_TO_USD", "0.005"))


FALLBACK_PRICES_USD: Dict[str, float] = {
    "sora-2-text-to-video": 0.0,
    "sora-2-image-to-video": 0.0,
    "sora-watermark-remover": 0.0,
    "grok-imagine/image-to-video": 0.0,
    "grok-imagine/text-to-video": 0.0,
}


@dataclass(frozen=True)
class PriceBreakdown:
    model_id: str
    base_cost_rub: float
    user_price_rub: float
    usd_to_rub_rate: float
    markup: float
    source: str


def _get_markup() -> float:
    # Prefer Config if available (keeps parity with startup logs)
    try:
        from app.utils.config import get_config

        return float(get_config().pricing_markup)
    except Exception:
        pass
    try:
        return float(os.getenv("PRICING_MARKUP", "2.0"))
    except Exception:
        return 2.0



def get_pricing_markup() -> float:
    """Public accessor for PRICING_MARKUP.

    Used by startup validation and pricing breakdowns.
    """
    return _get_markup()


def get_usd_to_rub_rate() -> float:
    """Public accessor for USD→RUB exchange rate (for external use).
    
    Returns base rate WITHOUT markup. Uses app.pricing.fx with CBR fallback.
    """
    return _get_usd_to_rub_rate()


def get_kie_credits_to_usd() -> float:
    """Public accessor for Kie.ai credits→USD conversion rate."""
    return KIE_CREDITS_TO_USD


def _get_usd_to_rub_rate() -> float:
    """Return USD→RUB rate WITHOUT markup."""
    try:
        return float(fx.get_usd_to_rub_rate())
    except Exception as e:
        fallback = float(os.getenv("USD_TO_RUB_FALLBACK", "79"))
        logger.warning("FX rate unavailable (%s). Using fallback USD_TO_RUB_FALLBACK=%s", e, fallback)
        return fallback


def _to_rub_from_usd(usd: float) -> float:
    return float(usd) * _get_usd_to_rub_rate()


def _to_rub_from_credits(credits: float) -> float:
    usd = float(credits) * KIE_CREDITS_TO_USD
    return _to_rub_from_usd(usd)


def _extract_cost_from_kie_response(kie_response: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """Best-effort extraction of cost from a Kie.ai response.

    Returns (base_cost_rub, source_tag) or None.

    We *never* apply markup here.
    """
    if not isinstance(kie_response, dict):
        return None

    # 1) Credits-based usage
    for key in ("credits_used", "used_credits", "credits", "credit_used"):
        if key in kie_response:
            try:
                credits = float(kie_response[key])
                if credits >= 0:
                    return (round(_to_rub_from_credits(credits), 6), f"kie_response:{key}")
            except Exception:
                continue

    # 2) Explicit USD cost
    for key in ("cost_usd", "usd_cost", "price_usd", "amount_usd"):
        if key in kie_response:
            try:
                usd = float(kie_response[key])
                if usd >= 0:
                    return (round(_to_rub_from_usd(usd), 6), f"kie_response:{key}")
            except Exception:
                continue

    # 3) Explicit RUB cost
    for key in ("cost_rub", "rub_cost", "price_rub", "amount_rub"):
        if key in kie_response:
            try:
                rub = float(kie_response[key])
                if rub >= 0:
                    return (round(rub, 6), f"kie_response:{key}")
            except Exception:
                continue

    # 4) Generic 'cost'/'price' + currency
    cost = kie_response.get("cost") or kie_response.get("price") or kie_response.get("usage_cost")
    currency = (kie_response.get("currency") or "").upper()
    if isinstance(cost, (int, float)):
        try:
            if currency == "USD":
                return (round(_to_rub_from_usd(float(cost)), 6), "kie_response:cost:USD")
            if currency == "RUB":
                return (round(float(cost), 6), "kie_response:cost:RUB")
        except Exception:
            pass

    return None


def _extract_cost_from_model_pricing(model: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """Extract base cost from model registry / source_of_truth.

    Supports different key conventions to avoid silent zeros.
    """
    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        pricing = {}

    # Direct RUB
    for key in ("rub_per_use", "rub_per_gen", "rub_per_call", "rub", "price_rub"):
        if key in pricing:
            try:
                rub = float(pricing[key])
                if rub >= 0:
                    return (round(rub, 6), f"model_pricing:{key}")
            except Exception:
                continue

    # USD
    for key in ("usd_per_use", "usd_per_gen", "usd_per_call", "usd", "price_usd"):
        if key in pricing:
            try:
                usd = float(pricing[key])
                if usd >= 0:
                    return (round(_to_rub_from_usd(usd), 6), f"model_pricing:{key}")
            except Exception:
                continue

    # Credits
    for key in ("credits_per_use", "credits_per_gen", "credits_per_call", "credits"):
        if key in pricing:
            try:
                credits = float(pricing[key])
                if credits >= 0:
                    return (round(_to_rub_from_credits(credits), 6), f"model_pricing:{key}")
            except Exception:
                continue

    # Legacy registry field
    legacy_usd = model.get("price")
    if legacy_usd is not None:
        try:
            usd = float(legacy_usd)
            if usd >= 0:
                return (round(_to_rub_from_usd(usd), 6), "legacy:model.price")
        except Exception:
            pass

    return None


def calculate_kie_cost(
    model: Dict[str, Any],
    user_inputs: Optional[Dict[str, Any]] = None,
    kie_response: Optional[Dict[str, Any]] = None,
    # Backward compatibility with old code
    payload: Optional[Dict[str, Any]] = None,
    api_response: Optional[Dict[str, Any]] = None,
) -> float:
    """Calculate *base* Kie.ai cost in RUB (no markup).
    
    Args:
        model: Model dict with pricing info
        user_inputs: User inputs dict (default: {})
        kie_response: Kie.ai API response with cost
        payload: Legacy alias for user_inputs (deprecated)
        api_response: Legacy alias for kie_response (deprecated)
    """
    # Handle backward compatibility
    if user_inputs is None:
        user_inputs = payload if payload is not None else {}
    if kie_response is None and api_response is not None:
        kie_response = api_response
    model_id = str(model.get("model_id") or model.get("id") or "unknown")

    # 1) Kie response cost (best signal)
    if kie_response:
        extracted = _extract_cost_from_kie_response(kie_response)
        if extracted:
            base_rub, src = extracted
            logger.info("pricing.base_cost model=%s base_rub=%.6f src=%s", model_id, base_rub, src)
            return float(base_rub)

    # 2) Model pricing
    extracted = _extract_cost_from_model_pricing(model)
    if extracted:
        base_rub, src = extracted
        logger.info("pricing.base_cost model=%s base_rub=%.6f src=%s", model_id, base_rub, src)
        return float(base_rub)

    # 3) Fallback (last resort)
    if model_id in FALLBACK_PRICES_USD:
        usd = FALLBACK_PRICES_USD[model_id]
        base_rub = round(_to_rub_from_usd(usd), 6)
        logger.warning(
            "pricing.fallback_used model=%s usd=%.4f base_rub=%.6f reason=no_source_of_truth",
            model_id,
            usd,
            base_rub,
        )
        return float(base_rub)

    base_rub = round(_to_rub_from_usd(DEFAULT_USD_FALLBACK), 6)
    logger.warning(
        "pricing.default_used model=%s usd=%.4f base_rub=%.6f reason=no_price_info",
        model_id,
        DEFAULT_USD_FALLBACK,
        base_rub,
    )
    return float(base_rub)


def calculate_user_price(kie_cost_rub: float) -> float:
    """Apply PRICING_MARKUP to base Kie cost."""
    if kie_cost_rub <= 0:
        return 0.0
    markup = _get_markup()
    user_price = float(kie_cost_rub) * float(markup)
    # UI friendly rounding
    return round(user_price, 2)


def get_price_breakdown(
    model: Dict[str, Any],
    user_inputs: Optional[Dict[str, Any]] = None,
    kie_response: Optional[Dict[str, Any]] = None,
) -> PriceBreakdown:
    user_inputs = user_inputs or {}
    model_id = str(model.get("model_id") or model.get("id") or "unknown")
    markup = _get_markup()
    rate = _get_usd_to_rub_rate()
    base_rub = calculate_kie_cost(model, user_inputs, kie_response)
    user_rub = calculate_user_price(base_rub)
    src = "computed"
    return PriceBreakdown(
        model_id=model_id,
        base_cost_rub=base_rub,
        user_price_rub=user_rub,
        usd_to_rub_rate=rate,
        markup=markup,
        source=src,
    )


def format_price_rub(price: float) -> str:
    """Format price in RUB with clean decimals (no trailing zeros).
    
    Examples:
        0 → Бесплатно
        0.76 → 0.76₽
        1.5 → 1.5₽
        3.8 → 3.8₽
        15.0 → 15₽
        95.0 → 95₽
    """
    if price <= 0:
        return "Бесплатно"
    
    # Round to 2 decimals, then strip trailing zeros
    formatted = f"{price:.2f}".rstrip('0').rstrip('.')
    return f"{formatted}₽"


def create_charge_metadata(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Metadata for DB/transactions (debuggable & deterministic)."""
    from datetime import datetime

    breakdown = get_price_breakdown(model, user_inputs, kie_response)

    return {
        "model_id": breakdown.model_id,
        "kie_cost_rub": breakdown.base_cost_rub,
        "user_price_rub": breakdown.user_price_rub,
        "usd_to_rub_rate": breakdown.usd_to_rub_rate,
        "markup": breakdown.markup,
        "timestamp": datetime.now().isoformat(),
    }
