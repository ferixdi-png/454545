#!/usr/bin/env python3
"""Тест официального API Kie.ai"""
import httpx
import json
import os

api_key = os.getenv("KIE_API_KEY", "4d49a621bc589222a2769978cb725495")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print("🔍 Проверка доступа к Kie.ai API Market...")
print()

# Попробуем разные endpoints для получения списка моделей
endpoints_to_try = [
    "https://kie.ai/api/models",  # возможно публичный список
    "https://api.kie.ai/api/v1/marketplace/models",
    "https://api.kie.ai/api/v1/models/list",
    "https://api.kie.ai/api/models",
]

with httpx.Client(timeout=30) as client:
    for endpoint in endpoints_to_try:
        try:
            print(f"Trying: {endpoint}")
            resp = client.get(endpoint, headers=headers)
            print(f"  Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✅ SUCCESS!")
                print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
                print(f"  Sample: {json.dumps(data if isinstance(data, list) and len(data) < 3 else (data if isinstance(data, dict) else str(data)[:500]), indent=2)[:500]}")
                break
            else:
                print(f"  Response: {resp.text[:200]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()
        
    # Попробуем тестовый запрос с z-image по документации
    print("\n🧪 Тест createTask с моделью 'z-image' (из документации)...")
    test_payload = {
        "model": "z-image",
        "input": {
            "prompt": "A simple test image of a red apple",
            "aspect_ratio": "1:1"
        }
    }
    
    try:
        resp = client.post(
            "https://api.kie.ai/api/v1/jobs/createTask",
            headers=headers,
            json=test_payload
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:500]}")
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 200:
                task_id = result.get("data", {}).get("taskId")
                print(f"\n✅ Task created! Task ID: {task_id}")
                
                # Проверяем статус
                print(f"\n🔎 Checking task status...")
                status_resp = client.get(
                    f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                    headers=headers
                )
                print(f"Status: {status_resp.status_code}")
                print(f"Response: {json.dumps(status_resp.json(), indent=2)[:500]}")
    except Exception as e:
        print(f"❌ Error: {e}")
