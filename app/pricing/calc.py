"""Pricing calculation helpers.

Single source of truth for effective price shown to user and used for FREE tier.

Rules:
- Prefer explicit RUB pricing if provided (rub_per_gen or rub_per_use)
- Else use USD pricing (usd_per_gen or usd_per_use) converted via FX with MARKUP
- Else use credits pricing (credits_per_gen or credits_per_use) via credits_to_rub with MARKUP
- MARKUP default 2.0, override via env MARKUP
- credits_to_usd_rate default 0.01, override via env CREDITS_TO_USD_RATE
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from . import fx


def _f(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def get_markup() -> float:
    try:
        return float(os.getenv("MARKUP", "2.0"))
    except Exception:
        return 2.0


def get_credits_to_usd_rate() -> float:
    try:
        return float(os.getenv("CREDITS_TO_USD_RATE", "0.01"))
    except Exception:
        return 0.01


def effective_rub_price(pricing: Dict[str, Any]) -> Tuple[float, str]:
    """Return (rub_price, basis) where basis in {'rub','usd','credits','none'}"""
    markup = get_markup()

    rub = _f(pricing.get("rub_per_gen", pricing.get("rub_per_use", 0.0)))
    if rub > 0:
        return rub, "rub"

    usd = _f(pricing.get("usd_per_gen", pricing.get("usd_per_use", 0.0)))
    if usd > 0:
        return fx.usd_to_rub(usd, markup=markup), "usd"

    credits = _f(pricing.get("credits_per_gen", pricing.get("credits_per_use", 0.0)))
    if credits > 0:
        return fx.credits_to_rub(credits, credits_to_usd_rate=get_credits_to_usd_rate(), markup=markup), "credits"

    return 0.0, "none"


def model_effective_rub(model: Dict[str, Any]) -> float:
    pricing = model.get("pricing") if isinstance(model, dict) else None
    if not isinstance(pricing, dict):
        return 0.0
    rub, _ = effective_rub_price(pricing)
    return rub


def format_rub(rub: float) -> str:
    if rub <= 0:
        return "0 ₽"
    # Keep integer-ish prices neat
    if abs(rub - round(rub)) < 1e-6:
        return f"{int(round(rub))} ₽"
    return f"{rub:.2f} ₽"
