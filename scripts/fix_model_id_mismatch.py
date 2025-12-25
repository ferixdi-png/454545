#!/usr/bin/env python3
"""
Фикс model_id mismatch - синхронизация с реальными tech IDs из Kie.ai API
"""
import json
from pathlib import Path


def fix_model_ids():
    """Исправляем model_id на реальные из примеров payload"""
    
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'r') as f:
        registry = json.load(f)
    
    print("=" * 80)
    print("🔧 FIXING MODEL_ID MISMATCH")
    print("=" * 80)
    
    models = registry['models']
    fixed_models = {}
    fixes = []
    
    for model_id, model_data in models.items():
        # Извлекаем реальный tech ID из примера
        examples = model_data.get('examples', [])
        
        if examples and 'model' in examples[0]:
            real_tech_id = examples[0]['model']
            
            # Если не совпадает - фиксим
            if real_tech_id != model_id:
                fixes.append({
                    'old': model_id,
                    'new': real_tech_id,
                    'display_name': model_data.get('display_name', '')
                })
                
                # Обновляем model_id везде
                model_data['model_id'] = real_tech_id
                model_data['old_registry_id'] = model_id  # Сохраняем для истории
                
                # Обновляем в examples (уже правильный)
                fixed_models[real_tech_id] = model_data
                
                print(f"✅ {model_id} → {real_tech_id}")
            else:
                fixed_models[model_id] = model_data
        else:
            # Нет примеров - оставляем как есть
            fixed_models[model_id] = model_data
    
    print(f"\n📊 Fixed: {len(fixes)} models")
    
    # Обновляем registry
    registry['models'] = fixed_models
    registry['total_models'] = len(fixed_models)
    
    # Сохраняем
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Registry updated: models/KIE_SOURCE_OF_TRUTH.json")
    
    # Сохраняем список фиксов
    fixes_file = Path('artifacts/model_id_fixes.json')
    with open(fixes_file, 'w') as f:
        json.dump(fixes, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Fixes log: {fixes_file}")
    
    return len(fixes)


if __name__ == '__main__':
    fixes_count = fix_model_ids()
    print(f"\n✅ Total fixes applied: {fixes_count}")
