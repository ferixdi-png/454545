"""
Comprehensive schema validation for ALL 77 models in registry.

Проверяет:
1. Input schema корректность (required/optional fields)
2. Pricing coverage (все модели имеют цены)
3. Payload builder работает для каждой модели
4. Категоризация моделей

NO API CALLS - только валидация данных.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload, get_model_schema


def load_registry() -> Dict[str, Any]:
    """Load registry."""
    path = Path("models/kie_models_final_truth.json")
    with open(path) as f:
        return json.load(f)


def validate_model_schema(model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate single model schema.
    
    Returns:
        {
            "valid": bool,
            "issues": List[str],
            "has_pricing": bool,
            "has_schema": bool,
            "required_params": int,
            "optional_params": int
        }
    """
    issues = []
    
    # Check model_id
    if not model.get('model_id'):
        issues.append("Missing model_id")
    
    # Check pricing
    pricing = model.get('pricing', {})
    has_pricing = bool(
        pricing.get('rub_per_use') is not None or
        pricing.get('credits_per_generation') is not None
    )
    
    if not has_pricing:
        issues.append("Missing pricing data")
    
    # Check schema
    schema = model.get('input_schema', {})
    has_schema = bool(schema)
    
    if not has_schema:
        issues.append("Missing input_schema")
    
    required = schema.get('required', [])
    optional = schema.get('optional', [])
    properties = schema.get('properties', {})
    
    # Validate required params have definitions
    for param in required:
        if param not in properties:
            issues.append(f"Required param '{param}' not in properties")
    
    # Check UX data
    if not model.get('description'):
        issues.append("Missing description")
    
    if not model.get('use_case'):
        issues.append("Missing use_case")
    
    if not model.get('tags'):
        issues.append("Missing tags")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "has_pricing": has_pricing,
        "has_schema": has_schema,
        "required_params": len(required),
        "optional_params": len(optional),
        "total_properties": len(properties)
    }


def test_payload_builder(model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test if payload builder can create payload for this model.
    
    Returns:
        {
            "success": bool,
            "error": Optional[str],
            "payload_size": int
        }
    """
    model_id = model['model_id']
    schema = model.get('input_schema', {})
    required = schema.get('required', [])
    properties = schema.get('properties', {})
    
    # Build minimal test inputs
    user_inputs = {}
    
    for param in required:
        prop = properties.get(param, {})
        param_type = prop.get('type', 'string')
        
        if param == 'prompt':
            user_inputs['prompt'] = "test"
        elif param == 'image':
            user_inputs['image'] = "https://example.com/test.jpg"
        elif param_type == 'string':
            user_inputs[param] = "test"
        elif param_type in ['number', 'integer']:
            user_inputs[param] = 1
        elif param_type == 'boolean':
            user_inputs[param] = True
    
    try:
        payload = build_payload(model_id, user_inputs)
        return {
            "success": True,
            "error": None,
            "payload_size": len(payload) if payload else 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "payload_size": 0
        }


def main():
    """Run comprehensive validation."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║      COMPREHENSIVE SCHEMA VALIDATION: ALL 77 MODELS           ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    # Load registry
    print("\n📦 Loading registry...")
    data = load_registry()
    models = data.get('models', [])
    version = data.get('version', 'unknown')
    
    print(f"   Version: {version}")
    print(f"   Total models: {len(models)}")
    
    # Validate each model
    print("\n🔍 Validating models...")
    
    results = []
    categories = defaultdict(int)
    issues_count = defaultdict(int)
    
    for model in models:
        model_id = model.get('model_id', 'unknown')
        category = model.get('category', 'unknown')
        categories[category] += 1
        
        # Schema validation
        schema_result = validate_model_schema(model)
        
        # Payload builder test
        builder_result = test_payload_builder(model)
        
        result = {
            "model_id": model_id,
            "display_name": model.get('display_name', model_id),
            "category": category,
            "schema_valid": schema_result['valid'],
            "schema_issues": schema_result['issues'],
            "has_pricing": schema_result['has_pricing'],
            "has_schema": schema_result['has_schema'],
            "required_params": schema_result['required_params'],
            "optional_params": schema_result['optional_params'],
            "builder_works": builder_result['success'],
            "builder_error": builder_result['error']
        }
        
        results.append(result)
        
        # Count issues
        for issue in schema_result['issues']:
            issues_count[issue] += 1
        
        if not builder_result['success']:
            issues_count['Payload builder failed'] += 1
    
    # Statistics
    print("\n" + "=" * 70)
    print("📊 VALIDATION RESULTS")
    print("=" * 70)
    
    valid_models = [r for r in results if r['schema_valid']]
    invalid_models = [r for r in results if not r['schema_valid']]
    
    with_pricing = [r for r in results if r['has_pricing']]
    with_schema = [r for r in results if r['has_schema']]
    builder_works = [r for r in results if r['builder_works']]
    
    print(f"\n✅ Schema Valid: {len(valid_models)}/{len(results)} ({len(valid_models)*100//len(results)}%)")
    print(f"💰 Has Pricing: {len(with_pricing)}/{len(results)} ({len(with_pricing)*100//len(results)}%)")
    print(f"📝 Has Schema: {len(with_schema)}/{len(results)} ({len(with_schema)*100//len(results)}%)")
    print(f"🏗️  Payload Builder Works: {len(builder_works)}/{len(results)} ({len(builder_works)*100//len(results)}%)")
    
    # Categories
    print(f"\n📂 CATEGORIES:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   - {cat}: {count} models")
    
    # Issues summary
    if issues_count:
        print(f"\n⚠️  ISSUES FOUND:")
        for issue, count in sorted(issues_count.items(), key=lambda x: -x[1])[:10]:
            print(f"   - {issue}: {count} models")
    
    # Invalid models details
    if invalid_models:
        print(f"\n❌ INVALID MODELS ({len(invalid_models)}):")
        for r in invalid_models[:10]:  # Show first 10
            print(f"\n   {r['display_name']}")
            print(f"      ID: {r['model_id']}")
            for issue in r['schema_issues']:
                print(f"      - {issue}")
    
    # Builder failures
    builder_failures = [r for r in results if not r['builder_works']]
    if builder_failures:
        print(f"\n🏗️  PAYLOAD BUILDER FAILURES ({len(builder_failures)}):")
        for r in builder_failures[:10]:
            print(f"   - {r['display_name']}: {r['builder_error']}")
    
    # Save results
    output_path = Path("artifacts/schema_validation_report.json")
    output_path.parent.mkdir(exist_ok=True)
    
    output = {
        "registry_version": version,
        "total_models": len(results),
        "valid_models": len(valid_models),
        "invalid_models": len(invalid_models),
        "with_pricing": len(with_pricing),
        "with_schema": len(with_schema),
        "builder_works": len(builder_works),
        "categories": dict(categories),
        "issues": dict(issues_count),
        "results": results
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed report saved: {output_path}")
    
    # Summary
    print("\n" + "=" * 70)
    
    if len(valid_models) == len(results) and len(builder_works) == len(results):
        print("✅ ALL MODELS VALID - READY FOR PRODUCTION")
        return 0
    elif len(valid_models) >= len(results) * 0.9:
        print(f"⚠️  MOSTLY VALID: {len(valid_models)}/{len(results)} - needs minor fixes")
        return 1
    else:
        print(f"❌ CRITICAL ISSUES: {len(invalid_models)}/{len(results)} invalid models")
        return 2


if __name__ == "__main__":
    sys.exit(main())
