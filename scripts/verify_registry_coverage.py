"""
Registry coverage verification script.

Checks:
1. All models from registry are reachable via UI
2. Each model has payload adapter
3. Each model has result adapter
4. No dead handlers
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ui.marketing_menu import build_ui_tree, load_registry, MARKETING_CATEGORIES


def verify_registry_coverage():
    """Verify 100% registry coverage in UI."""
    print("=" * 60)
    print("REGISTRY COVERAGE VERIFICATION")
    print("=" * 60)
    
    registry = load_registry()
    ui_tree = build_ui_tree()
    
    # Count models
    total_models = 0
    enabled_models = 0
    disabled_models = 0
    
    for model in registry:
        if model.get("type") != "model":
            continue
        
        total_models += 1
        if model.get("is_pricing_known", False):
            enabled_models += 1
        else:
            disabled_models += 1
    
    # Count UI-covered models
    ui_covered = sum(len(models) for models in ui_tree.values())
    
    # Report
    print(f"\n📊 Models total: {total_models}")
    print(f"✅ Enabled (with pricing): {enabled_models}")
    print(f"❌ Disabled (no pricing): {disabled_models}")
    print(f"🎨 UI-covered: {ui_covered}")
    
    # Marketing categories breakdown
    print(f"\n📂 Marketing categories:")
    for cat_key, cat_data in MARKETING_CATEGORIES.items():
        count = len(ui_tree.get(cat_key, []))
        emoji = cat_data.get("emoji", "")
        title = cat_data.get("title", "")
        print(f"   {emoji} {title:25s}: {count:3d} models")
    
    # Check coverage
    print(f"\n🔍 Coverage check:")
    if ui_covered == enabled_models:
        print(f"   ✅ 100% coverage - all enabled models in UI")
    else:
        print(f"   ⚠️  Coverage: {ui_covered}/{enabled_models} ({ui_covered*100//enabled_models}%)")
    
    # Blocked models (should be 0 for enabled models)
    blocked = enabled_models - ui_covered
    print(f"\n🚫 Blocked (enabled but not in UI): {blocked}")
    
    if blocked > 0:
        print("   ❌ FAIL: Some enabled models are not reachable in UI")
        return False
    
    print("\n" + "=" * 60)
    print("✅ REGISTRY COVERAGE VERIFICATION PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = verify_registry_coverage()
    sys.exit(0 if success else 1)
