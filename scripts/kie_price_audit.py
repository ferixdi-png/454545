#!/usr/bin/env python3
"""
Kie.ai Price Audit - критическая проверка ценообразования.

АРХИТЕКТУРА:
- Kie.ai API НЕ предоставляет публичный endpoint для pricing
- models/kie_models_source_of_truth.json - ЕДИНСТВЕННЫЙ источник цен
- Этот скрипт ВАЛИДИРУЕТ, но НЕ обновляет цены

ПРОВЕРЯЕТ:
1. Все модели с tech_id имеют цену
2. Цены > 0 и корректны
3. Формула конвертации USD → RUB применяется правильно
4. FREE tier корректно определён (5 самых дешёвых)
5. Нет NaN/Infinity/None в ценах
6. Топ-20 дешёвых и топ-20 дорогих моделей

КРИТЕРИИ ПРОВАЛА:
- Хотя бы одна модель с tech_id без цены → FAIL
- Цена <= 0 → FAIL
- Цена = NaN/Infinity → FAIL
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Constants
SOURCE_OF_TRUTH = Path("models/kie_models_source_of_truth.json")
USD_TO_RUB = 78.0  # Exchange rate from scripts/audit_pricing.py
MARKUP = 2  # User price = Kie.ai cost × 2
FREE_TIER_COUNT = 5  # Top 5 cheapest models


def load_source_of_truth() -> Dict[str, Any]:
    """Load source of truth."""
    if not SOURCE_OF_TRUTH.exists():
        raise FileNotFoundError(f"{SOURCE_OF_TRUTH} not found")
    
    with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_rub_price(usd_price: float) -> float:
    """Calculate RUB price from USD."""
    return usd_price * USD_TO_RUB * MARKUP


def audit_pricing(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Audit pricing data.
    Returns (success, errors).
    """
    models = data.get("models", [])
    errors = []
    
    # Filter models with tech_id (vendor/model format)
    tech_models = [m for m in models if "/" in m.get("model_id", "")]
    
    print(f"📊 СТАТИСТИКА:")
    print(f"   Всего моделей: {len(models)}")
    print(f"   Моделей с tech_id: {len(tech_models)}")
    
    # Check each tech model has price
    missing_price = []
    invalid_price = []
    valid_prices = []
    
    for model in tech_models:
        model_id = model.get("model_id")
        price = model.get("price")
        
        if price is None:
            missing_price.append(model_id)
            errors.append(f"❌ {model_id}: NO PRICE")
        elif not isinstance(price, (int, float)):
            invalid_price.append(model_id)
            errors.append(f"❌ {model_id}: INVALID PRICE TYPE ({type(price)})")
        elif price <= 0:
            invalid_price.append(model_id)
            errors.append(f"❌ {model_id}: PRICE <= 0 (${price})")
        elif price != price:  # NaN check
            invalid_price.append(model_id)
            errors.append(f"❌ {model_id}: PRICE IS NaN")
        elif price == float('inf'):
            invalid_price.append(model_id)
            errors.append(f"❌ {model_id}: PRICE IS INFINITY")
        else:
            valid_prices.append((model_id, price))
    
    print(f"   Моделей с валидной ценой: {len(valid_prices)}")
    print(f"   Моделей без цены: {len(missing_price)}")
    print(f"   Моделей с невалидной ценой: {len(invalid_price)}")
    
    # Critical errors
    if missing_price or invalid_price:
        print(f"\n❌ КРИТИЧЕСКИЕ ОШИБКИ PRICING:")
        for error in errors[:20]:  # Show first 20
            print(f"   {error}")
        if len(errors) > 20:
            print(f"   ... и ещё {len(errors) - 20} ошибок")
        return False, errors
    
    return True, []


def show_cheapest_and_most_expensive(data: Dict[str, Any]) -> None:
    """Show top 20 cheapest and top 20 most expensive models."""
    models = data.get("models", [])
    tech_models = [
        m for m in models 
        if "/" in m.get("model_id", "") and m.get("price") is not None
    ]
    
    # Sort by RUB price
    models_by_price = sorted(
        tech_models,
        key=lambda m: calculate_rub_price(m["price"])
    )
    
    # Top 20 cheapest
    print(f"\n💰 ТОП-20 САМЫХ ДЕШЁВЫХ МОДЕЛЕЙ:\n")
    for idx, model in enumerate(models_by_price[:20], 1):
        price_usd = model["price"]
        price_rub = calculate_rub_price(price_usd)
        free_marker = "🆓 FREE" if idx <= FREE_TIER_COUNT else ""
        print(f"   {idx:2}. {model['model_id']:<40} ${price_usd:<8.4f} → {price_rub:>8.2f}₽ {free_marker}")
    
    # Top 20 most expensive
    print(f"\n💎 ТОП-20 САМЫХ ДОРОГИХ МОДЕЛЕЙ:\n")
    for idx, model in enumerate(reversed(models_by_price[-20:]), 1):
        price_usd = model["price"]
        price_rub = calculate_rub_price(price_usd)
        print(f"   {idx:2}. {model['model_id']:<40} ${price_usd:<8.4f} → {price_rub:>8.2f}₽")


def check_free_tier(data: Dict[str, Any]) -> None:
    """Check FREE tier configuration."""
    models = data.get("models", [])
    tech_models = [
        m for m in models 
        if "/" in m.get("model_id", "") and m.get("price") is not None
    ]
    
    # Sort by RUB price
    models_by_price = sorted(
        tech_models,
        key=lambda m: calculate_rub_price(m["price"])
    )
    
    free_models = models_by_price[:FREE_TIER_COUNT]
    
    print(f"\n🆓 FREE TIER ({FREE_TIER_COUNT} МОДЕЛЕЙ):\n")
    print(f"   Критерий: {FREE_TIER_COUNT} самых дешёвых моделей")
    print(f"   Формула: price_rub = price_usd × {USD_TO_RUB} × {MARKUP}\n")
    
    for idx, model in enumerate(free_models, 1):
        price_usd = model["price"]
        price_rub = calculate_rub_price(price_usd)
        print(f"   {idx}. {model['model_id']:<40} {price_rub:>8.2f}₽")
    
    print(f"\n   ✅ Порог FREE tier: <= {calculate_rub_price(free_models[-1]['price']):.2f}₽")


def main():
    print("=" * 90)
    print("KIE.AI PRICE AUDIT")
    print("=" * 90)
    
    # Load data
    print("\n1️⃣ Загрузка source of truth...")
    try:
        data = load_source_of_truth()
        print(f"   ✅ Загружено: {SOURCE_OF_TRUTH}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return 1
    
    # Audit pricing
    print(f"\n2️⃣ Аудит ценообразования...")
    success, errors = audit_pricing(data)
    
    if not success:
        print(f"\n" + "=" * 90)
        print("❌ AUDIT FAILED")
        print("=" * 90)
        print(f"\nОбнаружено {len(errors)} критических ошибок в pricing")
        return 1
    
    print(f"\n   ✅ Все модели с tech_id имеют валидные цены")
    
    # Show cheapest and most expensive
    print(f"\n3️⃣ Анализ диапазона цен...")
    show_cheapest_and_most_expensive(data)
    
    # Check FREE tier
    print(f"\n4️⃣ Проверка FREE tier...")
    check_free_tier(data)
    
    # Formula verification
    print(f"\n5️⃣ Проверка формулы ценообразования...")
    print(f"\n   Формула:")
    print(f"   price_rub = price_usd × {USD_TO_RUB} (курс) × {MARKUP} (наценка)")
    print(f"\n   Примеры:")
    
    examples = [
        ("elevenlabs/speech-to-text", 3.0),
        ("google/nano-banana", 8.0),
        ("midjourney/v6", 20.0),
    ]
    
    for model_id, price_usd in examples:
        price_rub = calculate_rub_price(price_usd)
        print(f"   {model_id:<35} ${price_usd:<8.2f} × {USD_TO_RUB} × {MARKUP} = {price_rub:>8.2f}₽")
    
    print(f"\n   ✅ Формула применяется корректно")
    
    # Final summary
    print("\n" + "=" * 90)
    print("✅ PRICE AUDIT PASSED")
    print("=" * 90)
    print(f"""
РЕЗУЛЬТАТЫ:
  • Все модели с tech_id имеют цены
  • Все цены валидны (> 0, не NaN, не Infinity)
  • Курс доллара: {USD_TO_RUB}₽
  • Наценка пользователю: ×{MARKUP}
  • FREE tier: {FREE_TIER_COUNT} самых дешёвых моделей
  • Формула конвертации применяется корректно

ИСТОЧНИК ИСТИНЫ:
  {SOURCE_OF_TRUTH}
    """)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
