#!/usr/bin/env python3
"""
Validate SOURCE_OF_TRUTH structure and schema compliance.

Schema (current):
- Root: version, models (dict), updated_at (optional), metadata (optional)
- Model fields:
  - endpoint (required str)
  - pricing (required dict with usd_per_gen, rub_per_gen)
  - input_schema (required dict, can be empty)
  - examples (optional list[str] or list[dict])
  - tags (optional list[str])
  - ui_example_prompts (optional list[str])
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

def validate_root(data: Dict) -> Tuple[List[str], List[str]]:
    """Validate root-level structure."""
    errors = []
    warnings = []
    
    # Required
    if 'version' not in data:
        warnings.append("⚠️  Root: missing 'version'")
    
    if 'models' not in data:
        errors.append("❌ Root: missing 'models'")
    elif not isinstance(data['models'], dict):
        errors.append(f"❌ Root: 'models' must be dict, got {type(data['models'])}")
    
    # Optional metadata
    if 'updated_at' not in data and 'last_updated' not in data:
        warnings.append("⚠️  Root: no 'updated_at' timestamp")
    
    return errors, warnings

def validate_model(model_id: str, model: Dict) -> Tuple[List[str], List[str]]:
    """Validate single model structure."""
    errors = []
    warnings = []
    
    # endpoint (required)
    endpoint = model.get('endpoint')
    if not endpoint:
        errors.append(f"❌ {model_id}: missing 'endpoint'")
    elif not isinstance(endpoint, str):
        errors.append(f"❌ {model_id}: 'endpoint' must be string")
    
    # pricing (required)
    pricing = model.get('pricing')
    if not pricing:
        errors.append(f"❌ {model_id}: missing 'pricing'")
    elif not isinstance(pricing, dict):
        errors.append(f"❌ {model_id}: 'pricing' must be dict")
    else:
        usd = pricing.get('usd_per_gen')
        rub = pricing.get('rub_per_gen')
        
        if not isinstance(usd, (int, float)):
            errors.append(f"❌ {model_id}: pricing.usd_per_gen must be number")
        elif usd < 0:
            errors.append(f"❌ {model_id}: pricing.usd_per_gen cannot be negative")
        
        if not isinstance(rub, (int, float)):
            errors.append(f"❌ {model_id}: pricing.rub_per_gen must be number")
        elif rub < 0:
            errors.append(f"❌ {model_id}: pricing.rub_per_gen cannot be negative")
    
    # input_schema (required but can be empty)
    input_schema = model.get('input_schema')
    if input_schema is None:
        errors.append(f"❌ {model_id}: missing 'input_schema'")
    elif not isinstance(input_schema, dict):
        errors.append(f"❌ {model_id}: 'input_schema' must be dict")
    elif not input_schema:
        warnings.append(f"⚠️  {model_id}: empty input_schema (no parameters)")
    
    # examples (optional, can be list[str] or list[dict])
    examples = model.get('examples')
    if examples is not None:
        if not isinstance(examples, list):
            warnings.append(f"⚠️  {model_id}: 'examples' should be list")
        elif examples:
            first = examples[0]
            if isinstance(first, str):
                # curl string format
                if 'curl' not in first.lower() and '--url' not in first.lower():
                    warnings.append(f"⚠️  {model_id}: examples[0] doesn't look like curl command")
            elif not isinstance(first, dict):
                warnings.append(f"⚠️  {model_id}: examples should be list[str] or list[dict]")
    
    # tags (optional)
    tags = model.get('tags')
    if tags is not None and not isinstance(tags, list):
        warnings.append(f"⚠️  {model_id}: 'tags' should be list[str]")
    
    # ui_example_prompts (optional)
    prompts = model.get('ui_example_prompts')
    if prompts is not None and not isinstance(prompts, list):
        warnings.append(f"⚠️  {model_id}: 'ui_example_prompts' should be list[str]")
    
    return errors, warnings

def validate_source_of_truth():
    """Main validation function."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    
    if not sot_path.exists():
        print(f"❌ SOURCE_OF_TRUTH not found: {sot_path}")
        return 1
    
    try:
        with open(sot_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return 1
    
    all_errors = []
    all_warnings = []
    
    # Validate root
    root_errors, root_warnings = validate_root(data)
    all_errors.extend(root_errors)
    all_warnings.extend(root_warnings)
    
    # Validate models
    models = data.get('models', {})
    if isinstance(models, dict):
        for model_id, model in models.items():
            if not isinstance(model, dict):
                all_errors.append(f"❌ {model_id}: not a dict")
                continue
            
            m_errors, m_warnings = validate_model(model_id, model)
            all_errors.extend(m_errors)
            all_warnings.extend(m_warnings)
    
    # Summary
    print("═" * 70)
    print("🔍 SOURCE_OF_TRUTH VALIDATION")
    print("═" * 70)
    print(f"📦 File: {sot_path}")
    print(f"📊 Total models: {len(models)}")
    print()
    
    if all_errors:
        print(f"❌ ERRORS: {len(all_errors)}")
        for err in all_errors[:10]:
            print(f"  {err}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more")
        print()
    
    if all_warnings:
        print(f"⚠️  WARNINGS: {len(all_warnings)}")
        for warn in all_warnings[:10]:
            print(f"  {warn}")
        if len(all_warnings) > 10:
            print(f"  ... and {len(all_warnings) - 10} more")
        print()
    
    if all_errors:
        print("❌ Validation FAILED")
        print("═" * 70)
        return 1
    else:
        print("✅ Validation PASSED")
        print(f"   ({len(all_warnings)} warnings, non-critical)")
        print("═" * 70)
        return 0

if __name__ == "__main__":
    sys.exit(validate_source_of_truth())
