#!/usr/bin/env python3
"""
Мержит KIE_PARSED_SOURCE_OF_TRUTH.json и KIE_SOURCE_OF_TRUTH.json

Стратегия:
1. Берём PARSED как базу (_metadata, свежие examples)
2. Дополняем endpoint/pricing из SOT где отсутствуют
3. Сохраняем в KIE_SOURCE_OF_TRUTH.json (обновляем master)
"""

import json
from pathlib import Path


def merge_sources():
    """Merge parsed data with SOT fallbacks"""
    
    # Load both sources
    sot_path = Path('models/KIE_SOURCE_OF_TRUTH.json')
    parsed_path = Path('models/KIE_PARSED_SOURCE_OF_TRUTH.json')
    
    sot_data = json.load(open(sot_path))
    parsed_data = json.load(open(parsed_path))
    
    sot_models = sot_data['models']
    parsed_models = parsed_data['models']
    
    print('🔄 МЕРДЖ: PARSED + SOT\n')
    
    # Merge strategy
    merged_models = {}
    fixes_applied = {
        'endpoint': 0,
        'pricing': 0,
        'schema': 0
    }
    
    for model_id, parsed_model in parsed_models.items():
        merged = dict(parsed_model)  # Copy parsed data
        
        # Get SOT data for this model
        sot_model = sot_models.get(model_id, {})
        
        # Fix missing endpoint
        if not merged.get('endpoint') and sot_model.get('endpoint'):
            merged['endpoint'] = sot_model['endpoint']
            fixes_applied['endpoint'] += 1
            print(f'✅ {model_id}: добавлен endpoint из SOT')
        
        # Fix missing pricing
        if not merged.get('pricing', {}).get('rub_per_gen', 0) and sot_model.get('pricing', {}).get('rub_per_gen', 0):
            merged['pricing'] = sot_model['pricing']
            fixes_applied['pricing'] += 1
            print(f'✅ {model_id}: добавлен pricing из SOT')
        
        # Fix missing schema (if needed)
        if not merged.get('schema') and sot_model.get('schema'):
            merged['schema'] = sot_model['schema']
            fixes_applied['schema'] += 1
            print(f'✅ {model_id}: добавлена schema из SOT')
        
        merged_models[model_id] = merged
    
    # Create merged data structure
    merged_data = {
        'version': '1.1.0-PARSED-MERGED',
        'updated_at': parsed_data.get('updated_at'),
        'models': merged_models
    }
    
    # Save merged data (OVERWRITE SOT)
    print(f'\n💾 Сохранение в {sot_path}')
    with open(sot_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    # Stats
    print(f'\n📊 СТАТИСТИКА МЕРЖА:')
    print(f'   Всего моделей: {len(merged_models)}')
    print(f'   Исправлено endpoint: {fixes_applied["endpoint"]}')
    print(f'   Исправлено pricing: {fixes_applied["pricing"]}')
    print(f'   Исправлено schema: {fixes_applied["schema"]}')
    
    # Verify completeness
    complete_endpoint = sum(1 for m in merged_models.values() if m.get('endpoint'))
    complete_pricing = sum(1 for m in merged_models.values() if m.get('pricing', {}).get('rub_per_gen', 0) > 0)
    complete_metadata = sum(1 for m in merged_models.values() if m.get('_metadata'))
    
    print(f'\n✅ ФИНАЛЬНОЕ КАЧЕСТВО:')
    print(f'   endpoint: {complete_endpoint}/{len(merged_models)} ({complete_endpoint/len(merged_models)*100:.1f}%)')
    print(f'   pricing: {complete_pricing}/{len(merged_models)} ({complete_pricing/len(merged_models)*100:.1f}%)')
    print(f'   _metadata: {complete_metadata}/{len(merged_models)} ({complete_metadata/len(merged_models)*100:.1f}%)')
    
    return merged_data


if __name__ == '__main__':
    merge_sources()
