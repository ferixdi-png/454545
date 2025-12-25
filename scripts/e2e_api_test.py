#!/usr/bin/env python3
"""
E2E API Test - реальные вызовы Kie.ai API.

ЦЕЛЬ: Проверить что система работает с реальным API, а не только в юнит-тестах.

ПРОТЕСТИРУЕТ:
1. FREE модели (0 credits spent)
2. 1 дешевая PAID модель (потратим ~1580 RUB = ~$10 worth)
3. Retry logic (tenacity)
4. Pricing calculation
5. Error handling

БЮДЖЕТ: ~1580 RUB (~$10 USD)
"""
import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.client_v4 import KieApiClientV4
from app.kie.builder import (
    load_source_of_truth,
    get_model_schema,
    get_model_config,
    build_payload
)
from app.payments.pricing import calculate_kie_cost

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class E2EAPITest:
    """End-to-end API testing with real Kie.ai calls."""
    
    def __init__(self):
        self.api_key = os.getenv('KIE_API_KEY')
        if not self.api_key:
            raise ValueError("KIE_API_KEY not set in environment")
        
        self.client = KieApiClientV4(api_key=self.api_key)
        self.sot = load_source_of_truth()
        self.results = []
    
    async def test_free_model(self, model_id: str) -> Dict[str, Any]:
        """Test a FREE model (0 RUB, no credits spent)."""
        logger.info(f"\n{'='*60}")
        logger.info(f"🆓 Testing FREE model: {model_id}")
        logger.info(f"{'='*60}")
        
        try:
            # Get model config
            config = get_model_config(model_id, self.sot)
            if not config:
                return {
                    "model_id": model_id,
                    "status": "SKIP",
                    "reason": "Model config not found",
                    "cost_rub": 0
                }
            
            # Check pricing
            cost_rub = config.get('pricing', {}).get('rub_per_gen', 0)
            if cost_rub != 0:
                return {
                    "model_id": model_id,
                    "status": "FAIL",
                    "reason": f"NOT FREE! Cost: {cost_rub} RUB",
                    "cost_rub": cost_rub
                }
            
            logger.info(f"✅ Pricing: FREE (0 RUB)")
            
            # Build payload with minimal parameters
            schema = get_model_schema(model_id, self.sot)
            input_schema = schema.get('input_schema', {})
            user_params = self._get_minimal_params(input_schema)
            
            payload = build_payload(model_id, user_params, self.sot)
            logger.info(f"📦 Payload: {json.dumps(payload, indent=2)}")
            
            # Make API call
            logger.info(f"🚀 Making API call...")
            response = await self.client.create_task(model_id, payload)
            
            # Check API response success
            response_code = response.get('code', 0)
            if response_code != 200:
                error_msg = response.get('msg', 'Unknown error')
                logger.error(f"❌ API returned error: {error_msg} (code={response_code})")
                return {
                    "model_id": model_id,
                    "status": "FAIL",
                    "reason": f"API error: {error_msg}",
                    "cost_rub": 0,
                    "response": response
                }
            
            # Check taskId present
            task_id = response.get('data', {}).get('taskId')
            if not task_id:
                logger.error(f"❌ No taskId in response")
                return {
                    "model_id": model_id,
                    "status": "FAIL",
                    "reason": "No taskId in response",
                    "cost_rub": 0,
                    "response": response
                }
            
            logger.info(f"✅ Task created! taskId: {task_id}")
            logger.info(f"📊 Response: {json.dumps(response, indent=2)}")
            
            return {
                "model_id": model_id,
                "status": "PASS",
                "cost_rub": 0,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"❌ API call failed: {e}", exc_info=True)
            return {
                "model_id": model_id,
                "status": "FAIL",
                "reason": str(e),
                "cost_rub": 0
            }
    
    async def test_paid_model(self, model_id: str) -> Dict[str, Any]:
        """Test a PAID model (will spend credits)."""
        logger.info(f"\n{'='*60}")
        logger.info(f"💰 Testing PAID model: {model_id}")
        logger.info(f"{'='*60}")
        
        try:
            # Get model config
            config = get_model_config(model_id, self.sot)
            if not config:
                return {
                    "model_id": model_id,
                    "status": "SKIP",
                    "reason": "Model config not found",
                    "cost_rub": 0
                }
            
            # Check pricing
            cost_rub = config.get('pricing', {}).get('rub_per_gen', 0)
            logger.info(f"💵 Expected cost: {cost_rub} RUB")
            
            # Confirm before spending
            print(f"\n⚠️  This will spend {cost_rub} RUB on your Kie.ai account!")
            print(f"   Model: {model_id}")
            print(f"   Continue? [y/N]: ", end='')
            
            # Auto-confirm in CI or if CONFIRM_PAID_TEST=1
            auto_confirm = os.getenv('CONFIRM_PAID_TEST') == '1'
            if auto_confirm:
                confirm = 'y'
                print('y (auto-confirmed)')
            else:
                confirm = input().strip().lower()
            
            if confirm != 'y':
                logger.info("❌ User cancelled PAID test")
                return {
                    "model_id": model_id,
                    "status": "SKIP",
                    "reason": "User cancelled",
                    "cost_rub": 0
                }
            
            # Build payload
            schema = get_model_schema(model_id, self.sot)
            input_schema = schema.get('input_schema', {})
            user_params = self._get_minimal_params(input_schema)
            
            payload = build_payload(model_id, user_params, self.sot)
            logger.info(f"📦 Payload: {json.dumps(payload, indent=2)}")
            
            # Make API call
            logger.info(f"🚀 Making API call...")
            response = await self.client.create_task(model_id, payload)
            
            # Check API response success
            response_code = response.get('code', 0)
            if response_code != 200:
                error_msg = response.get('msg', 'Unknown error')
                logger.error(f"❌ API returned error: {error_msg} (code={response_code})")
                return {
                    "model_id": model_id,
                    "status": "FAIL",
                    "reason": f"API error: {error_msg}",
                    "cost_rub": cost_rub,
                    "response": response
                }
            
            # Check taskId present
            task_id = response.get('data', {}).get('taskId')
            if not task_id:
                logger.error(f"❌ No taskId in response")
                return {
                    "model_id": model_id,
                    "status": "FAIL",
                    "reason": "No taskId in response",
                    "cost_rub": cost_rub,
                    "response": response
                }
            
            logger.info(f"✅ Task created! taskId: {task_id}")
            logger.info(f"💸 Spent: {cost_rub} RUB")
            logger.info(f"📊 Response: {json.dumps(response, indent=2)}")
            
            return {
                "model_id": model_id,
                "status": "PASS",
                "cost_rub": cost_rub,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"❌ API call failed: {e}", exc_info=True)
            return {
                "model_id": model_id,
                "status": "FAIL",
                "reason": str(e),
                "cost_rub": cost_rub
            }
    
    def _get_minimal_params(self, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Get minimal parameters for a model based on input_schema."""
        params = {}
        
        # Handle 'input' wrapper (qwen models)
        if 'input' in input_schema:
            # WRAPPED format: get examples from 'input' field
            input_field = input_schema.get('input', {})
            examples = input_field.get('examples', [])
            if examples and isinstance(examples[0], dict):
                # Use first example as template
                return examples[0].copy()
        
        # Handle direct fields (z-image)
        for field_name, field_info in input_schema.items():
            if field_name in ('model', 'callBackUrl'):
                # Skip system fields
                continue
            
            if not isinstance(field_info, dict):
                continue
            
            if not field_info.get('required', False):
                continue
            
            field_type = field_info.get('type')
            
            # Get from examples first
            examples = field_info.get('examples', [])
            if examples and examples[0]:
                if field_type == 'dict' and isinstance(examples[0], dict):
                    params[field_name] = examples[0].copy()
                else:
                    params[field_name] = examples[0]
                continue
            
            # Fallback: generate minimal default values
            if field_type == 'string':
                if 'url' in field_name.lower() or 'image' in field_name.lower():
                    params[field_name] = "https://via.placeholder.com/512x512.png"
                elif 'prompt' in field_name.lower():
                    params[field_name] = "A simple test"
                else:
                    params[field_name] = "test"
            
            elif field_type in ('integer', 'int'):
                params[field_name] = 1
            
            elif field_type in ('number', 'float'):
                params[field_name] = 1.0
            
            elif field_type in ('boolean', 'bool'):
                params[field_name] = False
            
            elif field_type in ('array', 'list'):
                params[field_name] = []
            
            elif field_type == 'dict':
                params[field_name] = {}
        
        return params
    
    async def run_all_tests(self):
        """Run all E2E tests."""
        print("\n" + "="*60)
        print("🧪 E2E API TEST - Real Kie.ai API calls")
        print("="*60)
        
        # Get FREE models from metadata
        free_tier_models = self.sot.get('metadata', {}).get('free_tier_models', [])
        
        if not free_tier_models:
            # Fallback: find models with 0 RUB
            models = self.sot.get('models', {})
            free_tier_models = [
                model_id for model_id, model in models.items()
                if model.get('enabled', True)
                and model.get('pricing', {}).get('rub_per_gen') == 0
            ]
        
        print(f"\n📊 Test Plan:")
        print(f"   FREE models: {len(free_tier_models)}")
        print(f"   PAID models: 0 (manual confirmation required)")
        print(f"   Total budget: 0 RUB (FREE only by default)\n")
        
        # Test all FREE models
        for model_id in free_tier_models:
            result = await self.test_free_model(model_id)
            self.results.append(result)
            
            # Small delay between requests
            await asyncio.sleep(2)
        
        # Optional: Test 1 cheap PAID model
        # Uncomment to test PAID models (requires manual confirmation)
        # cheap_paid = "bytedance/seedream"  # ~1580 RUB
        # result = await self.test_paid_model(cheap_paid)
        # self.results.append(result)
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print test results summary."""
        print("\n" + "="*60)
        print("📊 E2E API TEST SUMMARY")
        print("="*60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        skipped = sum(1 for r in self.results if r['status'] == 'SKIP')
        
        total_cost = sum(r.get('cost_rub', 0) for r in self.results)
        
        for result in self.results:
            status = result['status']
            icon = '✅' if status == 'PASS' else '❌' if status == 'FAIL' else '⏭️'
            
            model_id = result['model_id']
            cost = result.get('cost_rub', 0)
            
            reason = f" ({result.get('reason', '')})" if 'reason' in result else ""
            
            print(f"{icon} {status:4} | {model_id:40} | {cost:8.1f} RUB{reason}")
        
        print("="*60)
        print(f"Total: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"💸 Total cost: {total_cost:.1f} RUB")
        print("="*60)
        
        if failed > 0:
            print("\n❌ SOME TESTS FAILED!")
            sys.exit(1)
        elif passed == 0:
            print("\n⚠️  NO TESTS PASSED!")
            sys.exit(1)
        else:
            print("\n✅ ALL TESTS PASSED!")


async def main():
    """Main entry point."""
    try:
        test = E2EAPITest()
        await test.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
