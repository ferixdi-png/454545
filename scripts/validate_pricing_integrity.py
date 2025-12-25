#!/usr/bin/env python3
"""
Validate pricing + free tier deterministically.

Checks:
- Can load models/KIE_SOURCE_OF_TRUTH.json
- Computes effective RUB prices for enabled models
- FREE tier equals TOP-5 cheapest by effective price
"""
import json
import sys
from pathlib import Path

from app.pricing.free_models import get_free_models, get_model_price_rub

SOURCE = Path("models/KIE_SOURCE_OF_TRUTH.json")

def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: missing {SOURCE}")
        return 2
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    models = (data.get("models", {}) or {})
    enabled = {mid: m for mid, m in models.items() if (m or {}).get("enabled", True)}

    priced = []
    missing = []
    for mid in enabled.keys():
        rub = get_model_price_rub(mid)
        if rub is None:
            missing.append(mid)
            continue
        priced.append((mid, float(rub)))

    if not priced:
        print("ERROR: no priced enabled models")
        return 3

    priced.sort(key=lambda x: x[1])
    expected = [mid for mid, _ in priced[:5]]
    actual = get_free_models(limit=5)

    print(f"Enabled models: {len(enabled)}")
    print(f"Priced models:  {len(priced)}")
    if missing:
        print(f"Missing price:  {len(missing)} (these won't be runnable/cheap-sorted): {', '.join(missing[:20])}")

    print("\nTop-10 cheapest (effective RUB):")
    for mid, rub in priced[:10]:
        tag = "FREE" if mid in actual else ""
        print(f" - {mid}: {rub:.4f} {tag}")

    if actual != expected:
        print("\nERROR: FREE tier mismatch")
        print("Expected TOP-5:", expected)
        print("Actual   TOP-5:", actual)
        return 4

    print("\n✅ Pricing integrity OK. FREE tier matches TOP-5 cheapest.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
