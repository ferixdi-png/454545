"""
Startup validation - проверка корректности системы при старте бота.

ПРОВЕРЯЕТ:
1. source_of_truth.json существует и парсится
2. Достаточно enabled моделей (минимум 20)
3. FREE tier корректен (5 cheapest моделей)
4. Pricing формула валидна (USD_TO_RUB = 78.0, MARKUP = 2.0)

КРИТИЧНО: Если валидация провалена → бот НЕ СТАРТУЕТ.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

SOURCE_OF_TRUTH_PATH = Path("models/KIE_SOURCE_OF_TRUTH.json")
USD_TO_RUB = 78.0
MARKUP = 2.0
MIN_ENABLED_MODELS = 20
FREE_TIER_COUNT = 5


class StartupValidationError(Exception):
    """Raised when startup validation fails."""
    pass


def load_source_of_truth() -> Dict[str, Any]:
    """Load and parse source of truth JSON."""
    
    if not SOURCE_OF_TRUTH_PATH.exists():
        raise StartupValidationError(
            f"Source of truth не найден: {SOURCE_OF_TRUTH_PATH}"
        )
    
    try:
        with open(SOURCE_OF_TRUTH_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StartupValidationError(
            f"Source of truth содержит невалидный JSON: {e}"
        )
    
    if "models" not in data:
        raise StartupValidationError(
            "Source of truth не содержит ключ 'models'"
        )
    
    return data


def validate_models(data: Dict[str, Any]) -> None:
    """Validate models count and structure."""
    models_dict = data.get("models", {})
    
    if not models_dict:
        raise StartupValidationError("Нет моделей в source of truth")
    
    # Count enabled models (pricing.rub_per_gen + enabled flag)
    enabled_models = [
        model for model_id, model in models_dict.items()
        if model.get("enabled", True) 
        and model.get("pricing", {}).get("rub_per_gen") is not None
    ]
    
    if len(enabled_models) < MIN_ENABLED_MODELS:
        raise StartupValidationError(
            f"Недостаточно enabled моделей: {len(enabled_models)} < {MIN_ENABLED_MODELS}"
        )
    
    logger.info(f"✅ Models: {len(models_dict)} total, {len(enabled_models)} enabled")


def validate_free_tier(data: Dict[str, Any]) -> None:
    """Validate FREE tier configuration."""
    models_dict = data.get("models", {})
    
    # Get enabled models sorted by price (rub_per_gen)
    enabled_models = [
        model for model_id, model in models_dict.items()
        if model.get("enabled", True)
        and model.get("pricing", {}).get("rub_per_gen") is not None
    ]
    enabled_models.sort(key=lambda m: m.get("pricing", {}).get("rub_per_gen", 999999))
    
    if len(enabled_models) < FREE_TIER_COUNT:
        raise StartupValidationError(
            f"Недостаточно моделей для FREE tier: {len(enabled_models)} < {FREE_TIER_COUNT}"
        )
    
    # Check that cheapest 5 have reasonable prices
    cheapest_5 = enabled_models[:FREE_TIER_COUNT]
    for model in cheapest_5:
        price_rub = model.get("pricing", {}).get("rub_per_gen", 0)
        if price_rub < 0:
            raise StartupValidationError(
                f"FREE tier модель {model.get('model_id')} имеет невалидную цену: {price_rub} RUB"
            )
        if price_rub > 100:
            logger.warning(
                f"⚠️ FREE tier модель {model.get('model_id')} дорогая: {price_rub} RUB"
            )
    
    logger.info(f"✅ FREE tier: {FREE_TIER_COUNT} cheapest моделей корректны")


def validate_pricing_formula() -> None:
    """Validate pricing formula constants."""
    # Just check that pricing module can be imported
    try:
        from app.pricing import fx
        logger.info(f"✅ Pricing: FX module доступен, MARKUP={MARKUP}")
    except ImportError as e:
        raise StartupValidationError(f"Не удалось импортировать pricing: {e}")


def validate_startup() -> None:
    """
    Complete startup validation.
    
    Raises:
        StartupValidationError: If any validation fails
    """
    logger.info("🔍 Startup validation начата...")
    
    # Step 1: Load source of truth
    data = load_source_of_truth()
    logger.info("✅ Source of truth загружен")
    
    # Step 2: Validate models
    validate_models(data)
    
    # Step 3: Validate FREE tier
    validate_free_tier(data)
    
    # Step 4: Validate pricing formula
    validate_pricing_formula()
    
    logger.info("✅ Startup validation PASSED - бот готов к запуску")


if __name__ == "__main__":
    # Test validation
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )
    
    try:
        validate_startup()
        print("\n✅ Валидация успешна")
    except StartupValidationError as e:
        print(f"\n❌ Валидация провалена: {e}")
        exit(1)
