#!/usr/bin/env python3
"""
Run all verification scripts in sequence.
Exits on first failure.
"""
import subprocess
import sys

def run_check(name: str, script: str) -> bool:
    """Run single check script."""
    print(f"\n{'='*70}")
    print(f"▶️  {name}")
    print(f"{'='*70}")
    
    result = subprocess.run(
        ['python', script],
        cwd='.',
        capture_output=False
    )
    
    if result.returncode != 0:
        print(f"\n❌ {name} FAILED (exit {result.returncode})")
        return False
    
    print(f"\n✅ {name} PASSED")
    return True

def main():
    checks = [
        ("Project Verification", "scripts/verify_project.py"),
        ("SOURCE_OF_TRUTH Validation", "scripts/validate_source_of_truth.py"),
        ("Dry-run Payload Validation", "scripts/dry_run_validate_payloads.py"),
    ]
    
    print("🚀 Running all verification checks...")
    
    for name, script in checks:
        if not run_check(name, script):
            print("\n" + "="*70)
            print("❌ CHECK SUITE FAILED")
            print("="*70)
            return 1
    
    print("\n" + "="*70)
    print("✅ ALL CHECKS PASSED")
    print("="*70)
    return 0

if __name__ == "__main__":
    sys.exit(main())
