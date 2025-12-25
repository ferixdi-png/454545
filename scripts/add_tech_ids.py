#!/usr/bin/env python3
"""
Автоматическое добавление tech_model_id ко всем моделям
"""
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "models" / "kie_models_final_truth.json"

def add_tech_model_ids():
    """Добавить tech_model_id для всех моделей"""
    
    with open(REGISTRY_PATH) as f:
        data = json.load(f)
    
    print("🔧 ДОБАВЛЕНИЕ TECH_MODEL_ID")
    print("=" * 80)
    print()
    print(f"📦 Registry v{data.get('version')}")
    print(f"📊 Моделей: {len(data['models'])}")
    print()
    
    added = 0
    already_had = 0
    
    for model in data['models']:
        if model.get('tech_model_id'):
            already_had += 1
            continue
        
        # Используем model_id как tech_model_id
        # (это правильно, т.к. model_id уже в формате Kie.ai)
        model['tech_model_id'] = model['model_id']
        added += 1
    
    print(f"✅ Tech IDs добавлено: {added}")
    print(f"ℹ️  Уже были: {already_had}")
    print()
    
    # Сохранить
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Сохранено: {REGISTRY_PATH}")
    print()
    
    return added

if __name__ == "__main__":
    added = add_tech_model_ids()
    
    if added > 0:
        print("=" * 80)
        print("✅ TECH_MODEL_ID ДОБАВЛЕНЫ")
        print("=" * 80)
    else:
        print("ℹ️  Все модели уже имели tech_model_id")
