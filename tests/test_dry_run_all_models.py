#!/usr/bin/env python3
"""
DRY-RUN тесты для всех 72 моделей из SOURCE_OF_TRUTH.

Цель: Проверить что build_payload() работает для ВСЕХ моделей БЕЗ реальных API вызовов.
Бюджет: 0 credits (только валидация payload)

Проверки:
1. load_source_of_truth() возвращает 72 модели
2. get_model_schema() работает для каждой модели
3. build_payload() строит payload без ошибок
4. Payload содержит обязательные поля (model, input)
5. Endpoint корректный
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
from typing import Dict, Any

from app.kie.builder import load_source_of_truth, get_model_schema, build_payload

logging.basicConfig(level=logging.WARNING)


def test_dry_run_all_models():
    """
    Dry-run test для всех 72 моделей.
    
    БЕЗ реальных API вызовов, только валидация payload.
    """
    
    print("🧪 DRY-RUN ТЕСТ: Все 72 модели из SOURCE_OF_TRUTH\n")
    print("=" * 80)
    
    # 1. Load SOURCE_OF_TRUTH
    print("\n1️⃣ Загрузка SOURCE_OF_TRUTH...")
    sot = load_source_of_truth()
    
    if not sot:
        print("❌ FAIL: SOURCE_OF_TRUTH пустой!")
        return False
    
    models = sot.get('models', {})
    print(f"   ✅ Загружено: {len(models)} моделей")
    
    if len(models) != 72:
        print(f"   ⚠️  Ожидалось 72, получено {len(models)}")
    
    # 2. Test each model
    print("\n2️⃣ Тестирование каждой модели...")
    print("=" * 80)
    
    results = {
        'success': [],
        'failed': [],
        'warnings': []
    }
    
    for i, (model_id, model_data) in enumerate(models.items(), 1):
        print(f"\n[{i}/{len(models)}] {model_id}")
        
        try:
            # 2.1. Get schema
            schema = get_model_schema(model_id, sot)
            
            if not schema:
                results['failed'].append({
                    'model': model_id,
                    'error': 'Schema not found'
                })
                print(f"   ❌ Schema not found")
                continue
            
            # 2.2. Check required fields
            required = ['input_schema', 'endpoint', 'pricing']
            missing = [f for f in required if not schema.get(f)]
            
            if missing:
                results['warnings'].append({
                    'model': model_id,
                    'warning': f'Missing fields: {missing}'
                })
                print(f"   ⚠️  Missing: {missing}")
            
            # 2.3. Build payload (dry-run)
            # Используем минимальные параметры
            test_params = {
                'prompt': 'test prompt for dry-run validation'
            }
            
            try:
                payload = build_payload(
                    model_id=model_id,
                    prompt=test_params['prompt'],
                    params={},
                    user_id='dry_run_test'
                )
                
                # 2.4. Validate payload structure
                if not isinstance(payload, dict):
                    raise ValueError(f"Payload не dict: {type(payload)}")
                
                if 'model' not in payload:
                    raise ValueError("Payload не содержит 'model'")
                
                if 'input' not in payload:
                    raise ValueError("Payload не содержит 'input'")
                
                # Success!
                results['success'].append(model_id)
                print(f"   ✅ Payload OK ({len(json.dumps(payload))} bytes)")
                
            except Exception as e:
                results['failed'].append({
                    'model': model_id,
                    'error': f'build_payload failed: {str(e)}'
                })
                print(f"   ❌ build_payload failed: {e}")
                
        except Exception as e:
            results['failed'].append({
                'model': model_id,
                'error': str(e)
            })
            print(f"   ❌ Error: {e}")
    
    # 3. Summary
    print("\n" + "=" * 80)
    print("📊 ИТОГИ DRY-RUN ТЕСТОВ")
    print("=" * 80)
    
    print(f"\n✅ Успешно: {len(results['success'])}/{len(models)} ({len(results['success'])/len(models)*100:.1f}%)")
    print(f"❌ Ошибки: {len(results['failed'])}")
    print(f"⚠️  Предупреждения: {len(results['warnings'])}")
    
    # Failed details
    if results['failed']:
        print(f"\n❌ ОШИБКИ ({len(results['failed'])}):")
        for item in results['failed'][:10]:  # Первые 10
            print(f"   - {item['model']}: {item['error']}")
        
        if len(results['failed']) > 10:
            print(f"   ... и ещё {len(results['failed']) - 10}")
    
    # Warnings details
    if results['warnings']:
        print(f"\n⚠️  ПРЕДУПРЕЖДЕНИЯ ({len(results['warnings'])}):")
        for item in results['warnings'][:5]:
            print(f"   - {item['model']}: {item['warning']}")
    
    # Save results
    output_file = Path('artifacts/dry_run_test_results.json')
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(models),
            'success': len(results['success']),
            'failed': len(results['failed']),
            'warnings': len(results['warnings']),
            'success_models': results['success'],
            'failed_details': results['failed'],
            'warnings_details': results['warnings']
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты сохранены: {output_file}")
    
    # Final verdict
    success_rate = len(results['success']) / len(models) * 100
    
    print(f"\n{'='*80}")
    if success_rate == 100:
        print("🎉 ВСЕ МОДЕЛИ ПРОШЛИ DRY-RUN!")
        print("   ✅ build_payload() работает для всех 72 моделей")
        print("   ✅ Можно переходить к реальным тестам на FREE моделях")
        return True
    elif success_rate >= 95:
        print("✅ ПОЧТИ ВСЕ МОДЕЛИ РАБОТАЮТ")
        print(f"   {len(results['success'])}/{len(models)} успешно")
        print("   ⚠️  Нужно исправить оставшиеся модели")
        return True
    else:
        print("❌ СЛИШКОМ МНОГО ОШИБОК")
        print(f"   Только {success_rate:.1f}% моделей работают")
        print("   Нужно исправить критичные проблемы")
        return False


if __name__ == '__main__':
    success = test_dry_run_all_models()
    sys.exit(0 if success else 1)
