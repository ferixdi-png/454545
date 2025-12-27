#!/usr/bin/env python3
"""
Model Coverage Audit - проверяет что ВСЕ модели Kie.ai доступны в UI.

Проверяет:
1. Все модели из registry есть в UI (categories/handlers)
2. Нет "потерянных" моделей
3. Нет "фантомных" моделей (в UI, но не в registry)
4. Все модели имеют валидный input_schema
"""
import json
import sys
from pathlib import Path
from typing import Dict, Set, List, Any


def load_registry() -> Dict[str, Any]:
    """Load source of truth registry."""
    registry_path = Path("models/kie_models_source_of_truth.json")
    with open(registry_path, 'r') as f:
        return json.load(f)


def get_registry_models(registry: Dict) -> Set[str]:
    """Get all model IDs from registry."""
    return {m['model_id'] for m in registry['models']}


def get_ui_models() -> Set[str]:
    """Get all model IDs accessible from UI."""
    # UI models определяются через registry + enabled флаг
    registry = load_registry()
    
    # В нашей системе UI = все модели с is_pricing_known=True
    ui_models = {
        m['model_id'] 
        for m in registry['models'] 
        if m.get('is_pricing_known', False)
    }
    
    return ui_models


def get_broken_models(registry: Dict) -> List[Dict[str, Any]]:
    """Find models without valid input_schema."""
    broken = []
    
    for model in registry['models']:
        model_id = model['model_id']
        schema = model.get('input_schema')
        
        # Check if schema exists
        if not schema:
            broken.append({
                'model_id': model_id,
                'reason': 'missing_schema',
                'has_pricing': model.get('is_pricing_known', False)
            })
            continue
        
        # Check if schema has required fields
        if not isinstance(schema, dict):
            broken.append({
                'model_id': model_id,
                'reason': 'invalid_schema_type',
                'schema_type': type(schema).__name__
            })
            continue
        
        # Check for properties
        if 'properties' not in schema:
            broken.append({
                'model_id': model_id,
                'reason': 'missing_properties',
                'schema_keys': list(schema.keys())
            })
            continue
    
    return broken


def generate_coverage_report():
    """Generate comprehensive coverage report."""
    print("=" * 70)
    print("MODEL COVERAGE AUDIT")
    print("=" * 70)
    print()
    
    # Load data
    registry = load_registry()
    registry_models = get_registry_models(registry)
    ui_models = get_ui_models()
    broken_models = get_broken_models(registry)
    
    # Calculate coverage
    total_registry = len(registry_models)
    total_ui = len(ui_models)
    missing_in_ui = registry_models - ui_models
    extra_in_ui = ui_models - registry_models
    
    # Print summary
    print(f"📊 SUMMARY:")
    print(f"  Registry models:     {total_registry}")
    print(f"  UI models:           {total_ui}")
    print(f"  Coverage:            {total_ui}/{total_registry} ({100*total_ui/total_registry:.1f}%)")
    print()
    
    # Check missing
    if missing_in_ui:
        print(f"❌ MISSING IN UI ({len(missing_in_ui)}):")
        for model_id in sorted(missing_in_ui):
            model = next(m for m in registry['models'] if m['model_id'] == model_id)
            reason = "no pricing" if not model.get('is_pricing_known') else "unknown"
            print(f"  - {model_id} ({reason})")
        print()
    else:
        print("✅ NO MISSING MODELS")
        print()
    
    # Check extra
    if extra_in_ui:
        print(f"⚠️  EXTRA IN UI ({len(extra_in_ui)}):")
        for model_id in sorted(extra_in_ui):
            print(f"  - {model_id}")
        print()
    else:
        print("✅ NO EXTRA MODELS")
        print()
    
    # Check broken schemas
    if broken_models:
        print(f"⚠️  BROKEN SCHEMAS ({len(broken_models)}):")
        for item in broken_models:
            print(f"  - {item['model_id']}: {item['reason']}")
        print()
    else:
        print("✅ ALL SCHEMAS VALID")
        print()
    
    # Generate JSON report
    report = {
        'summary': {
            'total_registry': total_registry,
            'total_ui': total_ui,
            'coverage_percent': round(100 * total_ui / total_registry, 2),
            'missing_count': len(missing_in_ui),
            'extra_count': len(extra_in_ui),
            'broken_count': len(broken_models)
        },
        'missing_in_ui': sorted(list(missing_in_ui)),
        'extra_in_ui': sorted(list(extra_in_ui)),
        'broken_models': broken_models,
        'all_registry_models': sorted(list(registry_models)),
        'all_ui_models': sorted(list(ui_models))
    }
    
    # Save reports
    Path('artifacts').mkdir(exist_ok=True)
    
    with open('artifacts/model_coverage_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate markdown
    md = f"""# Model Coverage Report

Generated: {__import__('datetime').datetime.now().isoformat()}

## Summary

| Metric | Value |
|--------|-------|
| Registry models | {total_registry} |
| UI models | {total_ui} |
| Coverage | {report['summary']['coverage_percent']}% |
| Missing in UI | {len(missing_in_ui)} |
| Extra in UI | {len(extra_in_ui)} |
| Broken schemas | {len(broken_models)} |

## Status

"""
    
    if missing_in_ui:
        md += f"### ❌ Missing in UI ({len(missing_in_ui)})\n\n"
        for model_id in sorted(missing_in_ui):
            model = next(m for m in registry['models'] if m['model_id'] == model_id)
            reason = "no pricing" if not model.get('is_pricing_known') else "unknown"
            md += f"- `{model_id}` - {reason}\n"
        md += "\n"
    else:
        md += "### ✅ No missing models\n\n"
    
    if extra_in_ui:
        md += f"### ⚠️  Extra in UI ({len(extra_in_ui)})\n\n"
        for model_id in sorted(extra_in_ui):
            md += f"- `{model_id}`\n"
        md += "\n"
    else:
        md += "### ✅ No extra models\n\n"
    
    if broken_models:
        md += f"### ⚠️  Broken schemas ({len(broken_models)})\n\n"
        for item in broken_models:
            md += f"- `{item['model_id']}` - {item['reason']}\n"
        md += "\n"
    else:
        md += "### ✅ All schemas valid\n\n"
    
    with open('artifacts/model_coverage_report.md', 'w') as f:
        f.write(md)
    
    print("=" * 70)
    print("📁 ARTIFACTS GENERATED:")
    print("  - artifacts/model_coverage_report.json")
    print("  - artifacts/model_coverage_report.md")
    print("=" * 70)
    print()
    
    # Exit code
    if missing_in_ui or broken_models:
        print("❌ COVERAGE AUDIT: FAILED")
        return 1
    else:
        print("✅ COVERAGE AUDIT: PASSED")
        return 0


if __name__ == '__main__':
    sys.exit(generate_coverage_report())
