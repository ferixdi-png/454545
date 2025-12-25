#!/usr/bin/env python3
"""
Мерж pricing в KIE_SOURCE_OF_TRUTH.json
Добавляет цены из artifacts/pricing_table.json
"""

import json
from pathlib import Path
from typing import Dict


def load_pricing() -> Dict:
    """Загружаем pricing table"""
    pricing_file = Path("artifacts/pricing_table.json")
    with open(pricing_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # КУРС ФИКСИРОВАННЫЙ: $1 = 79₽
    FIXED_RATE = 79.0
    
    # Создаем mapping model_id -> pricing
    pricing_map = {}
    for model in data['models']:
        model_id = model['model_id']
        usd = model.get('price_usd', 0)
        
        pricing_map[model_id] = {
            "credits_per_gen": usd * 200,  # 1 USD = 200 credits (из Kie.ai)
            "usd_per_gen": usd,
            "rub_per_gen": usd * FIXED_RATE,  # ИСПРАВЛЕНО: $1 = 79₽
            "is_free": model.get('is_free', False),
            "rank": model['rank']
        }
    
    return pricing_map


def merge_pricing_into_registry():
    """Мерж pricing в registry"""
    
    # Загружаем registry
    registry_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    # Загружаем pricing
    pricing_map = load_pricing()
    
    print("=" * 80)
    print("💰 MERGING PRICING INTO REGISTRY")
    print("=" * 80)
    print(f"\nRegistry models: {len(registry['models'])}")
    print(f"Pricing models: {len(pricing_map)}")
    
    # Мануальный маппинг для исправления несовпадений
    MANUAL_MAPPING = {
        # Seedream models
        'seedream/seedream': 'bytedance/seedream',
        'seedream/seedream-v4-text-to-image': 'bytedance/seedream-v4-text-to-image',
        'seedream/seedream-v4-edit': 'seedream/4.5-edit',
        
        # Flux2 models
        'flux2/pro-image-to-image': 'flux-2/pro-image-to-image',
        'flux2/pro-text-to-image': 'flux-2/pro-text-to-image',
        'flux2/flex-image-to-image': 'flux-2/flex-image-to-image',
        'flux2/flex-text-to-image': 'flux-2/flex-text-to-image',
        
        # Google models
        'google/pro-image-to-image': 'google/nano-banana-pro',
        'google/nano-banana-edit': 'google/nano-banana-edit',
        
        # Qwen models
        'z-image/z-image': 'qwen/z-image',
        'qwen/image-to-image': 'qwen/image-edit',
        'qwen/text-to-image': 'qwen/z-image',
    }
    
    # Мерж
    matched = 0
    unmatched = []
    
    for model_id, model_data in registry['models'].items():
        # Проверяем точное совпадение
        if model_id in pricing_map:
            model_data['pricing'] = pricing_map[model_id]
            matched += 1
        # Проверяем мануальный маппинг
        elif model_id in MANUAL_MAPPING:
            mapped_id = MANUAL_MAPPING[model_id]
            if mapped_id in pricing_map:
                model_data['pricing'] = pricing_map[mapped_id]
                matched += 1
                print(f"  ✅ Mapped: {model_id} -> {mapped_id}")
            else:
                unmatched.append(model_id)
        else:
            # Пробуем нормализацию
            # Убираем version suffixes и пробуем снова
            normalized_id = model_id.split('/')[0] + '/' + model_id.split('/')[1].split('-')[0]
            
            if normalized_id in pricing_map:
                model_data['pricing'] = pricing_map[normalized_id]
                matched += 1
            else:
                unmatched.append(model_id)
    
    print(f"\n✅ Matched: {matched}")
    print(f"⚠️  Unmatched: {len(unmatched)}")
    
    if unmatched:
        print(f"\nUnmatched models (first 10):")
        for mid in unmatched[:10]:
            print(f"  - {mid}")
    
    # Сохраняем обновленный registry
    with open(registry_file, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Registry updated: {registry_file}")
    
    # Статистика
    with_pricing = sum(1 for m in registry['models'].values() if m.get('pricing'))
    free_count = sum(1 for m in registry['models'].values() if m.get('pricing', {}).get('is_free'))
    
    print(f"\n📊 Final stats:")
    print(f"   - Models with pricing: {with_pricing}/{len(registry['models'])}")
    print(f"   - Free models: {free_count}")
    print(f"   - Paid models: {with_pricing - free_count}")


if __name__ == "__main__":
    merge_pricing_into_registry()
