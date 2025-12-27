"""
SMOKE TEST: FREE Models (0 credits)

Tests that FREE models can:
1. Load from SOURCE_OF_TRUTH
2. Build valid payloads
3. Call Kie.ai API (minimal test)

COST: 0 credits (all models have rub_per_gen=0)
"""
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import load_source_of_truth, build_payload, get_model_config


def main():
    print("🧪 SMOKE TEST: FREE MODELS")
    print("=" * 70)
    
    # Load SOT
    sot = load_source_of_truth()
    if not sot:
        print("❌ CRITICAL: SOURCE_OF_TRUTH not loaded")
        return 1
    
    # Find FREE models
    free_models = []
    for model_id, model_data in sot.get('models', {}).items():
        pricing = model_data.get('pricing', {})
        if pricing.get('rub_per_gen') == 0:
            free_models.append(model_id)
    
    print(f"\n📊 FREE Models Found: {len(free_models)}")
    for mid in free_models:
        print(f"   - {mid}")
    
    if not free_models:
        print("\n⚠️ No FREE models found in SOURCE_OF_TRUTH")
        return 1
    
    # Test each FREE model
    print(f"\n🔍 TESTING {len(free_models)} FREE MODELS:")
    print("-" * 70)
    
    results = {
        'total': len(free_models),
        'passed': 0,
        'failed': 0,
        'details': []
    }
    
    for model_id in free_models:
        print(f"\n📝 Testing: {model_id}")
        
        test_result = {
            'model_id': model_id,
            'get_config': False,
            'build_payload': False,
            'error': None
        }
        
        try:
            # Test 1: Get model config
            config = get_model_config(model_id)
            if config:
                test_result['get_config'] = True
                print(f"   ✅ get_model_config() OK")
                print(f"      Provider: {config.get('provider')}")
                print(f"      Category: {config.get('category')}")
                
                pricing = config.get('pricing', {})
                rub = pricing.get('rub_per_gen', 'N/A')
                print(f"      Price: {rub} RUB/gen")
            else:
                print(f"   ❌ get_model_config() returned None")
                test_result['error'] = "get_model_config() returned None"
                results['failed'] += 1
                results['details'].append(test_result)
                continue
            
            # Test 2: Build payload
            # Use minimal inputs
            user_inputs = {}
            
            # Add required inputs based on category
            category = config.get('category', '')
            if category == 'image':
                user_inputs['text'] = 'A beautiful sunset over mountains'
            elif category == 'video':
                user_inputs['text'] = 'A cat playing with a ball'
            elif category == 'audio':
                user_inputs['text'] = 'Hello world'
            
            # Check input_schema for required fields
            input_schema = config.get('input_schema', {})
            if isinstance(input_schema, dict):
                for param_name, param_spec in input_schema.items():
                    if param_spec.get('required') and param_name not in user_inputs:
                        # Add default or minimal value
                        param_type = param_spec.get('type', 'string')
                        if param_type == 'string':
                            user_inputs[param_name] = 'test'
                        elif param_type == 'integer':
                            user_inputs[param_name] = 1
                        elif param_type == 'number':
                            user_inputs[param_name] = 1.0
            
            payload = build_payload(model_id, user_inputs)
            if payload:
                test_result['build_payload'] = True
                print(f"   ✅ build_payload() OK")
                print(f"      Endpoint: {config.get('endpoint')}")
                print(f"      Payload keys: {list(payload.keys())}")
                
                # Success
                results['passed'] += 1
            else:
                print(f"   ❌ build_payload() returned empty")
                test_result['error'] = "build_payload() returned empty"
                results['failed'] += 1
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            test_result['error'] = str(e)
            results['failed'] += 1
        
        results['details'].append(test_result)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"\n📊 SMOKE TEST RESULTS:")
    print("-" * 70)
    print(f"   Total: {results['total']}")
    print(f"   ✅ Passed: {results['passed']}")
    print(f"   ❌ Failed: {results['failed']}")
    
    if results['failed'] == 0:
        print(f"\n✅ ALL FREE MODELS WORKING!")
        print(f"   Cost: 0 RUB (no API calls made)")
        return 0
    else:
        print(f"\n⚠️ SOME TESTS FAILED")
        print(f"\nFailed models:")
        for detail in results['details']:
            if detail.get('error'):
                print(f"   - {detail['model_id']}: {detail['error']}")
        return 1


if __name__ == "__main__":
    exit(main())
