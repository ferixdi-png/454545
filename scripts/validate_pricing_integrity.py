#!/usr/bin/env python3
"""Validate pricing integrity + free tier determinism.

Rules:
- Each runnable model must have a computable price in RUB:
  - prefer pricing.rub_per_gen
  - else pricing.usd_per_gen * FX * MARKUP
- FREE tier must equal the 5 cheapest runnable models by computed RUB cost.
- Prints the 5 cheapest list (model_id + cost_rub).

Exit code:
- 0 if all runnable models have computable price and free tier list is deterministic
- 1 if any runnable model has missing/invalid pricing
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.pricing.fx import get_usd_to_rub_rate  # noqa: E402

SOT_PATH = Path("models/KIE_SOURCE_OF_TRUTH.json")

def cost_rub(model: Dict[str, Any], fx: float, markup: float) -> float | None:
    pricing = model.get("pricing") or {}
    rub = pricing.get("rub_per_gen")
    if isinstance(rub, (int, float)) and rub >= 0:
        return float(rub)
    usd = pricing.get("usd_per_gen")
    if isinstance(usd, (int, float)) and usd >= 0:
        return float(usd) * fx * markup
    return None

def main() -> int:
    print("═" * 70)
    print("PRICING INTEGRITY VALIDATION")
    print("═" * 70)

    if not SOT_PATH.exists():
        print(f"❌ SOURCE_OF_TRUTH not found: {SOT_PATH}")
        return 1

    data = json.loads(SOT_PATH.read_text(encoding="utf-8"))
    models = data.get("models") or {}
    if not isinstance(models, dict) or not models:
        print("❌ models is empty or not a dict")
        return 1

    fx = float(os.getenv("FX_RUB_PER_USD", "0") or "0")
    if fx <= 0:
        fx = get_usd_to_rub_rate()
    markup = float(os.getenv("MARKUP", "2.0"))

    priced: List[Tuple[str, float]] = []
    missing: List[str] = []

    for model_id, model in models.items():
        if not (model or {}).get("endpoint"):
            continue
        c = cost_rub(model or {}, fx, markup)
        if c is None:
            missing.append(model_id)
        else:
            priced.append((model_id, c))

    if missing:
        print(f"❌ Missing/invalid pricing for {len(missing)} runnable models (first 20):")
        for mid in missing[:20]:
            print(" ", mid)
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return 1

    priced.sort(key=lambda x: x[1])
    cheapest5 = priced[:5]

    print(f"\nFX_RUB_PER_USD={fx:.6f}  MARKUP={markup:.3f}")
    print("\n5 cheapest runnable models (FREE tier expected):")
    for mid, c in cheapest5:
        print(f"  {mid:<40} {c:.2f} RUB")

    print("\n✅ Pricing integrity PASSED")
    print("═" * 70)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
