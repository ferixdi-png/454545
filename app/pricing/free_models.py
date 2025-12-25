"""
Free models management - automatic TOP-5 cheapest selection.

RULES (product truth):
1) FREE tier = 5 cheapest runnable/enabled models by EFFECTIVE cost (RUB)
2) Cost source priority per model:
   - pricing.rub_per_gen (or rub_per_use) if present
   - pricing.usd_per_gen (or usd_per_use) * FX * MARKUP
   - pricing.credits_per_gen (or credits_per_use) * CREDITS_TO_USD * FX * MARKUP
3) No manual hardcoding of FREE models in source-of-truth.
4) Re-calculated on every startup / source-of-truth update.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.pricing.fx import get_usd_to_rub_rate

logger = logging.getLogger(__name__)

SOURCE_OF_TRUTH = Path("models/KIE_SOURCE_OF_TRUTH.json")


def _get_markup() -> float:
    try:
        return float(os.getenv("PRICING_MARKUP", "2.0"))
    except Exception:
        return 2.0


def _get_credits_to_usd() -> float:
    # Kie часто использует 1 credit = $0.005 (по твоей доке/прайсингу), но делаем конфигurable.
    try:
        return float(os.getenv("KIE_CREDITS_TO_USD", "0.005"))
    except Exception:
        return 0.005


def _extract_pricing(model: Dict[str, Any]) -> Dict[str, Any]:
    return (model or {}).get("pricing", {}) or {}


def _effective_rub(pricing: Dict[str, Any], fx: float, markup: float, credits_to_usd: float) -> float | None:
    # prefer explicit rub
    for k in ("rub_per_gen", "rub_per_use"):
        v = pricing.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)

    # usd
    for k in ("usd_per_gen", "usd_per_use"):
        v = pricing.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v) * fx * markup

    # credits
    for k in ("credits_per_gen", "credits_per_use"):
        v = pricing.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v) * credits_to_usd * fx * markup

    return None


def get_free_models(limit: int = 5) -> List[str]:
    """
    Compute FREE tier model_ids (tech IDs) as TOP-N cheapest by effective RUB cost.
    """
    if not SOURCE_OF_TRUTH.exists():
        logger.error(f"Source of truth not found: {SOURCE_OF_TRUTH}")
        return []

    try:
        data = json.loads(SOURCE_OF_TRUTH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception(f"Failed to load source of truth: {e}")
        return []

    models: Dict[str, Any] = data.get("models", {}) or {}
    enabled_items: List[Tuple[str, Dict[str, Any]]] = [
        (model_id, model) for model_id, model in models.items() if (model or {}).get("enabled", True)
    ]

    fx = get_usd_to_rub_rate()
    markup = _get_markup()
    credits_to_usd = _get_credits_to_usd()

    priced: List[Tuple[str, float]] = []
    for model_id, model in enabled_items:
        p = _extract_pricing(model)
        rub = _effective_rub(p, fx=fx, markup=markup, credits_to_usd=credits_to_usd)
        if rub is None:
            continue
        priced.append((model_id, float(rub)))

    priced.sort(key=lambda x: x[1])
    free_ids = [mid for mid, _ in priced[: max(0, int(limit))]]

    logger.info(
        "Computed FREE tier: %d models (fx=%.4f, markup=%.3f). Top cheapest: %s",
        len(free_ids),
        fx,
        markup,
        ", ".join(free_ids[:10]),
    )
    return free_ids


def get_model_price_rub(model_id: str) -> float | None:
    """
    Helper: compute effective RUB cost for a specific model_id.
    """
    if not SOURCE_OF_TRUTH.exists():
        return None
    data = json.loads(SOURCE_OF_TRUTH.read_text(encoding="utf-8"))
    model = (data.get("models", {}) or {}).get(model_id)
    if not model:
        return None
    fx = get_usd_to_rub_rate()
    markup = _get_markup()
    credits_to_usd = _get_credits_to_usd()
    return _effective_rub(_extract_pricing(model), fx=fx, markup=markup, credits_to_usd=credits_to_usd)
