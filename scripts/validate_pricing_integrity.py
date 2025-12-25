#!/usr/bin/env python3
"""Validate pricing and free-tier integrity."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

def fail(msg: str) -> None:
    raise SystemExit(f"❌ {msg}")

def validate(root: Path) -> None:
    sot = root / "models" / "KIE_SOURCE_OF_TRUTH.json"
    data = json.loads(sot.read_text(encoding="utf-8"))
    models: Dict[str, Any] = data.get("models", {})
    if not isinstance(models, dict):
        fail("models is not dict")

    from app.pricing.free_models import get_free_models
    from app.pricing.calc import model_effective_rub

    # compute effective prices
    priced: List[Tuple[str, float]] = []
    for mid, m in models.items():
        if not m.get("enabled", True):
            continue
        rub = model_effective_rub(m)
        if rub <= 0 and (mid.isupper() or "_processor" in mid.lower()):
            continue
        priced.append((mid, rub))

    if not priced:
        fail("No priced models found (enabled)")

    priced.sort(key=lambda x: (x[1] if x[1] > 0 else 10**12, x[0]))
    expected = [mid for mid,_ in priced[:5]]
    actual = get_free_models()

    if actual != expected:
        fail(f"FREE tier mismatch. expected={expected} actual={actual}")

    # Ensure every enabled model has pricing dict
    for mid, m in models.items():
        if not m.get("enabled", True):
            continue
        if not isinstance(m.get("pricing", {}), dict):
            fail(f"Model {mid} missing pricing dict")
    print(f"✅ Pricing integrity: FREE tier = TOP-5 cheapest: {actual}")

if __name__ == "__main__":
    validate(Path(__file__).resolve().parents[1])
