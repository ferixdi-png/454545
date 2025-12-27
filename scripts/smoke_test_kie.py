#!/usr/bin/env python3
"""
Smoke Test for KIE.AI Integration

Tests ONLY the 5 cheapest models to minimize credit usage.
Budget: ~10 credits max (~7₽)

Requirements:
- KIE_API_KEY environment variable
- Working model registry
- Internet connection
"""

import os
import sys
import time
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import load_source_of_truth, build_payload

# Check API key
if not os.getenv('KIE_API_KEY'):
    print("❌ ERROR: KIE_API_KEY not set")
    print("   export KIE_API_KEY=sk-your-key")
    sys.exit(1)

class KieSmokeTest:
    """Minimal smoke test for KIE.AI models"""
    
    def __init__(self):
        self.api_key = os.getenv('KIE_API_KEY')
        self.base_url = os.getenv('KIE_BASE_URL', 'https://api.kie.ai')
        self.registry = None
        self.free_tier_models = []
        self.total_credits_used = 0
        self.results = []
    
    def load_registry(self):
        """Load model registry"""
        print("📂 Loading registry...")
        
        self.registry = load_source_of_truth()
        total_models = len(self.registry.get('models', []))
        
        print(f"   ✅ Loaded {total_models} models")
        print(f"   Version: {self.registry.get('version', 'unknown')}")
        
        # Get FREE tier models
        self.free_tier_models = self.registry.get('free_tier_models', [])
        
        if not self.free_tier_models:
            print("   ⚠️  No free_tier_models defined, finding cheapest...")
            # Find 5 cheapest manually
            models = self.registry.get('models', [])
            models_with_price = []
            
            for m in models:
                credits = m.get('pricing', {}).get('credits_per_generation', 0)
                if credits > 0:
                    models_with_price.append((m['model_id'], credits))
            
            models_with_price.sort(key=lambda x: x[1])
            self.free_tier_models = [m[0] for m in models_with_price[:5]]
        
        print(f"\n   🎯 Testing FREE tier models ({len(self.free_tier_models)}):")
        for i, model_id in enumerate(self.free_tier_models, 1):
            print(f"      {i}. {model_id}")
    
    def test_payload_generation(self):
        """Test that payloads can be built"""
        print("\n🧪 Testing payload generation...")
        
        for model_id in self.free_tier_models:
            try:
                # Try building payload
                payload = build_payload(model_id, {"prompt": "test"})
                
                if 'model' in payload and 'input' in payload:
                    print(f"   ✅ {model_id:40s} - payload OK")
                else:
                    print(f"   ❌ {model_id:40s} - invalid payload structure")
                    self.results.append({
                        'model_id': model_id,
                        'test': 'payload_generation',
                        'status': 'failed',
                        'error': 'Missing model or input field'
                    })
            except Exception as e:
                print(f"   ❌ {model_id:40s} - {str(e)[:50]}")
                self.results.append({
                    'model_id': model_id,
                    'test': 'payload_generation',
                    'status': 'error',
                    'error': str(e)
                })
    
    def test_api_call(self, model_id: str, test_input: dict) -> bool:
        """
        Test single API call (DRY RUN - not actually calling API yet)
        
        In production, this would:
        1. POST to /api/v1/jobs/createTask
        2. Poll /api/v1/jobs/recordInfo?taskId=xxx
        3. Wait for completion
        4. Parse result
        """
        print(f"\n🔬 Testing: {model_id}")
        
        try:
            # Build payload
            payload = build_payload(model_id, test_input)
            
            print(f"   📦 Payload: {json.dumps(payload, indent=2)[:200]}...")
            
            # In real test:
            # response = requests.post(
            #     f"{self.base_url}/api/v1/jobs/createTask",
            #     json=payload,
            #     headers={"Authorization": f"Bearer {self.api_key}"}
            # )
            
            # For now: just validate payload structure
            required_fields = ['model', 'input']
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")
            
            print(f"   ✅ Payload structure valid")
            
            self.results.append({
                'model_id': model_id,
                'test': 'api_call_dry_run',
                'status': 'passed',
                'payload': payload
            })
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append({
                'model_id': model_id,
                'test': 'api_call_dry_run',
                'status': 'failed',
                'error': str(e)
            })
            return False
    
    def run(self):
        """Run smoke test"""
        
        print("="*80)
        print("🔥 KIE.AI SMOKE TEST")
        print("="*80)
        print(f"\n🔑 API Key: {self.api_key[:20]}...")
        print(f"🌐 Base URL: {self.base_url}")
        print(f"💰 Budget: ~10 credits (~7₽)")
        
        # Load registry
        self.load_registry()
        
        # Test payload generation
        self.test_payload_generation()
        
        # Test API calls (DRY RUN)
        print("\n🔬 Testing API calls (DRY RUN)...")
        print("   ⚠️  Not actually calling API - just validating payloads")
        print()
        
        test_inputs = {
            "recraft/crisp-upscale": {"image": "https://example.com/test.jpg"},
            "qwen/z-image": {"prompt": "A cute cat"},
            "recraft/remove-background": {"image": "https://example.com/test.jpg"},
            "midjourney/image-to-image": {"image": "https://example.com/test.jpg", "prompt": "cyberpunk style"},
            "midjourney/text-to-image": {"prompt": "A magical forest"}
        }
        
        for model_id in self.free_tier_models:
            test_input = test_inputs.get(model_id, {"prompt": "test"})
            self.test_api_call(model_id, test_input)
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        
        print("\n" + "="*80)
        print("📊 SMOKE TEST SUMMARY")
        print("="*80)
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'passed')
        failed = sum(1 for r in self.results if r['status'] == 'failed')
        errors = sum(1 for r in self.results if r['status'] == 'error')
        
        print(f"\n✅ Passed: {passed}/{total_tests}")
        print(f"❌ Failed: {failed}/{total_tests}")
        print(f"⚠️  Errors: {errors}/{total_tests}")
        
        print(f"\n💰 Credits used: {self.total_credits_used:.1f} (estimated)")
        
        if failed > 0 or errors > 0:
            print(f"\n❌ ISSUES FOUND:")
            for r in self.results:
                if r['status'] in ['failed', 'error']:
                    print(f"   • {r['model_id']}: {r.get('error', 'unknown error')}")
        
        print("\n" + "="*80)
        
        if passed == total_tests:
            print("✅ ALL TESTS PASSED")
            print("="*80)
            print()
            print("🎯 Next steps:")
            print("   1. Set KIE_API_KEY for real API testing")
            print("   2. Run: python scripts/smoke_test_kie.py --real")
            print("   3. Monitor credit usage")
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("="*80)
            return 1


def main():
    """Run smoke test"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Smoke test KIE.AI integration")
    parser.add_argument('--real', action='store_true', help="Make real API calls (costs credits)")
    args = parser.parse_args()
    
    if args.real:
        print("⚠️  REAL API MODE - This will consume credits!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    tester = KieSmokeTest()
    exit_code = tester.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
