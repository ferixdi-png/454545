#!/usr/bin/env python3
"""
Dry-run validation для всех 72 моделей
БЮДЖЕТ: 0 credits (только проверка payload build)
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload, load_source_of_truth


def dry_run_all_models():
    """Проверка build_payload для всех моделей (0 credits)"""
    
    print('🧪 DRY-RUN VALIDATION: ВСЕ 72 МОДЕЛИ\n')
    print('⚠️  БЮДЖЕТ: 0 credits (только build_payload)\n')
    
    # Load SOT
    sot = load_source_of_truth()
    models_dict = sot.get('models', {})
    
    print(f'📦 Загружено моделей: {len(models_dict)}\n')
    
    results = {
        'success': [],
        'failed': [],
        'total': len(models_dict)
    }
    
    for i, (model_id, model_data) in enumerate(models_dict.items(), 1):
        print(f'[{i}/{len(models_dict)}] {model_id}... ', end='')
        
        try:
            # Минимальный payload
            examples = model_data.get('examples', [])
            
            # Пробуем построить payload
            if examples and len(examples) > 0:
                # Берём первый пример
                example = examples[0]
                user_inputs = example.get('input', {})
            else:
                # Fallback: пустой prompt
                user_inputs = {'prompt': 'test'}
            
            # BUILD PAYLOAD (без API call!)
            payload = build_payload(model_id, user_inputs)
            
            # Проверка структуры
            # WRAPPED format: {model: ..., input: {...}}
            # DIRECT format: {model: ..., prompt: ..., ...} (veo3_fast, V4)
            has_model = 'model' in payload
            is_wrapped = 'input' in payload and isinstance(payload['input'], dict)
            is_direct = 'model' in payload and 'prompt' in payload and 'input' not in payload
            
            if has_model and (is_wrapped or is_direct):
                format_type = "WRAPPED" if is_wrapped else "DIRECT"
                print(f'✅')
                results['success'].append(model_id)
            else:
                print(f'⚠️  странная структура: {list(payload.keys())[:5]}')
                results['failed'].append({
                    'model': model_id,
                    'error': f'Invalid payload structure: {list(payload.keys())}'
                })
                
        except Exception as e:
            print(f'❌ {str(e)[:50]}')
            results['failed'].append({
                'model': model_id,
                'error': str(e)
            })
    
    # Summary
    print(f'\n📊 ИТОГИ DRY-RUN:')
    print(f'   ✅ Успешно: {len(results["success"])}/{results["total"]} ({len(results["success"])/results["total"]*100:.1f}%)')
    print(f'   ❌ Ошибок: {len(results["failed"])}/{results["total"]}')
    
    if results['failed']:
        print(f'\n❌ ОШИБКИ:')
        for fail in results['failed'][:10]:
            print(f'   - {fail["model"]}: {fail["error"][:80]}')
    
    # Save results
    output = {
        'test_type': 'dry_run_payload_build',
        'credits_spent': 0,
        'total_models': results['total'],
        'success_count': len(results['success']),
        'failed_count': len(results['failed']),
        'success_rate': len(results['success']) / results['total'] * 100,
        'results': results
    }
    
    output_file = Path('artifacts/dry_run_validation_cycle16.json')
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f'\n💾 Результаты: {output_file}')
    print(f'💰 Потрачено credits: 0 ✅')
    
    return len(results['failed']) == 0


if __name__ == '__main__':
    success = dry_run_all_models()
    sys.exit(0 if success else 1)
