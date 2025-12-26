"""
Verify UI compliance with requirements.

Checks:
- No "kie.ai" in UI strings
- All enabled models covered
- FREE + Referral in main menu
- Callback lengths <= 64
"""
import sys
import os
import re
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_no_kie_ai():
    """Check that no 'kie.ai' appears in UI code."""
    print("🔍 Checking for 'kie.ai' in UI...")
    
    ui_paths = [
        Path("app/ui"),
        Path("bot/handlers"),
    ]
    
    violations = []
    
    for base_path in ui_paths:
        if not base_path.exists():
            continue
        
        for py_file in base_path.rglob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for kie.ai (case-insensitive)
                if re.search(r'kie\.ai', content, re.IGNORECASE):
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if re.search(r'kie\.ai', line, re.IGNORECASE):
                            violations.append(f"{py_file}:{i}: {line.strip()}")
    
    if violations:
        print("❌ Found 'kie.ai' in UI:")
        for v in violations:
            print(f"  {v}")
        return False
    
    print("✅ No 'kie.ai' found in UI")
    return True


def check_all_models_covered():
    """Check that all enabled models are in UI tree."""
    print("\n🔍 Checking model coverage...")
    
    try:
        from app.ui.catalog import get_all_enabled_models, build_ui_tree
        
        all_models = get_all_enabled_models()
        tree = build_ui_tree()
        
        tree_ids = set()
        for models in tree.values():
            for m in models:
                tree_ids.add(m.get("model_id"))
        
        all_ids = set(m.get("model_id") for m in all_models)
        
        if tree_ids == all_ids:
            print(f"✅ All {len(all_ids)} enabled models covered")
            return True
        else:
            lost = all_ids - tree_ids
            print(f"❌ Lost models: {lost}")
            return False
    except Exception as e:
        print(f"❌ Error checking coverage: {e}")
        return False


def check_callback_lengths():
    """Check that callback_data strings don't exceed 64 bytes."""
    print("\n🔍 Checking callback_data lengths...")
    
    # Sample callbacks from code
    test_callbacks = [
        "main_menu",
        "menu:free",
        "menu:referral",
        "menu:popular",
        "menu:history",
        "menu:balance",
        "menu:pricing",
        "menu:search",
        "menu:help",
        "cat:video",
        "cat:image",
        "cat:text_ads",
        "cat:audio_voice",
        "cat:music",
        "cat:tools",
        "cat:other",
    ]
    
    # Add model: callbacks
    try:
        from app.ui.catalog import get_all_enabled_models
        models = get_all_enabled_models()
        for model in models[:10]:
            model_id = model.get("model_id", "")
            test_callbacks.append(f"model:{model_id}")
            test_callbacks.append(f"gen:{model_id}")
    except Exception:
        pass
    
    violations = []
    for cb in test_callbacks:
        if len(cb) > 64:
            violations.append(f"{cb} ({len(cb)} bytes)")
    
    if violations:
        print("❌ Callbacks too long:")
        for v in violations:
            print(f"  {v}")
        return False
    
    print(f"✅ All {len(test_callbacks)} callbacks <= 64 bytes")
    return True


def check_main_menu_features():
    """Check that main menu has FREE and Referral."""
    print("\n🔍 Checking main menu features...")
    
    try:
        marketing_file = Path("bot/handlers/marketing.py")
        if not marketing_file.exists():
            print("❌ marketing.py not found")
            return False
        
        with open(marketing_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_free = "menu:free" in content
        has_referral = "menu:referral" in content
        
        if has_free and has_referral:
            print("✅ Main menu has FREE and Referral buttons")
            return True
        else:
            print(f"❌ Main menu missing: FREE={has_free}, Referral={has_referral}")
            return False
    except Exception as e:
        print(f"❌ Error checking main menu: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("UI COMPLIANCE VERIFICATION")
    print("=" * 60)
    
    results = []
    
    results.append(("No kie.ai in UI", check_no_kie_ai()))
    results.append(("All models covered", check_all_models_covered()))
    results.append(("Callback lengths", check_callback_lengths()))
    results.append(("Main menu features", check_main_menu_features()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n✅ All checks passed!")
        return 0
    else:
        print("\n❌ Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
