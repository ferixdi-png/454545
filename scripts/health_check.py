#!/usr/bin/env python3
"""
Project health check - comprehensive status report.
"""
import json
import subprocess
import sys
from pathlib import Path

def check_source_of_truth():
    """Check SOURCE_OF_TRUTH status."""
    print("\n📦 SOURCE_OF_TRUTH Status")
    print("-" * 70)
    
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not sot_path.exists():
        print("❌ Not found")
        return False
    
    data = json.loads(sot_path.read_text())
    models = data.get('models', {})
    
    # Count schemas
    with_schema = sum(1 for m in models.values() if m.get('input_schema', {}).get('properties'))
    empty_schema = len(models) - with_schema
    
    # Count pricing
    with_pricing = sum(1 for m in models.values() 
                      if m.get('pricing', {}).get('usd_per_gen') is not None)
    
    print(f"✅ Total models: {len(models)}")
    print(f"✅ Version: {data.get('version')}")
    print(f"✅ With pricing: {with_pricing}/{len(models)}")
    print(f"⚠️  With input_schema: {with_schema}/{len(models)}")
    print(f"⚠️  Empty schemas: {empty_schema}/{len(models)}")
    
    return True

def check_verifications():
    """Run verification scripts."""
    print("\n🔍 Verification Scripts")
    print("-" * 70)
    
    result = subprocess.run(
        ["python", "scripts/check_all.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ All verifications passed")
        return True
    else:
        print("⚠️  Some verifications failed")
        print(result.stdout[-200:] if len(result.stdout) > 200 else result.stdout)
        return False

def check_tests():
    """Run quick tests."""
    print("\n🧪 Unit Tests")
    print("-" * 70)
    
    result = subprocess.run(
        ["pytest", "-q", "--tb=no", "tests/test_pricing.py", "tests/test_cheapest_models.py"],
        capture_output=True,
        text=True
    )
    
    # Parse output
    output = result.stdout + result.stderr
    if "passed" in output:
        passed = output.split("passed")[0].strip().split()[-1]
        print(f"✅ Passed: {passed} tests")
        return True
    else:
        print("⚠️  Tests had issues")
        print(output[-200:])
        return False

def check_env():
    """Check environment setup."""
    print("\n⚙️  Environment")
    print("-" * 70)
    
    env_path = Path(".env")
    if env_path.exists():
        print("✅ .env file exists")
    else:
        print("⚠️  .env file missing (OK for CI)")
    
    # Check Python version
    import sys
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check key packages
    try:
        import aiogram
        print(f"✅ aiogram {aiogram.__version__}")
    except ImportError:
        print("❌ aiogram not installed")
    
    return True

def check_docs():
    """Check documentation completeness."""
    print("\n📚 Documentation")
    print("-" * 70)
    
    docs = {
        "README.md": "Main documentation",
        "QUICK_START_DEV.md": "Developer quickstart",
        "CONTRIBUTING.md": "Contribution guidelines",
        "DEPLOYMENT.md": "Production deployment",
    }
    
    for doc, desc in docs.items():
        if Path(doc).exists():
            print(f"✅ {doc:<25} {desc}")
        else:
            print(f"⚠️  {doc:<25} Missing")
    
    return True

def main():
    """Main health check."""
    print("=" * 70)
    print("🏥 PROJECT HEALTH CHECK")
    print("=" * 70)
    
    checks = [
        check_source_of_truth,
        check_verifications,
        check_tests,
        check_env,
        check_docs,
    ]
    
    results = [check() for check in checks]
    
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All checks passed ({passed}/{total})")
        print("\n🎉 Project is healthy!")
    else:
        print(f"⚠️  Some checks failed ({passed}/{total} passed)")
        print("\n💡 See details above")
    
    print("=" * 70)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
