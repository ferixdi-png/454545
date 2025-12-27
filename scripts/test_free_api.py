#!/usr/bin/env python3
"""
Real API test for FREE models.
Tests actual generation without spending credits.
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.kie_client import KieApiClient as KieClient
from app.kie.builder import build_payload, load_source_of_truth


async def test_free_models():
    """Test all FREE models with real API."""
    
    # Load config
    api_key = os.getenv('KIE_API_KEY')
    if not api_key:
        print("❌ KIE_API_KEY not set!")
        return
    
    client = KieClient(api_key=api_key)
    sot = load_source_of_truth()
    models = sot.get('models', {})
    
    # Find FREE models
    free_models = []
    for mid, mdata in models.items():
        if mdata.get('pricing', {}).get('rub_per_gen', 999) == 0:
            free_models.append((mid, mdata))
    
    print(f"🆓 FREE MODELS REAL API TEST")
    print("=" * 70)
    print(f"Найдено FREE моделей: {len(free_models)}")
    print()
    
    results = []
    
    for model_id, model_data in free_models:
        print(f"🧪 Тест: {model_id}")
        
        # Build test payload
        test_inputs = {'prompt': 'A beautiful sunset over the ocean'}
        
        try:
            payload = build_payload(model_id, test_inputs)
            print(f"   ✅ Payload построен: {list(payload.keys())}")
            
            # Real API call
            print(f"   🌐 Отправка в Kie.ai API...")
            result = await client.create_task(payload)
            
            task_id = result.get('taskId') or result.get('task_id')
            
            if task_id:
                print(f"   ✅ Task создан: {task_id}")
                results.append({
                    'model_id': model_id,
                    'status': 'SUCCESS',
                    'task_id': task_id
                })
                
                # Wait a bit for processing
                print(f"   ⏳ Ждём 3 сек...")
                await asyncio.sleep(3)
                
                # Check status
                status = await client.get_task_status(task_id)
                print(f"   📊 Статус: {status.get('status', 'UNKNOWN')}")
                
            else:
                print(f"   ⚠️ Task ID не получен")
                results.append({
                    'model_id': model_id,
                    'status': 'NO_TASK_ID',
                    'response': result
                })
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            results.append({
                'model_id': model_id,
                'status': 'ERROR',
                'error': str(e)
            })
        
        print()
    
    # Summary
    print("=" * 70)
    print("📊 ИТОГО:")
    success = sum(1 for r in results if r['status'] == 'SUCCESS')
    print(f"   ✅ Успешно: {success}/{len(free_models)}")
    print(f"   ❌ Ошибок: {len(free_models) - success}/{len(free_models)}")
    print(f"   💰 Credits потрачено: 0 (все FREE модели)")
    
    print("\n📝 Детали:")
    for r in results:
        status_emoji = "✅" if r['status'] == 'SUCCESS' else "❌"
        print(f"   {status_emoji} {r['model_id']}: {r['status']}")
    
    await client.close()
    
    return results


if __name__ == '__main__':
    results = asyncio.run(test_free_models())
    
    # Exit code
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    exit(0 if success_count > 0 else 1)
