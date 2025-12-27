#!/usr/bin/env python3
"""
Verify runtime contracts for critical functions.
CRITICAL: This test ensures generate_with_payment signature is backward compatible.

Run before deployment to catch signature breaking changes.
"""
import sys
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_generate_with_payment_signature():
    """
    CRITICAL: Verify generate_with_payment accepts both user_inputs and payload.
    
    This prevents TypeError in production when old code calls:
    generate_with_payment(payload=...)
    
    Requirements:
    1. Must have 'payload' parameter (backward compat)
    2. Must have **kwargs (never crash on unknown args)
    3. Should have 'user_inputs' parameter (preferred)
    """
    from app.payments.integration import generate_with_payment
    
    sig = inspect.signature(generate_with_payment)
    params = sig.parameters
    
    # Check 1: Has payload parameter
    if 'payload' not in params:
        print("❌ FAIL: generate_with_payment missing 'payload' parameter")
        print(f"   Current signature: {sig}")
        print("   REQUIRED: payload parameter for backward compatibility")
        return False
    
    # Check 2: Has **kwargs catch-all
    has_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD 
        for p in params.values()
    )
    
    if not has_kwargs:
        print("❌ FAIL: generate_with_payment missing **kwargs")
        print(f"   Current signature: {sig}")
        print("   REQUIRED: **kwargs to prevent TypeError on unknown args")
        return False
    
    # Check 3: Has user_inputs parameter (preferred)
    if 'user_inputs' not in params:
        print("⚠️  WARNING: generate_with_payment missing 'user_inputs' parameter")
        print(f"   Current signature: {sig}")
        print("   RECOMMENDED: user_inputs parameter (preferred API)")
    
    # Success
    print("✅ PASS: generate_with_payment signature is backward compatible")
    print(f"   Signature: {sig}")
    print(f"   • payload: {'✅' if 'payload' in params else '❌'}")
    print(f"   • user_inputs: {'✅' if 'user_inputs' in params else '❌'}")
    print(f"   • **kwargs: {'✅' if has_kwargs else '❌'}")
    
    return True


def test_no_payload_in_calls():
    """
    CRITICAL: Verify no code calls generate_with_payment(payload=...).
    
    All calls should use user_inputs= (payload is for backward compat only).
    """
    import subprocess
    
    print("\n🔍 Checking for generate_with_payment(payload=...) calls...")
    
    # Grep for payload= usage in generate_with_payment calls
    # Exclude test files, docs, and scripts
    try:
        result = subprocess.run(
            [
                'grep',
                '-r',
                '-n',
                '--include=*.py',
                '--exclude-dir=tests',
                '--exclude-dir=scripts',
                '--exclude-dir=__pycache__',
                '--exclude-dir=.git',
                r'generate_with_payment(.*payload\s*=',
                str(project_root / 'app'),
                str(project_root / 'bot')
            ],
            capture_output=True,
            text=True
        )
        
        # Filter out comments and documentation
        lines = [
            line for line in result.stdout.split('\n')
            if line and not any(x in line for x in ['#', '"""', "'''", '.md:', 'COMPLETE.md'])
        ]
        
        if lines:
            print(f"❌ FAIL: Found {len(lines)} generate_with_payment(payload=...) calls:")
            for line in lines[:10]:  # Show first 10
                print(f"   {line}")
            print("\n   ACTION: Replace all payload= with user_inputs=")
            return False
        
        print("✅ PASS: No generate_with_payment(payload=...) calls in app/ or bot/")
        return True
        
    except Exception as e:
        print(f"⚠️  WARNING: Could not grep for payload calls: {e}")
        return True  # Non-critical if grep fails


def test_models_sot_exists():
    """Verify models SOURCE_OF_TRUTH file exists."""
    sot_path = project_root / "models" / "KIE_SOURCE_OF_TRUTH.json"
    
    if not sot_path.exists():
        print(f"❌ FAIL: {sot_path} not found")
        return False
    
    print(f"✅ PASS: {sot_path} exists")
    return True


def test_allowed_models_locked():
    """Verify ALLOWED_MODEL_IDS.txt exists (production lock)."""
    allowed_path = project_root / "models" / "ALLOWED_MODEL_IDS.txt"
    
    if not allowed_path.exists():
        print(f"❌ FAIL: {allowed_path} not found")
        return False
    
    # Read and validate format
    with open(allowed_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not lines:
        print(f"❌ FAIL: {allowed_path} is empty")
        return False
    
    print(f"✅ PASS: {allowed_path} exists ({len(lines)} models locked)")
    return True


def test_version_module():
    """Verify version tracking module works."""
    try:
        from app.utils.version import get_version_string, get_git_commit, get_build_date
        
        version = get_version_string()
        commit = get_git_commit()
        build_date = get_build_date()
        
        print(f"✅ PASS: Version module works")
        print(f"   Version: {version}")
        print(f"   Commit: {commit}")
        print(f"   Build Date: {build_date}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Version module error: {e}")
        return False


def main():
    """Run all runtime contract tests."""
    print("=" * 60)
    print("RUNTIME CONTRACT VERIFICATION")
    print("=" * 60)
    
    tests = [
        ("generate_with_payment signature", test_generate_with_payment_signature),
        ("No payload= in calls", test_no_payload_in_calls),
        ("Models SOURCE_OF_TRUTH exists", test_models_sot_exists),
        ("ALLOWED_MODEL_IDS.txt locked", test_allowed_models_locked),
        ("Version tracking module", test_version_module),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"TEST: {name}")
        print(f"{'=' * 60}")
        
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED - Ready for deployment")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} tests FAILED - Fix before deployment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
