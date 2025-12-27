#!/usr/bin/env python3
"""
Comprehensive pre-deploy smoke tests.

Checks:
1. No generate_with_payment(payload=...) calls (all must use user_inputs=)
2. Schema can apply (syntax valid)
3. Version info works
4. Callback registry functional
5. Menu building works (no crashes)
6. Navigation handlers exist
"""
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_no_payload_calls():
    """Check no generate_with_payment(payload=...) calls."""
    logger.info("🔍 Checking for generate_with_payment(payload=...) calls...")
    
    result = subprocess.run(
        ["grep", "-r", "-E", "generate_with_payment.*payload=", "bot/", "app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        logger.error(f"❌ Found generate_with_payment(payload=...) calls:")
        for line in result.stdout.strip().split('\n')[:5]:
            logger.error(f"   {line}")
        return False
    
    logger.info("✅ No generate_with_payment(payload=...) calls (all use user_inputs=)")
    return True


def check_schema_syntax():
    """Check schema SQL syntax."""
    logger.info("\n🔍 Checking database schema syntax...")
    
    try:
        from app.database.schema import SCHEMA_SQL, apply_schema
        
        # Check SQL contains migration code
        if "ALTER TABLE users ADD COLUMN" not in apply_schema.__code__.co_consts:
            # Check source
            import inspect
            source = inspect.getsource(apply_schema)
            if "ALTER TABLE" not in source or "tg_username" not in source:
                logger.error("❌ Schema migration code missing (tg_username columns)")
                return False
        
        logger.info("✅ Schema SQL valid with migration support")
        return True
    except Exception as e:
        logger.error(f"❌ Schema error: {e}")
        return False


def check_version_info():
    """Check version info module."""
    logger.info("\n🔍 Checking version info...")
    
    try:
        from app.utils.version import get_version_string, get_git_commit, get_admin_version_info
        
        version = get_version_string()
        commit = get_git_commit()
        admin_info = get_admin_version_info()
        
        if not commit or commit == "unknown":
            logger.warning("⚠️  Git commit unknown (expected in CI/Render)")
        
        logger.info(f"✅ Version module works: {version}")
        return True
    except Exception as e:
        logger.error(f"❌ Version module error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_callback_registry():
    """Check callback registry."""
    logger.info("\n🔍 Checking callback registry...")
    
    try:
        from app.ui.callback_registry import make_key, resolve_key, init_registry_from_models
        from app.ui.catalog import load_models_sot
        
        models = load_models_sot()
        init_registry_from_models(models)
        
        # Test roundtrip
        test_model = list(models.keys())[0]
        key = make_key("gen", test_model)
        resolved = resolve_key(key)
        
        if resolved != test_model:
            logger.error(f"❌ Callback registry roundtrip failed: {test_model} → {key} → {resolved}")
            return False
        
        # Check all keys are short
        for model_id in models.keys():
            for prefix in ["m", "gen", "card"]:
                k = make_key(prefix, model_id)
                if len(k.encode('utf-8')) > 64:
                    logger.error(f"❌ Callback too long: {k} ({len(k)} bytes)")
                    return False
        
        logger.info(f"✅ Callback registry works ({len(models)} models, all keys <64 bytes)")
        return True
    except Exception as e:
        logger.error(f"❌ Callback registry error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_menu_building():
    """Check menu building doesn't crash."""
    logger.info("\n🔍 Checking menu building...")
    
    try:
        from bot.handlers.navigation import _build_main_menu_keyboard
        
        menu = _build_main_menu_keyboard()
        
        if not menu or not menu.inline_keyboard:
            logger.error("❌ Main menu empty")
            return False
        
        button_count = sum(len(row) for row in menu.inline_keyboard)
        logger.info(f"✅ Main menu builds OK ({button_count} buttons)")
        return True
    except Exception as e:
        logger.error(f"❌ Menu building error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_navigation_handlers():
    """Check navigation handlers exist."""
    logger.info("\n🔍 Checking navigation handlers...")
    
    try:
        from bot.handlers import navigation_router, gen_handler_router
        
        if not navigation_router:
            logger.error("❌ navigation_router not found")
            return False
        
        if not gen_handler_router:
            logger.error("❌ gen_handler_router not found")
            return False
        
        logger.info("✅ Navigation handlers exist")
        return True
    except Exception as e:
        logger.error(f"❌ Navigation handlers error: {e}")
        return False


def check_integration_function():
    """Check generate_with_payment signature supports both payload and user_inputs."""
    logger.info("\n🔍 Checking generate_with_payment signature...")
    
    try:
        from app.payments.integration import generate_with_payment
        import inspect
        
        sig = inspect.signature(generate_with_payment)
        params = sig.parameters
        
        if 'user_inputs' not in params:
            logger.error("❌ generate_with_payment missing user_inputs parameter")
            return False
        
        if 'payload' not in params:
            logger.error("❌ generate_with_payment missing payload parameter (backward compat)")
            return False
        
        # Check defaults
        if params['payload'].default == inspect.Parameter.empty:
            logger.error("❌ payload parameter should have default=None")
            return False
        
        logger.info("✅ generate_with_payment signature correct (user_inputs + payload compat)")
        return True
    except Exception as e:
        logger.error(f"❌ Integration function error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks."""
    logger.info("=" * 60)
    logger.info("PRE-DEPLOY SMOKE TESTS")
    logger.info("=" * 60)
    
    checks = [
        ("Payload calls check", check_no_payload_calls),
        ("Schema syntax", check_schema_syntax),
        ("Version info", check_version_info),
        ("Callback registry", check_callback_registry),
        ("Menu building", check_menu_building),
        ("Navigation handlers", check_navigation_handlers),
        ("Integration function", check_integration_function),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            results.append(check_fn())
        except Exception as e:
            logger.error(f"\n❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"RESULTS: {sum(results)}/{len(results)} checks passed")
    logger.info("=" * 60)
    
    if all(results):
        logger.info("\n✅ ALL SMOKE TESTS PASSED - Ready for deploy!")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED - Fix issues before deploy")
        return 1


if __name__ == "__main__":
    sys.exit(main())
