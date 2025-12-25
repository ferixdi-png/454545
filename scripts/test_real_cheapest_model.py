#!/usr/bin/env python3
"""
РЕАЛЬНЫЙ ТЕСТ самой дешевой модели (elevenlabs/speech-to-text - $3)
ЛИМИТ: 1 тест = 3 USD = 600 credits
"""
import json
import httpx
import os
import time
from pathlib import Path


def load_registry():
    with open('models/KIE_SOURCE_OF_TRUTH.json', 'r') as f:
        return json.load(f)


def get_cheapest_model(registry):
    """Находим самую дешевую модель"""
    models = registry['models']
    models_with_price = [(mid, m) for mid, m in models.items() if m.get('pricing')]
    cheapest = sorted(models_with_price, key=lambda x: x[1]['pricing'].get('usd_per_gen', 999))
    return cheapest[0] if cheapest else None


def test_real_generation(model_id: str, model_data: dict):
    """Реальный тест генерации"""
    
    API_KEY = os.getenv('KIE_API_KEY')
    if not API_KEY:
        print("❌ KIE_API_KEY not set!")
        return None
    
    # Берем первый example
    example = model_data['examples'][0]
    pricing = model_data['pricing']
    
    print(f"\n🚀 REAL TEST: {model_id}")
    print(f"   Price: ${pricing['usd_per_gen']} / {pricing['rub_per_gen']}₽")
    print(f"   Credits: {pricing['credits_per_gen']}")
    print(f"\n⚠️  THIS WILL SPEND ~{pricing['credits_per_gen']} CREDITS!")
    
    # Подтверждение (автоматическое для CI)
    if os.getenv('CI') != 'true':
        confirm = input("\n   Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("   Cancelled.")
            return None
    
    # Строим request
    url = "https://api.kie.ai/api/v1/jobs/createTask"
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Используем callback URL (нужен для async API)
    # В реальности нужен свой сервер для callback, но для теста можем использовать webhook.site
    # ИЛИ использовать polling
    
    payload = example.copy()
    # Заменяем callback на реальный (или используем webhook.site для теста)
    payload['callBackUrl'] = 'https://webhook.site/your-unique-id'  # TODO: real callback
    
    print(f"\n📤 REQUEST:")
    print(f"   URL: {url}")
    print(f"   Payload: {json.dumps(payload, indent=2)[:300]}...")
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            
            print(f"\n📥 RESPONSE:")
            print(f"   Status: {resp.status_code}")
            print(f"   Headers: {dict(resp.headers)}")
            
            if resp.status_code == 200:
                result = resp.json()
                print(f"   Body: {json.dumps(result, indent=2)[:500]}")
                
                # Сохраняем результат
                test_result = {
                    'model_id': model_id,
                    'status': 'success',
                    'status_code': resp.status_code,
                    'request': payload,
                    'response': result,
                    'credits_spent': pricing['credits_per_gen'],
                    'timestamp': time.time()
                }
                
                return test_result
            else:
                print(f"   Error: {resp.text}")
                
                test_result = {
                    'model_id': model_id,
                    'status': 'error',
                    'status_code': resp.status_code,
                    'error': resp.text,
                    'timestamp': time.time()
                }
                
                return test_result
                
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        
        return {
            'model_id': model_id,
            'status': 'exception',
            'error': str(e),
            'timestamp': time.time()
        }


def main():
    print("=" * 80)
    print("🧪 REAL API TEST - TOP-1 CHEAPEST MODEL")
    print("=" * 80)
    
    registry = load_registry()
    
    # Находим cheapest
    cheapest = get_cheapest_model(registry)
    
    if not cheapest:
        print("❌ No models with pricing found!")
        return 1
    
    model_id, model_data = cheapest
    
    # Запускаем тест
    result = test_real_generation(model_id, model_data)
    
    if not result:
        print("\n⚠️  Test cancelled")
        return 0
    
    # Сохраняем результат
    output_file = Path('artifacts/real_test_result.json')
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Test result saved: {output_file}")
    
    if result['status'] == 'success':
        print(f"\n✅ TEST PASSED!")
        print(f"   Model: {model_id}")
        print(f"   Credits spent: ~{model_data['pricing']['credits_per_gen']}")
        return 0
    else:
        print(f"\n❌ TEST FAILED!")
        print(f"   Status: {result['status']}")
        return 1


if __name__ == '__main__':
    exit(main())
