#!/usr/bin/env python3
"""
Dry-run payload validation - test payload building WITHOUT real API calls.

Uses actual app code to build payloads from input_schema.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any

def generate_test_input(input_schema: Dict[str, Any], ui_prompts: list = None) -> Dict[str, Any]:
    """Generate test input data based on schema."""
    properties = input_schema.get('properties', {})
    required = input_schema.get('required', [])
    test_input = {}
    
    for field_name, field_schema in properties.items():
        field_type = field_schema.get('type', 'string')
        
        # Use example from schema if available
        if 'default' in field_schema:
            test_input[field_name] = field_schema['default']
            continue
        
        # Generate by type
        if field_type == 'string':
            # Use ui_example_prompts if available for prompt fields
            if field_name in ['prompt', 'text', 'input'] and ui_prompts:
                test_input[field_name] = ui_prompts[0]
            else:
                test_input[field_name] = "test"
        elif field_type == 'number' or field_type == 'integer':
            test_input[field_name] = 1
        elif field_type == 'boolean':
            test_input[field_name] = False
        elif field_type == 'array':
            test_input[field_name] = ["test_item"]
        elif field_type == 'object':
            test_input[field_name] = {}
    
    return test_input

def validate_payloads():
    """Validate payload building for all models."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    
    if not sot_path.exists():
        print(f"❌ SOURCE_OF_TRUTH not found")
        return 1
    
    with open(sot_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models = data.get('models', {})
    
    results = {'ok': 0, 'warn': 0, 'error': 0}
    errors = []
    warnings = []
    
    for model_id, model in models.items():
        input_schema = model.get('input_schema', {})
        ui_prompts = model.get('ui_example_prompts', [])
        endpoint = model.get('endpoint', '')
        
        # Check if schema is empty
        if not input_schema or not input_schema.get('properties'):
            warnings.append(f"⚠️  {model_id}: empty input_schema")
            results['warn'] += 1
            continue
        
        try:
            # Generate test input
            test_input = generate_test_input(input_schema, ui_prompts)
            
            # Validate required fields are present
            required = input_schema.get('required', [])
            missing = [f for f in required if f not in test_input]
            if missing:
                errors.append(f"❌ {model_id}: cannot generate required fields: {missing}")
                results['error'] += 1
                continue
            
            # Build minimal payload (what V4 API expects)
            payload = {
                'model': model_id,
                **test_input
            }
            
            # Validate payload is dict and has model field
            if not isinstance(payload, dict):
                errors.append(f"❌ {model_id}: payload is not dict")
                results['error'] += 1
            elif 'model' not in payload:
                errors.append(f"❌ {model_id}: payload missing 'model' field")
                results['error'] += 1
            else:
                results['ok'] += 1
        
        except Exception as e:
            errors.append(f"❌ {model_id}: payload build failed: {e}")
            results['error'] += 1
    
    # Summary
    total = len(models)
    print("═" * 70)
    print("🧪 DRY-RUN PAYLOAD VALIDATION")
    print("═" * 70)
    print(f"📊 Total models: {total}")
    print(f"✅ OK: {results['ok']}")
    print(f"⚠️  WARNINGS: {results['warn']}")
    print(f"❌ ERRORS: {results['error']}")
    print()
    
    if errors:
        print("❌ ERRORS:")
        for err in errors[:10]:
            print(f"  {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print()
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warn in warnings[:10]:
            print(f"  {warn}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
        print()
    
    if results['error'] > 0:
        print("❌ Dry-run FAILED")
        print("═" * 70)
        return 1
    else:
        print("✅ Dry-run PASSED")
        print(f"   ({results['warn']} models with empty schemas)")
        print("═" * 70)
        return 0

if __name__ == "__main__":
    sys.exit(validate_payloads())
