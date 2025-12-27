#!/usr/bin/env python3
"""Critical hotfix smoke tests."""
import sys
import subprocess

def check_no_payload_calls():
    """Check no generate_with_payment(payload=...) calls."""
    result = subprocess.run(
        ["grep", "-r", "-E", "generate_with_payment.*payload=", "bot/", "app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        print(f"❌ Found generate_with_payment(payload=...) calls")
        return False
    
    print("✅ No generate_with_payment(payload=...) calls")
    return True

def check_version():
    """Check version module."""
    try:
        from app.utils.version import get_version_string
        version = get_version_string()
        print(f"✅ Version: {version}")
        return True
    except Exception as e:
        print(f"❌ Version error: {e}")
        return False

def check_schema():
    """Check schema has migration code."""
    try:
        from app.database.schema import apply_schema
        import inspect
        source = inspect.getsource(apply_schema)
        has_migration = "ALTER TABLE" in source and "tg_username" in source
        if has_migration:
            print("✅ Schema has migration code")
            return True
        else:
            print("❌ Schema missing migration code")
            return False
    except Exception as e:
        print(f"❌ Schema error: {e}")
        return False

if __name__ == "__main__":
    print("HOTFIX SMOKE TESTS")
    print("=" * 40)
    
    checks = [
        check_no_payload_calls,
        check_version,
        check_schema,
    ]
    
    results = [check() for check in checks]
    
    print("=" * 40)
    print(f"Results: {sum(results)}/{len(results)} passed")
    
    sys.exit(0 if all(results) else 1)
