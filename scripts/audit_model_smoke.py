#!/usr/bin/env python3
"""
Model Smoke Test - проверяет что каждая модель может сгенерировать payload.

Для каждой AI модели:
1. Загружает input_schema
2. Генерирует минимально-валидный payload
3. Валидирует через существующую логику
4. Проверяет что нет exceptions

Не делает реальных API вызовов - только DRY RUN.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_registry() -> Dict[str, Any]:
    """Load source of truth registry."""
    registry_path = Path("models/kie_models_source_of_truth.json")
    with open(registry_path, 'r') as f:
        return json.load(f)


def get_ai_models(registry: Dict) -> List[Dict]:
    """Get only real AI models (not processors/docs)."""
    return [
        m for m in registry['models']
        if '/' in m['model_id']  # Real AI models have vendor/model format
    ]


def generate_minimal_payload(model: Dict) -> Tuple[bool, Dict[str, Any], str]:
    """
    Generate minimal valid payload for model.
    
    Returns:
        (success, payload, error_message)
    """
    model_id = model['model_id']
    schema = model.get('input_schema', {})
    
    if not schema:
        return False, {}, f"No input_schema"
    
    if not isinstance(schema, dict):
        return False, {}, f"Invalid schema type: {type(schema).__name__}"
    
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    
    if not properties:
        return False, {}, "No properties in schema"
    
    # Generate minimal payload with required fields
    payload = {}
    
    for field in required:
        if field not in properties:
            return False, {}, f"Required field '{field}' not in properties"
        
        prop = properties[field]
        prop_type = prop.get('type', 'string')
        
        # Generate minimal value based on type
        if prop_type == 'string':
            # Check for enum
            if 'enum' in prop:
                payload[field] = prop['enum'][0]
            else:
                payload[field] = "test"
        elif prop_type == 'integer':
            # Use minimum or default
            payload[field] = prop.get('minimum', prop.get('default', 1))
        elif prop_type == 'number':
            payload[field] = prop.get('minimum', prop.get('default', 1.0))
        elif prop_type == 'boolean':
            payload[field] = prop.get('default', True)
        elif prop_type == 'array':
            payload[field] = []
        elif prop_type == 'object':
            payload[field] = {}
        else:
            payload[field] = None
    
    return True, payload, ""


def validate_payload(model: Dict, payload: Dict) -> Tuple[bool, str]:
    """
    Validate payload against schema.
    
    Returns:
        (valid, error_message)
    """
    schema = model.get('input_schema', {})
    required = schema.get('required', [])
    properties = schema.get('properties', {})
    
    # Check all required fields present
    for field in required:
        if field not in payload:
            return False, f"Missing required field: {field}"
    
    # Check types (basic validation)
    for field, value in payload.items():
        if field not in properties:
            continue  # Allow extra fields
        
        prop = properties[field]
        expected_type = prop.get('type')
        
        if expected_type == 'string' and not isinstance(value, str):
            return False, f"Field '{field}' should be string, got {type(value).__name__}"
        elif expected_type == 'integer' and not isinstance(value, int):
            return False, f"Field '{field}' should be integer, got {type(value).__name__}"
        elif expected_type == 'number' and not isinstance(value, (int, float)):
            return False, f"Field '{field}' should be number, got {type(value).__name__}"
        elif expected_type == 'boolean' and not isinstance(value, bool):
            return False, f"Field '{field}' should be boolean, got {type(value).__name__}"
    
    return True, ""


def smoke_test_model(model: Dict) -> Dict[str, Any]:
    """
    Smoke test single model.
    
    Returns:
        Test result dict
    """
    model_id = model['model_id']
    category = model.get('category', 'unknown')
    
    # Step 1: Generate payload
    success, payload, error = generate_minimal_payload(model)
    
    if not success:
        return {
            'model_id': model_id,
            'category': category,
            'status': 'FAIL',
            'stage': 'generate_payload',
            'error': error,
            'required_fields': model.get('input_schema', {}).get('required', [])
        }
    
    # Step 2: Validate payload
    valid, error = validate_payload(model, payload)
    
    if not valid:
        return {
            'model_id': model_id,
            'category': category,
            'status': 'FAIL',
            'stage': 'validate_payload',
            'error': error,
            'required_fields': model.get('input_schema', {}).get('required', []),
            'generated_payload': payload
        }
    
    # Success
    return {
        'model_id': model_id,
        'category': category,
        'status': 'OK',
        'stage': 'complete',
        'error': '',
        'required_fields': model.get('input_schema', {}).get('required', []),
        'generated_payload': payload
    }


def run_smoke_tests():
    """Run smoke tests for all models."""
    print("=" * 70)
    print("MODEL SMOKE TEST - PAYLOAD GENERATION")
    print("=" * 70)
    print()
    
    # Load data
    registry = load_registry()
    ai_models = get_ai_models(registry)
    
    print(f"Testing {len(ai_models)} AI models...")
    print()
    
    # Run tests
    results = []
    for model in ai_models:
        result = smoke_test_model(model)
        results.append(result)
        
        # Print progress
        status_icon = "✅" if result['status'] == 'OK' else "❌"
        print(f"{status_icon} {result['model_id']:<50} {result['status']}")
    
    # Summary
    passed = [r for r in results if r['status'] == 'OK']
    failed = [r for r in results if r['status'] == 'FAIL']
    
    print()
    print("=" * 70)
    print(f"📊 SUMMARY:")
    print(f"  Total:   {len(results)}")
    print(f"  Passed:  {len(passed)}")
    print(f"  Failed:  {len(failed)}")
    print(f"  Success: {100*len(passed)/len(results):.1f}%")
    print("=" * 70)
    print()
    
    # Show failures
    if failed:
        print(f"❌ FAILED MODELS ({len(failed)}):")
        print()
        for result in failed:
            print(f"  {result['model_id']}:")
            print(f"    Stage:  {result['stage']}")
            print(f"    Error:  {result['error']}")
            print(f"    Fields: {result['required_fields']}")
            print()
    
    # Generate CSV
    Path('artifacts').mkdir(exist_ok=True)
    
    with open('artifacts/model_smoke_matrix.csv', 'w') as f:
        f.write("model_id,category,status,stage,error,required_fields\n")
        for r in results:
            fields = "|".join(r['required_fields'])
            error = r['error'].replace(',', ';').replace('\n', ' ')
            f.write(f"{r['model_id']},{r['category']},{r['status']},{r['stage']},{error},{fields}\n")
    
    # Generate JSON
    with open('artifacts/model_smoke_results.json', 'w') as f:
        json.dump({
            'summary': {
                'total': len(results),
                'passed': len(passed),
                'failed': len(failed),
                'success_rate': round(100 * len(passed) / len(results), 2)
            },
            'results': results
        }, f, indent=2)
    
    print("📁 ARTIFACTS:")
    print("  - artifacts/model_smoke_matrix.csv")
    print("  - artifacts/model_smoke_results.json")
    print()
    
    # Exit code
    if failed:
        print("❌ SMOKE TEST: FAILED")
        return 1
    else:
        print("✅ SMOKE TEST: PASSED")
        return 0


if __name__ == '__main__':
    sys.exit(run_smoke_tests())
