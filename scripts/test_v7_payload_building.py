#!/usr/bin/env python3
"""
🧪 DRY-RUN ТЕСТЫ V7 PAYLOAD BUILDING

Проверяет что builder.py правильно строит payloads для v7 моделей
БЕЗ реальных API запросов (dry-run).

Цель:
- Убедиться что v7 payloads строятся корректно
- Проверить все 6 моделей из v7 registry
- Валидировать структуру без трат кредитов
"""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import load_source_of_truth, build_payload, get_model_schema


def test_v7_payload_building():
    """Тестирует payload building для всех v7 моделей"""
    
    print("=" * 80)
    print("🧪 DRY-RUN: TESTING V7 PAYLOAD BUILDING")
    print("=" * 80)
    print()
    
    # Load v7 registry
    registry = load_source_of_truth()
    
    if registry.get("version") != "7.0.0-DOCS-SOURCE-OF-TRUTH":
        print(f"⚠️  WARNING: Not using v7 registry (version: {registry.get('version')})")
        print()
    
    models = registry.get("models", {})
    
    if isinstance(models, list):
        print("❌ ERROR: Registry has old list format, expecting v7 dict format")
        return False
    
    print(f"📊 Testing {len(models)} models from v7 registry\n")
    
    # Test cases for each model (using CORRECT tech IDs)
    test_cases = {
        "veo3_fast": {
            "prompt": "A beautiful sunset over mountains",
        },
        "veo3": {
            "prompt": "A cat playing with yarn",
        },
        "runway_gen3_alpha": {
            "prompt": "Abstract art animation",
        },
        "V3_5": {  # Suno tech ID
            "prompt": "Upbeat electronic music",
        },
        "gpt-4o-image": {  # GPT-4o tech ID
            "prompt": "A futuristic cityscape",
        },
        "flux-kontext-pro": {  # Flux tech ID
            "prompt": "Portrait of a robot",
        },
        "flux-kontext-max": {  # Flux Max (new!)
            "prompt": "Complex architectural interior with intricate details",
            "promptUpsampling": True
        }
    }
    
    passed = 0
    failed = 0
    
    for model_id, user_inputs in test_cases.items():
        print(f"🧪 Testing: {model_id}")
        
        # Get model schema
        schema = get_model_schema(model_id, registry)
        
        if not schema:
            print(f"   ❌ FAIL: Model not found in registry")
            failed += 1
            continue
        
        print(f"   Name: {schema.get('display_name')}")
        print(f"   Endpoint: {schema.get('endpoint')}")
        
        # Try to build payload
        try:
            payload = build_payload(model_id, user_inputs, registry)
            
            print(f"   ✅ PASS: Payload built successfully")
            print(f"   Payload: {json.dumps(payload, indent=2)[:200]}...")
            
            # Validate payload structure
            if 'prompt' in payload:
                print(f"   ✓ Has 'prompt' field")
            
            # Check that it doesn't have old 'input' wrapper for v7
            if 'input' in payload and isinstance(payload['input'], dict):
                print(f"   ⚠️  WARNING: Payload has 'input' wrapper (might be old format)")
            
            passed += 1
            
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            failed += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {len(test_cases)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print()
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print("❌ SOME TESTS FAILED - need fixes")
        return False


def main():
    """Main execution"""
    success = test_v7_payload_building()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
