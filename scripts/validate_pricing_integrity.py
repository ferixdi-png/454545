#!/usr/bin/env python3
"""Validate pricing consistency & FREE tier determinism.

Rules (project contract):
- Every enabled model must have a computable effective RUB price:
  rub_per_gen OR (usd_per_gen OR credits_per_gen) converted via FX + MARKUP
- Free tier = deterministic TOP-5 cheapest by effective rub_per_gen
- Sorting bucket (cheap->expensive) uses the same effective price

This script does NOT call Kie.ai (no credits).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple, List

ROOT = Path(__file__).resolve().parents[1]
SOT = ROOT / "models" / "KIE_SOURCE_OF_TRUTH.json"

def _num(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0

def _get_pricing(model: Dict[str, Any]) -> Dict[str, Any]:
    return model.get("pricing") or {}

def _effective_rub(model: Dict[str, Any], fx_rate: float, markup: float) -> Tuple[float, str]:
    p = _get_pricing(model)
    rub = _num(p.get("rub_per_gen") or p.get("rub_per_use"))
    if rub > 0:
        return rub, "rub_per_gen"
    usd = _num(p.get("usd_per_gen") or p.get("usd_per_use"))
    if usd > 0:
        return usd * fx_rate * markup, "usd->rub"
    credits = _num(p.get("credits_per_gen") or p.get("credits_per_use"))
    # If Kie uses credits and you have a fixed conversion in SoT, keep it in rub_per_gen.
    # Here we only validate 'computable': credits alone is NOT computable without a mapping.
    if credits > 0:
        return 0.0, "credits_only"
    return 0.0, "missing"

def main() -> int:
    if not SOT.exists():
        print(f"❌ Source of truth not found: {SOT}")
        return 1

    data = json.loads(SOT.read_text(encoding="utf-8"))
    models = data.get("models") or {}
    if not isinstance(models, dict):
        print("❌ Expected SoT V7 format: root.models must be a dict")
        return 1

    # FX + markup
    # Prefer env override to avoid external network in CI
    fx_rate = float(os.getenv("FX_RATE_RUB_USD", "0") or 0)
    markup = float(os.getenv("MARKUP", "2.0") or 2.0)

    # If FX not provided, try to import in-project FX module (may fetch online; acceptable locally)
    if fx_rate <= 0:
        try:
            from app.pricing.fx import get_fx_rate  # type: ignore
            fx_rate = float(get_fx_rate())
        except Exception as e:
            print(f"⚠️ Could not obtain FX rate from app.pricing.fx: {e}")
            print("   Set FX_RATE_RUB_USD env var to make this deterministic in CI.")
            fx_rate = 0.0

    if fx_rate <= 0:
        print("❌ FX rate is not available. Set FX_RATE_RUB_USD env var.")
        return 1

    priced: List[Tuple[str, float, str]] = []
    errors: List[str] = []

    for model_id, model in models.items():
        if not isinstance(model, dict):
            errors.append(f"{model_id}: invalid model object")
            continue
        enabled = model.get("enabled", True)
        if not enabled:
            continue
        rub, src = _effective_rub(model, fx_rate, markup)
        if rub <= 0:
            errors.append(f"{model_id}: no effective RUB price (source={src})")
            continue
        priced.append((model_id, rub, src))

    if errors:
        print("❌ Pricing integrity errors:")
        for e in errors[:50]:
            print(" -", e)
        if len(errors) > 50:
            print(f" ... and {len(errors)-50} more")
        return 1

    priced.sort(key=lambda t: t[1])
    top5 = priced[:5]

    print(f"✅ FX={fx_rate:.6f} RUB/USD, MARKUP={markup:.2f}")
    print("✅ TOP-5 cheapest (expected FREE tier):")
    for i, (mid, rub, src) in enumerate(top5, 1):
        print(f" {i:>2}. {mid}: {rub:.2f} RUB ({src})")

    # Optional cross-check with app.pricing.free_models if present
    try:
        from app.pricing.free_models import get_free_models  # type: ignore
        free = get_free_models()
        free_set = set(free)
        top_set = set([m for m, _, _ in top5])
        if free_set != top_set:
            print("❌ FREE tier mismatch between validate_pricing_integrity (TOP5) and app.pricing.free_models.get_free_models()")
            print("   TOP5 :", sorted(top_set))
            print("   FREE :", sorted(free_set))
            return 1
        print("✅ FREE tier matches app.pricing.free_models")
    except Exception as e:
        print(f"⚠️ Could not cross-check with app.pricing.free_models: {e}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
