#!/usr/bin/env python3
"""
ФИНАЛЬНАЯ ФИКСАЦИЯ ЦЕН
Используем artifacts/pricing_table.json (USD цены спарсены ранее)
Применяем ПРАВИЛЬНУЮ формулу: RUB = USD × 79 × 2
"""
import json
from pathlib import Path

# ФОРМУЛА (как требует пользователь)
EXCHANGE_RATE = 79.0  # RUB/USD
MARKUP = 2.0  # Наценка ×2
# ИТОГО: RUB = USD × 158

def load_pricing_table():
    """Загружаем спарсенные USD цены"""
    with open('artifacts/pricing_table.json', 'r') as f:
        data = json.load(f)
    
    return data['models']

def recalculate_prices(models_pricing):
    """Пересчитываем цены по правильной формуле"""
    
    recalculated = {}
    
    for model in models_pricing:
        model_id = model['model_id']
        usd = model['price_usd']
        is_free = model.get('is_free', False)
        
        # Применяем формулу
        rub = usd * EXCHANGE_RATE * MARKUP if not is_free else 0
        credits = usd * 200  # 1 USD = 200 credits
        
        recalculated[model_id] = {
            'usd_per_gen': usd,
            'rub_per_gen': rub,
            'credits_per_gen': credits,
            'is_free': is_free,
            'rank': model.get('rank'),
            'source': 'pricing_table_recalculated'
        }
    
    return recalculated


def apply_to_registry(pricing_map):
    """Применяем цены к registry"""
    
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'r') as f:
        registry = json.load(f)
    
    models = registry['models']
    
    print("=" * 80)
    print("🔄 APPLYING RECALCULATED PRICES TO REGISTRY")
    print("=" * 80)
    print(f"\nFormula: RUB = USD × {EXCHANGE_RATE} × {MARKUP} = USD × {EXCHANGE_RATE * MARKUP}")
    
    matched = 0
    unmatched = []
    
    for model_id, model_data in models.items():
        if model_id in pricing_map:
            model_data['pricing'] = pricing_map[model_id]
            matched += 1
        else:
            unmatched.append(model_id)
    
    print(f"\n✅ Matched: {matched}")
    print(f"⚠️  Unmatched: {len(unmatched)}")
    
    if unmatched:
        print(f"\nUnmatched models (first 10):")
        for mid in unmatched[:10]:
            print(f"  - {mid}")
    
    # Сохраняем
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Registry updated!")
    
    # Статистика
    with_pricing = sum(1 for m in models.values() if m.get('pricing'))
    free_count = sum(1 for m in models.values() if m.get('pricing', {}).get('is_free'))
    
    print(f"\n📊 Final stats:")
    print(f"   - Total models: {len(models)}")
    print(f"   - With pricing: {with_pricing}")
    print(f"   - Free models: {free_count}")
    print(f"   - Paid models: {with_pricing - free_count}")
    
    # Top-5 cheapest
    print(f"\n💰 TOP-5 CHEAPEST (after recalculation):")
    
    models_with_price = [
        (mid, m['pricing'])
        for mid, m in models.items()
        if m.get('pricing') and not m['pricing'].get('is_free')
    ]
    
    cheapest = sorted(models_with_price, key=lambda x: x[1]['usd_per_gen'])[:5]
    
    for i, (mid, pricing) in enumerate(cheapest, 1):
        usd = pricing['usd_per_gen']
        rub = pricing['rub_per_gen']
        old_rub = usd * 78 * 2  # Старая формула
        
        print(f"{i}. {mid}")
        print(f"   USD: ${usd}")
        print(f"   RUB: {rub}₽ (было {old_rub}₽)")
        print(f"   Разница: {rub - old_rub:+.0f}₽")


def main():
    print("=" * 80)
    print("💰 FINAL PRICE FIXATION")
    print("=" * 80)
    
    # 1. Загружаем спарсенные USD цены
    print("\n📦 Loading pricing_table.json...")
    models_pricing = load_pricing_table()
    print(f"   ✅ Loaded {len(models_pricing)} models")
    
    # 2. Пересчитываем по правильной формуле
    print("\n🔢 Recalculating with formula: RUB = USD × 79 × 2...")
    pricing_map = recalculate_prices(models_pricing)
    print(f"   ✅ Recalculated {len(pricing_map)} models")
    
    # 3. Применяем к registry
    apply_to_registry(pricing_map)
    
    print("\n✅ PRICES FIXED!")
    print("   Source: artifacts/pricing_table.json (USD)")
    print("   Formula: RUB = USD × 79 × 2")
    print("   Status: ЗАФИКСИРОВАНО ОДИН РАЗ")


if __name__ == '__main__':
    main()
