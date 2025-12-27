#!/usr/bin/env python3
"""
🔗 MERGE: Parsed data → Registry

Объединяет данные из мастер-парсера с текущим registry:
- Обновляет endpoints (real вместо generic)
- Добавляет examples где их нет
- Сохраняет существующий pricing (не перезаписывает)

Автор: AUTOPILOT
"""

import json
from pathlib import Path
from typing import Dict, Any


def merge_parsed_to_registry():
    """Объединить parsed данные с registry"""
    
    print("🔗 ОБЪЕДИНЕНИЕ parsed данных с registry\n")
    print("=" * 70)
    
    # Load registry
    registry_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    with open(registry_path) as f:
        registry = json.load(f)
    
    # Load parsed
    parsed_path = Path("models/KIE_PARSED_SOURCE_OF_TRUTH.json")
    with open(parsed_path) as f:
        parsed = json.load(f)
    
    models = registry['models']
    parsed_models = parsed['models']
    
    stats = {
        'endpoint_updated': 0,
        'examples_added': 0,
        'pricing_kept': 0,
        'no_changes': 0
    }
    
    for model_id, parsed_data in parsed_models.items():
        if model_id not in models:
            print(f"⚠️  Model {model_id} in parsed but NOT in registry!")
            continue
        
        model = models[model_id]
        changed = False
        
        # 1. Update endpoint (если parsed имеет реальный, а registry - generic)
        parsed_endpoint = parsed_data.get('endpoint')
        current_endpoint = model.get('endpoint', '')
        
        if parsed_endpoint and parsed_endpoint != current_endpoint:
            # Проверяем что это не None и не пустой
            if parsed_endpoint.strip() and parsed_endpoint != 'None':
                model['endpoint'] = parsed_endpoint
                stats['endpoint_updated'] += 1
                changed = True
                print(f"✅ {model_id[:50]:50} endpoint updated")
        
        # 2. Add examples (если их нет или меньше)
        parsed_examples = parsed_data.get('examples', [])
        current_examples = model.get('examples', [])
        
        if parsed_examples and len(parsed_examples) > len(current_examples):
            model['examples'] = parsed_examples
            stats['examples_added'] += 1
            changed = True
            print(f"✅ {model_id[:50]:50} examples added ({len(parsed_examples)})")
        
        # 3. Pricing: НЕ ПЕРЕЗАПИСЫВАЕМ, только сохраняем
        if model.get('pricing'):
            stats['pricing_kept'] += 1
        
        if not changed:
            stats['no_changes'] += 1
    
    # Save updated registry
    backup_path = Path("models/KIE_SOURCE_OF_TRUTH.backup.json")
    
    # Backup
    with open(backup_path, 'w') as f:
        with open(registry_path) as orig:
            f.write(orig.read())
    
    # Save
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"\n📊 СТАТИСТИКА MERGE:")
    print(f"   Endpoints updated: {stats['endpoint_updated']}")
    print(f"   Examples added: {stats['examples_added']}")
    print(f"   Pricing kept: {stats['pricing_kept']}")
    print(f"   No changes: {stats['no_changes']}")
    
    print(f"\n✅ Registry обновлён: {registry_path}")
    print(f"💾 Backup создан: {backup_path}")
    
    return stats


if __name__ == '__main__':
    merge_parsed_to_registry()
