#!/usr/bin/env python3
"""Extended project verification - checks compatibility fixes."""
import sys
import json
import inspect
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

errors = []
warnings = []


def check_generate_with_payment_signature():
    """Verify generate_with_payment accepts payload parameter."""
    print("✓ Checking generate_with_payment signature...")
    
    try:
        from app.payments.integration import generate_with_payment
        
        sig = inspect.signature(generate_with_payment)
        params = list(sig.parameters.keys())
        
        if 'payload' not in params:
            errors.append("generate_with_payment must have 'payload' parameter for backward compat")
        else:
            print("  ✅ 'payload' parameter exists")
        
        if 'user_inputs' not in params:
            errors.append("generate_with_payment must have 'user_inputs' parameter")
        else:
            print("  ✅ 'user_inputs' parameter exists")
            
    except Exception as e:
        errors.append(f"Failed to import generate_with_payment: {e}")


def check_curated_popular_models():
    """Verify curated_popular.json only contains models from SOURCE_OF_TRUTH."""
    print("✓ Checking curated_popular.json against SOURCE_OF_TRUTH...")
    
    try:
        sot_file = REPO_ROOT / "models/KIE_SOURCE_OF_TRUTH.json"
        curated_file = REPO_ROOT / "app/ui/curated_popular.json"
        
        with open(sot_file, 'r') as f:
            sot = json.load(f)
        
        with open(curated_file, 'r') as f:
            curated = json.load(f)
        
        enabled_ids = {m['model_id'] for m in sot['models'].values() if m.get('enabled', True)}
        
        # Check popular_models list
        popular = curated.get('popular_models', [])
        invalid_popular = [m for m in popular if m not in enabled_ids]
        
        if invalid_popular:
            errors.append(f"curated_popular.json contains invalid models in popular_models: {invalid_popular}")
        else:
            print(f"  ✅ All {len(popular)} popular models exist in SOURCE_OF_TRUTH")
        
        # Check recommended_by_format
        for fmt, model_list in curated.get('recommended_by_format', {}).items():
            invalid = [m for m in model_list if m not in enabled_ids]
            if invalid:
                warnings.append(f"curated_popular.json format '{fmt}' contains invalid models: {invalid}")
        
        print(f"  ✅ Verified {len(curated.get('recommended_by_format', {}))} format categories")
        
    except Exception as e:
        errors.append(f"Failed to verify curated_popular.json: {e}")


def check_users_schema():
    """Verify users table schema has tg_username, tg_first_name, tg_last_name."""
    print("✓ Checking users table schema...")
    
    try:
        schema_file = REPO_ROOT / "app/database/schema.py"
        
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        if 'tg_username' in schema_sql:
            print("  ✅ tg_username column present")
        else:
            warnings.append("schema.py should have tg_username column (old schema: username)")
        
        if 'tg_first_name' in schema_sql:
            print("  ✅ tg_first_name column present")
        else:
            warnings.append("schema.py should have tg_first_name column")
        
        if 'tg_last_name' in schema_sql:
            print("  ✅ tg_last_name column present")
        else:
            warnings.append("schema.py should have tg_last_name column")
            
    except Exception as e:
        errors.append(f"Failed to check schema.py: {e}")


def check_no_hardcoded_payload_calls():
    """Grep for generate_with_payment(payload=...) calls (should use user_inputs=)."""
    print("✓ Checking for hardcoded payload= calls...")
    
    try:
        import subprocess
        
        result = subprocess.run(
            ['grep', '-r', '-n', 'generate_with_payment.*payload=', 
             str(REPO_ROOT / 'bot'), str(REPO_ROOT / 'app')],
            capture_output=True,
            text=True
        )
        
        # Filter out backward compat parameter definition and comments
        lines = [l for l in result.stdout.splitlines() 
                if 'payload:' not in l  # parameter definition
                and '# payload' not in l.lower()  # comments
                and 'payload=' in l]  # actual calls
        
        if lines:
            warnings.append(f"Found {len(lines)} potential payload= calls (check if using user_inputs= is better)")
            for line in lines[:5]:
                print(f"  ⚠️  {line}")
        else:
            print("  ✅ No hardcoded payload= calls found")
            
    except Exception as e:
        warnings.append(f"Failed to grep for payload calls: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("EXTENDED PROJECT VERIFICATION")
    print("=" * 60)
    
    check_generate_with_payment_signature()
    check_curated_popular_models()
    check_users_schema()
    check_no_hardcoded_payload_calls()
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ {len(errors)} ERRORS:")
        for err in errors:
            print(f"  • {err}")
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} WARNINGS:")
        for warn in warnings:
            print(f"  • {warn}")
    
    if not errors and not warnings:
        print("\n✅ ALL CHECKS PASSED")
        sys.exit(0)
    elif errors:
        print(f"\n❌ VERIFICATION FAILED ({len(errors)} errors, {len(warnings)} warnings)")
        sys.exit(1)
    else:
        print(f"\n✅ VERIFICATION PASSED ({len(warnings)} warnings)")
        sys.exit(0)
