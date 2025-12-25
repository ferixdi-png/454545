#!/usr/bin/env python3
"""
Quick health check - проверяет критичные компоненты системы.
Запускается перед деплоем для валидации.
"""
import sys
import json
from pathlib import Path

def check_registry():
    """Проверка registry v6.2."""
    print("🔍 Checking registry v6.2...")
    
    registry_path = Path("models/kie_models_final_truth.json")
    if not registry_path.exists():
        print("   ❌ FAIL: Registry file not found")
        return False
    
    with open(registry_path, 'r') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    free_tier_ids = data.get('free_tier_models', [])
    version = data.get('version', 'unknown')
    
    print(f"   ✅ Version: {version}")
    print(f"   ✅ Models: {len(models)}")
    print(f"   ✅ FREE tier: {len(free_tier_ids)}")
    
    # Check critical models exist
    for model_id in free_tier_ids:
        if not any(m['model_id'] == model_id for m in models):
            print(f"   ❌ FAIL: FREE tier model not found: {model_id}")
            return False
    
    # Check all models have pricing
    missing_pricing = [m['model_id'] for m in models if not m.get('pricing', {}).get('rub_per_generation')]
    if missing_pricing:
        print(f"   ⚠️  WARNING: {len(missing_pricing)} models without pricing")
    
    return True


def check_ui_tree():
    """Проверка UI tree."""
    print("\n🌳 Checking UI tree...")
    
    try:
        from app.ui.marketing_menu import build_ui_tree, load_registry
        
        registry = load_registry()
        print(f"   ✅ Registry loaded: {len(registry)} models")
        
        tree = build_ui_tree()
        total = sum(len(models) for models in tree.values())
        print(f"   ✅ UI tree built: {total} models")
        
        for cat_key, models in tree.items():
            if models:
                print(f"      - {cat_key}: {len(models)} models")
        
        return True
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def check_pricing():
    """Проверка pricing calculator."""
    print("\n💰 Checking pricing calculator...")
    
    try:
        from app.payments.pricing import calculate_kie_cost, calculate_user_price
        
        # Test with v6.2 format
        test_model = {
            "model_id": "test/model",
            "pricing": {
                "rub_per_generation": 10.0
            }
        }
        
        kie_cost = calculate_kie_cost(test_model, {}, None)
        user_price = calculate_user_price(kie_cost)
        
        if kie_cost != 10.0:
            print(f"   ❌ FAIL: Expected 10.0, got {kie_cost}")
            return False
        
        if user_price != 20.0:
            print(f"   ❌ FAIL: Expected 20.0 (2x markup), got {user_price}")
            return False
        
        print(f"   ✅ V6.2 format: {kie_cost}₽ KIE → {user_price}₽ USER")
        
        # Test with old format (backward compatibility)
        old_model = {
            "model_id": "old/model",
            "price": 1.0  # USD
        }
        
        kie_cost = calculate_kie_cost(old_model, {}, None)
        user_price = calculate_user_price(kie_cost)
        
        expected_kie = 78.0  # 1 USD × 78
        expected_user = 156.0  # 78 × 2
        
        if abs(kie_cost - expected_kie) > 0.01:
            print(f"   ❌ FAIL: Expected {expected_kie}, got {kie_cost}")
            return False
        
        print(f"   ✅ Old format: $1.00 → {kie_cost}₽ KIE → {user_price}₽ USER")
        
        return True
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def check_imports():
    """Проверка критичных импортов."""
    print("\n📦 Checking critical imports...")
    
    imports = [
        ("app.ui.marketing_menu", "UI menu"),
        ("app.payments.pricing", "Pricing"),
        ("app.free.manager", "FREE manager"),
        ("app.admin.service", "Admin service"),
        ("app.kie.builder", "KIE builder"),
        ("bot.handlers.marketing", "Marketing handlers"),
    ]
    
    for module_name, description in imports:
        try:
            __import__(module_name)
            print(f"   ✅ {description}")
        except Exception as e:
            print(f"   ❌ {description}: {e}")
            return False
    
    return True


def main():
    """Run all health checks."""
    print("=" * 80)
    print("🏥 QUICK HEALTH CHECK")
    print("=" * 80)
    
    checks = [
        ("Registry v6.2", check_registry),
        ("UI Tree", check_ui_tree),
        ("Pricing Calculator", check_pricing),
        ("Critical Imports", check_imports),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ {name} crashed: {e}")
            results[name] = False
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status:10} : {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - READY FOR PRODUCTION")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - FIX BEFORE DEPLOY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
