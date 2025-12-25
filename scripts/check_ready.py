#!/usr/bin/env python3
"""
Single entrypoint to validate repository readiness (no "report theater").

Exits non-zero on any failure.
Intended for CI, Codespaces and local quick checks.
"""
import subprocess
import sys

def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    p = subprocess.run(cmd)
    return p.returncode

def main() -> int:
    # 1) pricing + free tier integrity
    rc = run([sys.executable, "scripts/validate_pricing_integrity.py"])
    if rc != 0:
        return rc

    # 2) startup validation (no telegram)
    rc = run([sys.executable, "-c", "from app.utils.startup_validation import validate_startup; validate_startup()"])
    if rc != 0:
        return rc

    # 3) run lightweight tests if available
    rc = run(["pytest", "-q"])
    if rc != 0:
        print("pytest failed (or not installed). Fix tests or install deps.")
        return rc

    print("\n✅ READY CHECK PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
