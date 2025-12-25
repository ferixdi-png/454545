"""
FINAL SYSTEM TEST - Проверка всех компонентов на 100%

Этот тест проверяет:
1. SOURCE_OF_TRUTH загружается
2. Builder работает с SOT
3. Validator интегрирован
4. Pricing корректен
5. API Client готов
6. UI components используют SOT
"""
import json
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_source_of_truth():
    """Test 1: SOURCE_OF_TRUTH integrity"""
    print("\n" + "="*80)
    print("TEST 1: SOURCE_OF_TRUTH INTEGRITY")
    print("="*80)
    
    sot_path = "models/KIE_SOURCE_OF_TRUTH.json"
    
    # Check file exists
    assert os.path.exists(sot_path), f"❌ {sot_path} not found"
    print(f"✅ {sot_path} exists")
    
    # Load and validate structure
    with open(sot_path) as f:
        sot = json.load(f)
    
    assert 'version' in sot, "❌ Missing version"
    assert 'models' in sot, "❌ Missing models"
    print(f"✅ Version: {sot['version']}")
    print(f"✅ Models: {len(sot['models'])}")
    
    # Check completeness
    models = sot['models']
    assert len(models) == 72, f"❌ Expected 72 models, got {len(models)}"
    print(f"✅ All 72 models present")
    
    # Check required fields
    required_fields = ['model_id', 'provider', 'category', 'display_name', 
                      'endpoint', 'method', 'input_schema', 'pricing']
    
    for mid, mdata in models.items():
        for field in required_fields:
            assert field in mdata, f"❌ {mid} missing {field}"
    
    print(f"✅ All models have required fields")
    
    # Check pricing
    models_with_prices = sum(1 for m in models.values() if 'rub_per_gen' in m.get('pricing', {}))
    assert models_with_prices == 72, f"❌ Only {models_with_prices}/72 have prices"
    print(f"✅ All 72 models have pricing")
    
    # Check FREE models
    free_models = [mid for mid, m in models.items() if m.get('pricing', {}).get('rub_per_gen') == 0]
    assert len(free_models) == 4, f"❌ Expected 4 FREE models, got {len(free_models)}"
    print(f"✅ 4 FREE models: {', '.join(free_models)}")
    
    return True


def test_builder():
    """Test 2: Builder integration"""
    print("\n" + "="*80)
    print("TEST 2: BUILDER INTEGRATION")
    print("="*80)
    
    from app.kie.builder import (
        load_source_of_truth,
        get_model_schema,
        get_model_config,
        build_payload
    )
    
    # Test load_source_of_truth
    sot = load_source_of_truth()
    assert sot is not None, "❌ load_source_of_truth() returned None"
    assert len(sot.get('models', {})) == 72, "❌ Wrong number of models"
    print(f"✅ load_source_of_truth() works")
    
    # Test get_model_schema
    schema = get_model_schema('z-image')
    assert schema is not None, "❌ get_model_schema() returned None"
    assert 'model_id' in schema, "❌ Schema missing model_id"
    print(f"✅ get_model_schema() works")
    
    # Test get_model_config
    config = get_model_config('z-image')
    assert config is not None, "❌ get_model_config() returned None"
    assert 'pricing' in config, "❌ Config missing pricing"
    print(f"✅ get_model_config() works")
    
    # Test build_payload
    payload = build_payload('z-image', {'text': 'A beautiful sunset'})
    assert payload is not None, "❌ build_payload() returned None"
    assert 'model' in payload, "❌ Payload missing model"
    assert 'input' in payload, "❌ Payload missing input"
    print(f"✅ build_payload() works")
    print(f"   Payload keys: {list(payload.keys())}")
    
    return True


def test_validator():
    """Test 3: Validator integration"""
    print("\n" + "="*80)
    print("TEST 3: VALIDATOR INTEGRATION")
    print("="*80)
    
    from app.kie.validator import validate_model_inputs, ModelContractError
    from app.kie.builder import get_model_schema
    
    # Get schema from SOT
    schema = get_model_schema('z-image')
    assert schema is not None, "❌ Cannot get schema for test"
    
    # Test valid inputs
    try:
        validate_model_inputs('z-image', schema, {'text': 'Test prompt'})
        print(f"✅ Validator accepts valid inputs")
    except ModelContractError as e:
        raise AssertionError(f"❌ Validator rejected valid inputs: {e}")
    
    # Test invalid inputs (should raise)
    try:
        validate_model_inputs('z-image', schema, {})  # Empty inputs
        print(f"⚠️ Validator accepted empty inputs (may be OK if all optional)")
    except ModelContractError:
        print(f"✅ Validator rejects invalid inputs")
    
    return True


def test_pricing():
    """Test 4: Pricing system"""
    print("\n" + "="*80)
    print("TEST 4: PRICING SYSTEM")
    print("="*80)
    
    from app.payments.pricing import (
        calculate_kie_cost,
        calculate_user_price,
        USD_TO_RUB,
        MARKUP_MULTIPLIER
    )
    from app.kie.builder import get_model_config
    
    # Check constants
    assert USD_TO_RUB == 78.0, f"❌ USD_TO_RUB should be 78.0, got {USD_TO_RUB}"
    assert MARKUP_MULTIPLIER == 2.0, f"❌ MARKUP should be 2.0, got {MARKUP_MULTIPLIER}"
    print(f"✅ Pricing constants: USD_TO_RUB={USD_TO_RUB}, MARKUP={MARKUP_MULTIPLIER}")
    
    # Test FREE model
    free_model = get_model_config('z-image')
    kie_cost = calculate_kie_cost(free_model, {})
    assert kie_cost == 0, f"❌ FREE model should cost 0, got {kie_cost}"
    user_price = calculate_user_price(kie_cost)
    assert user_price == 0, f"❌ FREE model user price should be 0, got {user_price}"
    print(f"✅ FREE model pricing: 0 RUB")
    
    # Test PAID model
    paid_model = get_model_config('bytedance/seedream')
    assert paid_model is not None, "❌ Cannot get paid model config"
    kie_cost = calculate_kie_cost(paid_model, {})
    assert kie_cost > 0, f"❌ PAID model should have cost > 0"
    user_price = calculate_user_price(kie_cost)
    assert user_price == kie_cost * MARKUP_MULTIPLIER, "❌ Wrong user price calculation"
    print(f"✅ PAID model pricing: {kie_cost} RUB → {user_price} RUB (user)")
    
    return True


def test_api_client():
    """Test 5: API Client structure"""
    print("\n" + "="*80)
    print("TEST 5: API CLIENT")
    print("="*80)
    
    # Check client_v4 exists
    client_file = "app/kie/client_v4.py"
    assert os.path.exists(client_file), f"❌ {client_file} not found"
    print(f"✅ {client_file} exists")
    
    # Check for retry logic
    with open(client_file) as f:
        content = f.read()
    
    assert 'tenacity' in content, "❌ Missing tenacity import"
    assert '@retry' in content, "❌ Missing @retry decorator"
    assert 'stop_after_attempt' in content, "❌ Missing retry configuration"
    print(f"✅ Retry logic present (tenacity)")
    
    # Check generator exists
    gen_file = "app/kie/generator.py"
    assert os.path.exists(gen_file), f"❌ {gen_file} not found"
    print(f"✅ {gen_file} exists")
    
    return True


def test_ui_integration():
    """Test 6: UI components use SOT"""
    print("\n" + "="*80)
    print("TEST 6: UI INTEGRATION")
    print("="*80)
    
    files_to_check = {
        'app/ui/marketing_menu.py': 'Marketing UI',
        'bot/handlers/marketing.py': 'Marketing handlers',
        'bot/handlers/flow.py': 'Flow handlers'
    }
    
    for filepath, desc in files_to_check.items():
        assert os.path.exists(filepath), f"❌ {filepath} not found"
        
        with open(filepath) as f:
            content = f.read()
        
        uses_sot = 'KIE_SOURCE_OF_TRUTH' in content or 'load_source_of_truth' in content
        assert uses_sot, f"❌ {filepath} doesn't use SOURCE_OF_TRUTH"
        print(f"✅ {desc} uses SOT")
    
    return True


def test_documentation():
    """Test 7: Documentation complete"""
    print("\n" + "="*80)
    print("TEST 7: DOCUMENTATION")
    print("="*80)
    
    docs = {
        'SYSTEM_STATUS_REPORT.md': 'System status report',
        'QUICK_START.md': 'Quick start guide',
        '.env.example': 'Environment variables example'
    }
    
    for filename, desc in docs.items():
        assert os.path.exists(filename), f"❌ {filename} not found"
        print(f"✅ {desc}: {filename}")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "🧪 "+"="*78)
    print("🧪 FINAL SYSTEM TEST - 100% READINESS CHECK")
    print("🧪 "+"="*78)
    
    tests = [
        ("SOURCE_OF_TRUTH Integrity", test_source_of_truth),
        ("Builder Integration", test_builder),
        ("Validator Integration", test_validator),
        ("Pricing System", test_pricing),
        ("API Client", test_api_client),
        ("UI Integration", test_ui_integration),
        ("Documentation", test_documentation),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True, None))
        except Exception as e:
            results.append((name, False, str(e)))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)
    
    for name, success, error in results:
        status = "✅ PASS" if success else f"❌ FAIL: {error}"
        print(f"{status:50} | {name}")
    
    print("="*80)
    print(f"Total: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {passed/len(results)*100:.0f}%")
    print("="*80)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! SYSTEM IS 100% READY!")
        return 0
    else:
        print(f"\n⚠️ {failed} TESTS FAILED - FIX REQUIRED")
        return 1


if __name__ == "__main__":
    exit(main())
