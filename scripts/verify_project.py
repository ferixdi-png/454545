#!/usr/bin/env python3
"""
Verify project invariants against current SOURCE_OF_TRUTH structure.

Current schema:
- models/KIE_SOURCE_OF_TRUTH.json
- Root: version, models (dict), updated_at, metadata
- Model: endpoint, input_schema, pricing, tags, ui_example_prompts, examples
"""
import json
import sys
from pathlib import Path

def verify_project():
    """Verify project structure and SOURCE_OF_TRUTH integrity."""
    errors = []
    warnings = []
    
    # 1. Check SOURCE_OF_TRUTH exists
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not sot_path.exists():
        errors.append(f"❌ SOURCE_OF_TRUTH not found: {sot_path}")
        print("\n".join(errors))
        return 1
    
    # 2. Load and parse
    try:
        with open(sot_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"❌ JSON parse error: {e}")
        print("\n".join(errors))
        return 1
    
    # 3. Validate root structure
    if not isinstance(data.get('models'), dict):
        errors.append(f"❌ 'models' must be dict, got: {type(data.get('models'))}")
    
    models = data.get('models', {})
    
    if len(models) < 20:
        warnings.append(f"⚠️  Only {len(models)} models (expected >= 20)")
    
    # 4. Validate each model
    for model_id, model in models.items():
        if not isinstance(model_id, str) or not model_id.strip():
            errors.append(f"❌ Invalid model_id: {repr(model_id)}")
            continue
        
        if not isinstance(model, dict):
            errors.append(f"❌ Model {model_id} is not dict: {type(model)}")
            continue
        
        # Required fields
        endpoint = model.get('endpoint')
        if not isinstance(endpoint, str) or not endpoint:
            errors.append(f"❌ {model_id}: missing/invalid 'endpoint'")
        
        input_schema = model.get('input_schema')
        if not isinstance(input_schema, dict):
            errors.append(f"❌ {model_id}: 'input_schema' must be dict")
        elif not input_schema:
            warnings.append(f"⚠️  {model_id}: empty input_schema")
        
        pricing = model.get('pricing')
        if not isinstance(pricing, dict):
            errors.append(f"❌ {model_id}: 'pricing' must be dict")
        else:
            usd = pricing.get('usd_per_gen')
            rub = pricing.get('rub_per_gen')
            
            if not isinstance(usd, (int, float)) or usd < 0:
                errors.append(f"❌ {model_id}: invalid pricing.usd_per_gen: {usd}")
            
            if not isinstance(rub, (int, float)) or rub < 0:
                errors.append(f"❌ {model_id}: invalid pricing.rub_per_gen: {rub}")
        
        # Optional but recommended
        tags = model.get('tags')
        if not isinstance(tags, list):
            warnings.append(f"⚠️  {model_id}: 'tags' should be list[str]")
        
        prompts = model.get('ui_example_prompts')
        if not isinstance(prompts, list) or len(prompts) == 0:
            warnings.append(f"⚠️  {model_id}: no ui_example_prompts")
    
    # 5. Summary
    print("═" * 70)
    print("🔍 PROJECT VERIFICATION")
    print("═" * 70)
    print(f"📦 SOURCE_OF_TRUTH: {sot_path}")
    print(f"📊 Total models: {len(models)}")
    print(f"✅ Version: {data.get('version', 'N/A')}")
    print(f"📅 Updated: {data.get('updated_at', 'N/A')}")
    print()
    
    if errors:
        print(f"❌ ERRORS: {len(errors)}")
        for err in errors[:10]:  # First 10
            print(f"  {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print()
    
    if warnings:
        print(f"⚠️  WARNINGS: {len(warnings)}")
        for warn in warnings[:5]:  # First 5
            print(f"  {warn}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")
        print()
    
    if not errors:
        print("✅ All critical checks passed!")
        print("═" * 70)
        return 0
    else:
        print("❌ Verification FAILED")
        print("═" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(verify_project())
