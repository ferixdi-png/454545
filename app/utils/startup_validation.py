"""Startup validation

Проверяет *боевую* готовность на старте (Render/Docker).

Почему это важно:
  - source_of_truth может сломаться после обновлений
  - цены обязаны быть一致ны (Kie.ai → FX → MARKUP)
  - FREE tier обязан быть честным TOP-5 cheapest (base cost)

Если валидация падает -> бот НЕ стартует (чтобы не "тихо" ломать UX/кассу).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.payments.pricing import (
    calculate_kie_cost,
    get_pricing_markup,
    get_usd_to_rub_rate,
)

logger = logging.getLogger(__name__)

def _load_allowed_model_ids() -> list[str]:
    try:
        p = Path("models/ALLOWED_MODEL_IDS.txt")
        if not p.exists():
            return []
        ids=[]
        for line in p.read_text(encoding="utf-8").splitlines():
            s=line.strip()
            if not s or s.startswith("#"):
                continue
            ids.append(s)
        seen=set()
        out=[]
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            out.append(mid)
        return out
    except Exception:
        return []


SOURCE_OF_TRUTH_PATH = Path("models/KIE_SOURCE_OF_TRUTH.json")
MIN_ENABLED_MODELS = 5  # minimal lock default (expand later)
FREE_TIER_COUNT = 5


class StartupValidationError(Exception):
    """Raised when startup validation fails."""


def load_source_of_truth() -> Dict[str, Any]:
    if not SOURCE_OF_TRUTH_PATH.exists():
        raise StartupValidationError(f"Source of truth не найден: {SOURCE_OF_TRUTH_PATH}")

    try:
        data = json.loads(SOURCE_OF_TRUTH_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise StartupValidationError(f"Source of truth содержит невалидный JSON: {e}")

    if "models" not in data:
        raise StartupValidationError("Source of truth не содержит ключ 'models'")

    if not isinstance(data.get("models"), dict):
        raise StartupValidationError("Source of truth 'models' должен быть объектом (dict)")

    return data


def _enabled_models(models_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for model_id, model in models_dict.items():
        if not isinstance(model, dict):
            continue
        if not model.get("enabled", True):
            continue
        if model.get("model_id") is None:
            # tolerate: some files may key by model_id and omit duplicated field
            model = dict(model)
            model["model_id"] = model_id
        out.append(model)
    return out


def _model_base_cost_pairs(models: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    pairs: List[Tuple[str, float]] = []
    for m in models:
        mid = str(m.get("model_id") or "")
        base = calculate_kie_cost(m, user_inputs={}, kie_response=None)
        if base is None:
            continue
        if base < 0:
            raise StartupValidationError(f"Негативная base cost у модели {mid}: {base}")
        pairs.append((mid, float(base)))
    return pairs


def validate_models(data: Dict[str, Any]) -> None:
    models_dict = data.get("models", {})
    enabled = _enabled_models(models_dict)
    if not enabled:
        raise StartupValidationError("Нет enabled моделей в source of truth")

    # require enough models with computable base cost
    pairs = _model_base_cost_pairs(enabled)
    if len(pairs) < MIN_ENABLED_MODELS:
        raise StartupValidationError(
            f"Недостаточно моделей с валидным pricing: {len(pairs)} < {MIN_ENABLED_MODELS}"
        )

    logger.info(f"✅ Models: {len(models_dict)} total, {len(enabled)} enabled")
    logger.info(f"✅ Models with valid pricing: {len(pairs)}")


def validate_free_tier(data: Dict[str, Any]) -> None:
    """FREE tier обязан быть TOP-5 cheapest по base cost.
    
    IMPORTANT: Exclude models with base_cost=0 (truly free on Kie.ai).
    We only consider PAID models for FREE tier to ensure monetization works.
    """
    models_dict = data.get("models", {})
    enabled = _enabled_models(models_dict)
    pairs = _model_base_cost_pairs(enabled)
    
    # Filter out zero-cost models (truly free, not part of FREE tier)
    paid_pairs = [(mid, cost) for mid, cost in pairs if cost > 0]
    
    if len(paid_pairs) < FREE_TIER_COUNT:
        raise StartupValidationError(
            f"Недостаточно ПЛАТНЫХ моделей для FREE tier: {len(paid_pairs)} < {FREE_TIER_COUNT}"
        )

    paid_pairs.sort(key=lambda x: x[1])
    cheapest = [mid for mid, _ in paid_pairs[:FREE_TIER_COUNT]]

    # source_of_truth должен содержать is_free флаг (true) у этих моделей
    is_free_ids: List[str] = []
    for mid, model in models_dict.items():
        if not isinstance(model, dict):
            continue
        if model.get("is_free") is True:
            is_free_ids.append(str(model.get("model_id") or mid))

    if len(is_free_ids) != FREE_TIER_COUNT:
        raise StartupValidationError(
            f"В source_of_truth должно быть ровно {FREE_TIER_COUNT} FREE моделей (is_free=true), сейчас: {len(is_free_ids)}"
        )

    # order-agnostic compare
    if set(is_free_ids) != set(cheapest):
        raise StartupValidationError(
            "FREE tier не совпадает с TOP-5 cheapest по base cost. "
            f"expected={cheapest} actual={sorted(is_free_ids)}"
        )

    logger.info(f"✅ FREE tier: {FREE_TIER_COUNT} cheapest моделей корректны")


def validate_pricing_formula() -> None:
    # FX module must be alive (network can fail, but rate fallback exists)
    rate = get_usd_to_rub_rate()
    markup = get_pricing_markup()
    if rate <= 0:
        raise StartupValidationError(f"FX rate невалидный: {rate}")
    if markup <= 0:
        raise StartupValidationError(f"PRICING_MARKUP невалидный: {markup}")
    logger.info(f"✅ Pricing: FX module доступен, MARKUP={markup}")


def validate_startup() -> None:
    logger.info("🔍 Startup validation начата...")

    data = load_source_of_truth()

    # Canonical allowlist check (must be exactly 42 model_ids)
    allowed = _load_allowed_model_ids()
    if allowed and len(allowed) != 42:
        raise RuntimeError(f"ALLOWLIST must contain exactly 42 model_ids, got {len(allowed)}")

    logger.info("✅ Source of truth загружен")

    validate_models(data)
    validate_free_tier(data)
    validate_pricing_formula()

    logger.info("✅ Startup validation PASSED - бот готов к запуску")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    try:
        validate_startup()
        print("\n✅ Валидация успешна")
    except StartupValidationError as e:
        print(f"\n❌ Валидация провалена: {e}")
        raise SystemExit(1)
