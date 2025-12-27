#!/usr/bin/env python3
"""
Comprehensive navigation stability verification.

Checks:
1. No /workspaces paths in runtime code
2. All callbacks use short keys (<64 bytes)
3. Callback registry initialized properly
4. Navigation handlers exist
5. Format map loads correctly
"""
import sys
import subprocess
from pathlib import Path

def check_no_workspaces_paths():
    """Check for hardcoded /workspaces paths."""
    print("🔍 Checking for /workspaces paths...")
    
    result = subprocess.run(
        ["grep", "-r", "/workspaces/454545", "bot/", "app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        # Found matches - filter out comments/tests
        lines = result.stdout.strip().split('\n')
        runtime_matches = [l for l in lines if not ("#" in l or "test" in l.lower())]
        
        if runtime_matches:
            print(f"❌ Found {len(runtime_matches)} /workspaces paths in runtime code:")
            for match in runtime_matches[:5]:
                print(f"   {match}")
            return False
    
    print("✅ No /workspaces paths found")
    return True


def check_short_callbacks():
    """Check that all callbacks use short keys."""
    print("\n🔍 Checking callback lengths...")
    
    from app.ui.callback_registry import make_key
    from app.ui.catalog import load_models_sot
    
    try:
        models = load_models_sot()
        
        for model_id in models.keys():
            for prefix in ["m", "gen", "card"]:
                key = make_key(prefix, model_id)
                byte_len = len(key.encode('utf-8'))
                
                if byte_len > 64:
                    print(f"❌ Callback too long: {key} ({byte_len} bytes)")
                    return False
        
        print(f"✅ All {len(models)} models have short callbacks (<64 bytes)")
        return True
    except Exception as e:
        print(f"❌ Error checking callbacks: {e}")
        return False


def check_registry_initialized():
    """Check that callback registry can be initialized."""
    print("\n🔍 Checking callback registry initialization...")
    
    try:
        from app.ui.callback_registry import init_registry_from_models, resolve_key, make_key
        from app.ui.catalog import load_models_sot
        
        models = load_models_sot()
        init_registry_from_models(models)
        
        # Test a few roundtrips
        test_model = list(models.keys())[0]
        key = make_key("gen", test_model)
        resolved = resolve_key(key)
        
        if resolved != test_model:
            print(f"❌ Roundtrip failed: {test_model} → {key} → {resolved}")
            return False
        
        print(f"✅ Callback registry initialized with {len(models)} models")
        return True
    except Exception as e:
        print(f"❌ Error initializing registry: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_navigation_handlers():
    """Check that navigation handlers exist."""
    print("\n🔍 Checking navigation handlers...")
    
    try:
        from bot.handlers import navigation_router, gen_handler_router
        
        assert navigation_router is not None, "navigation_router not found"
        assert gen_handler_router is not None, "gen_handler_router not found"
        
        print("✅ Navigation handlers exist")
        return True
    except Exception as e:
        print(f"❌ Error loading handlers: {e}")
        return False


def check_format_map():
    """Check that format map loads."""
    print("\n🔍 Checking format map...")
    
    try:
        import json
        
        repo_root = Path(__file__).resolve().parent.parent
        map_file = repo_root / "app/ui/content/model_format_map.json"
        
        if not map_file.exists():
            print(f"❌ Format map not found: {map_file}")
            return False
        
        with open(map_file, "r", encoding="utf-8") as f:
            format_map = json.load(f)
        
        if "model_to_formats" not in format_map:
            print("❌ Format map missing model_to_formats key")
            return False
        
        model_count = len(format_map["model_to_formats"])
        print(f"✅ Format map loaded ({model_count} models)")
        return True
    except Exception as e:
        print(f"❌ Error loading format map: {e}")
        return False


def check_validate_callback():
    """Check that validate_callback doesn't truncate."""
    print("\n🔍 Checking validate_callback behavior...")
    
    try:
        from app.ui.nav import validate_callback
        
        # Should accept short callbacks
        short = "menu:main"
        validate_callback(short)
        
        # Should reject long callbacks
        long = "x" * 100
        try:
            validate_callback(long)
            print("❌ validate_callback accepted long callback (should raise)")
            return False
        except ValueError:
            # Expected
            pass
        
        print("✅ validate_callback raises on long callbacks (no truncation)")
        return True
    except Exception as e:
        print(f"❌ Error checking validate_callback: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("NAVIGATION STABILITY VERIFICATION")
    print("=" * 60)
    
    checks = [
        check_no_workspaces_paths,
        check_short_callbacks,
        check_registry_initialized,
        check_navigation_handlers,
        check_format_map,
        check_validate_callback,
    ]
    
    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"\n❌ Check failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} checks passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ ALL CHECKS PASSED - Navigation stability verified!")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review issues above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
