#!/usr/bin/env python3
"""Single entrypoint readiness check.

Runs:
- startup validation (pure, no telegram)
- pricing integrity validation
- dry-run payload validation
- tests (pytest)

Exit code: non-zero on first failure.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def run(cmd: list[str]) -> int:
    print("\n$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if p.returncode != 0:
        print(f"\n❌ FAILED: {' '.join(cmd)} (code={p.returncode})")
    return p.returncode

def main() -> int:
    print("═" * 70)
    print("CHECK READY")
    print("═" * 70)

    # 1) Startup validation (should raise on failure)
    try:
        from app.utils.startup_validation import validate_startup  # noqa: E402
        validate_startup()
        print("✅ Startup validation: PASSED")
    except Exception as e:
        print(f"❌ Startup validation FAILED: {type(e).__name__}: {e}")
        return 1

    # 2) Pricing integrity
    rc = run([sys.executable, "scripts/validate_pricing_integrity.py"])
    if rc != 0:
        return rc

    # 3) Dry-run payloads
    rc = run([sys.executable, "scripts/dry_run_validate_payloads.py"])
    if rc != 0:
        return rc

    # 4) Tests
    rc = run([sys.executable, "-m", "pytest", "-q"])
    if rc != 0:
        return rc

    print("\n✅ ALL READY CHECKS PASSED")
    print("═" * 70)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
