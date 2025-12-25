#!/usr/bin/env python3
"""Project readiness check (fast, deterministic).

This script is the single 'definition of done' gate for CI and manual runs.

It does NOT hit Telegram or Kie.ai network.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOT = ROOT / "models" / "KIE_SOURCE_OF_TRUTH.json"

def fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)

def ok(msg: str) -> None:
    print(f"✅ {msg}")

def main() -> None:
    # Core files
    for p in ["Dockerfile", "requirements.txt", "main_render.py"]:
        if not (ROOT / p).exists():
            fail(f"Missing {p} in repo root")
    ok("Core files present")

    if not SOT.exists():
        fail("models/KIE_SOURCE_OF_TRUTH.json missing")
    data = json.loads(SOT.read_text(encoding="utf-8"))
    models = data.get("models", {})
    if not isinstance(models, dict) or not models:
        fail("Source-of-truth has no models")
    enabled = {mid:m for mid,m in models.items() if m.get("enabled", True)}
    ok(f"Source-of-truth loaded: {len(models)} total, {len(enabled)} enabled")

    # Pricing integrity
    from scripts.validate_pricing_integrity import validate
    validate(ROOT)

    ok("READY CHECK PASSED")

if __name__ == "__main__":
    main()
