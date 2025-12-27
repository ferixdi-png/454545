#!/usr/bin/env python3
"""
РЕАЛЬНЫЙ PAID TEST - потратит настоящие деньги на Kie.ai!

МОДЕЛЬ: elevenlabs/speech-to-text
СТОИМОСТЬ: 474 RUB (~$6 USD)
ЦЕЛЬ: Проверить что PAID модели работают в production

⚠️  ВАЖНО: Этот тест потратит РЕАЛЬНЫЕ деньги!
"""
import os
import sys
import json
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.client_v4 import KieApiClientV4
from app.kie.builder import (
    load_source_of_truth,
    get_model_schema,
    get_model_config,
    build_payload
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_paid_model():
    """Test cheapest PAID model."""
    
    # Config
    model_id = "elevenlabs/speech-to-text"
    expected_cost = 474.0  # RUB
    
    print("\n" + "="*60)
    print("⚠️  РЕАЛЬНЫЙ PAID TEST")
    print("="*60)
    print(f"Модель: {model_id}")
    print(f"Стоимость: {expected_cost} RUB (~${expected_cost/78:.2f} USD)")
    print("\n⚠️  Этот тест потратит РЕАЛЬНЫЕ деньги на вашем Kie.ai аккаунте!")
    print("\nПродолжить? [yes/no]: ", end='')
    
    # Manual confirmation required
    confirm = input().strip().lower()
    if confirm != 'yes':
        print("\n❌ Тест отменен пользователем")
        return False
    
    print("\n🚀 Запуск PAID теста...\n")
    
    # Initialize
    api_key = os.getenv('KIE_API_KEY')
    if not api_key:
        print("❌ KIE_API_KEY not set")
        return False
    
    client = KieApiClientV4(api_key=api_key)
    sot = load_source_of_truth()
    
    # Get model config
    config = get_model_config(model_id, sot)
    if not config:
        print(f"❌ Model config not found for {model_id}")
        return False
    
    # Check pricing
    cost_rub = config.get('pricing', {}).get('rub_per_gen', 0)
    print(f"💵 Expected cost: {cost_rub} RUB")
    
    if cost_rub != expected_cost:
        print(f"⚠️  WARNING: Expected {expected_cost} but got {cost_rub}")
    
    # Build minimal payload
    schema = get_model_schema(model_id, sot)
    input_schema = schema.get('input_schema', {})
    
    # Use example from schema
    examples = input_schema.get('input', {}).get('examples', [])
    if examples and isinstance(examples[0], dict):
        user_params = examples[0].copy()
    else:
        print("❌ No examples found in schema")
        return False
    
    payload = build_payload(model_id, user_params, sot)
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    # Make API call
    print(f"\n🚀 Making REAL API call (will spend {cost_rub} RUB)...")
    
    try:
        response = await client.create_task(model_id, payload)
        
        # Check response
        response_code = response.get('code', 0)
        if response_code != 200:
            error_msg = response.get('msg', 'Unknown error')
            print(f"❌ API error: {error_msg} (code={response_code})")
            print(f"📊 Response: {json.dumps(response, indent=2)}")
            return False
        
        # Check taskId
        task_id = response.get('data', {}).get('taskId')
        if not task_id:
            print(f"❌ No taskId in response")
            print(f"📊 Response: {json.dumps(response, indent=2)}")
            return False
        
        print(f"\n✅ SUCCESS! Task created")
        print(f"📊 Response: {json.dumps(response, indent=2)}")
        print(f"\n💸 Потрачено: {cost_rub} RUB (~${cost_rub/78:.2f} USD)")
        print(f"🎫 Task ID: {task_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        logger.error("Full traceback:", exc_info=True)
        return False


async def main():
    success = await test_paid_model()
    
    print("\n" + "="*60)
    if success:
        print("✅ PAID TEST PASSED - REAL API CALL SUCCESS")
        print("="*60)
        sys.exit(0)
    else:
        print("❌ PAID TEST FAILED")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
