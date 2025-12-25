#!/usr/bin/env python3
"""Single entrypoint readiness check (no Render required).

Runs a deterministic set of validations to prevent 'green logs but broken bot'.

Exit codes:
- 0: all checks passed
- 1: at least one check failed
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    ("verify_project", [sys.executable, "scripts/verify_project.py"]),
    ("validate_source_of_truth", [sys.executable, "scripts/validate_source_of_truth.py"]),
    ("validate_pricing_integrity", [sys.executable, "scripts/validate_pricing_integrity.py"]),
    ("dry_run_validate_payloads", [sys.executable, "scripts/dry_run_validate_payloads.py"]),
]

def run(name: str, cmd: list[str]) -> int:
    print(f"\n=== {name} ===")
    p = subprocess.run(cmd, cwd=str(ROOT))
    return p.returncode

def main() -> int:
    failed = []
    for name, cmd in CHECKS:
        rc = run(name, cmd)
        if rc != 0:
            failed.append((name, rc))
            break  # fail fast
    if failed:
        name, rc = failed[0]
        print(f"\n❌ READY CHECK FAILED: {name} (exit={rc})")
        return 1
    print("\n✅ READY CHECK PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
