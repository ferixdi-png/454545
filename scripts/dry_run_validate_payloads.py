#!/usr/bin/env python3
"""
Dry-run payload validation - build payloads for ALL runnable models WITHOUT real API calls.

Why:
- KIE_SOURCE_OF_TRUTH.json uses a custom input_schema format (not JSON Schema).
- examples can be curl strings; we must not rely on examples.

What this does:
- Loads models/KIE_SOURCE_OF_TRUTH.json
- For each model, generates minimal user_inputs from input_schema (required fields)
- Calls app.kie.builder.build_payload(model_id, user_inputs, sot)
- Reports ok/warn/error and exits non-zero on errors

No network calls. Safe to run locally and in CI.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

# Ensure repo root is on sys.path when running from scripts/
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.kie.builder import build_payload  # noqa: E402
from app.pricing.fx import get_usd_to_rub_rate  # noqa: E402

SOT_PATH = Path("models/KIE_SOURCE_OF_TRUTH.json")

def _pick_example(spec: Dict[str, Any]) -> Any:
    ex = spec.get("examples")
    if isinstance(ex, list) and ex:
        return ex[0]
    return None

def _normalize_type(t: Any) -> str:
    if isinstance(t, str):
        return t.lower()
    return str(t).lower()

def generate_user_inputs(model_id: str, input_schema: Dict[str, Any]) -> Tuple[Dict[str, Any], str | None]:
    """Generate minimal user_inputs for builder.build_payload.

    Returns: (user_inputs, warning_or_none)
    """
    if not isinstance(input_schema, dict) or not input_schema:
        return {}, "empty input_schema"

    user_inputs: Dict[str, Any] = {}
    warn: str | None = None

    # KIE V4/V6 wrapper format:
    # {model: {...}, callBackUrl: {...}, input: {type: dict, examples:[{prompt:..., ...}]}}
    # In this case, real user fields live inside input.examples[0] (dict) or input.properties.
    if "input" in input_schema and isinstance(input_schema.get("input"), dict):
        input_spec = input_schema.get("input") or {}
        if isinstance(input_spec.get("properties"), dict) and input_spec.get("properties"):
            # Use nested properties as the effective schema
            input_schema = input_spec["properties"]
        else:
            ex = input_spec.get("examples")
            if isinstance(ex, list) and ex and isinstance(ex[0], dict):
                example_dict = ex[0]
                # Convert example dict to minimal required schema: all keys required with example value
                input_schema = {
                    k: {"type": type(v).__name__.lower() if v is not None else "str", "required": True, "examples": [v]}
                    for k, v in example_dict.items()
                }


    for field_name, spec in input_schema.items():
        if not isinstance(spec, dict):
            # Sometimes schema can be direct values; skip
            continue

        required = bool(spec.get("required"))
        if not required:
            continue

        # Prefer explicit default
        if "default" in spec and spec.get("default") is not None:
            user_inputs[field_name] = spec["default"]
            continue

        # Prefer examples
        example = _pick_example(spec)
        if example is not None:
            user_inputs[field_name] = example
            continue

        t = _normalize_type(spec.get("type", "str"))

        # Reasonable fallbacks
        if field_name == "model":
            user_inputs[field_name] = model_id
        elif field_name.lower() in {"callbackurl", "callback_url"}:
            # Render/webhook callback isn't required for dry-run; put placeholder
            user_inputs[field_name] = os.getenv("CALLBACK_URL", "https://example.com/callback")
        elif t in {"str", "string"}:
            user_inputs[field_name] = "test"
        elif t in {"int", "integer", "number", "float"}:
            user_inputs[field_name] = 1
        elif t in {"bool", "boolean"}:
            user_inputs[field_name] = False
        elif t in {"dict", "object"}:
            user_inputs[field_name] = {}
            warn = warn or f"required dict field '{field_name}' had no example/default"
        elif t in {"list", "array"}:
            user_inputs[field_name] = []
            warn = warn or f"required list field '{field_name}' had no example/default"
        else:
            user_inputs[field_name] = "test"

    return user_inputs, warn

def compute_cost_rub(model: Dict[str, Any], fx: float, markup: float) -> float | None:
    pricing = model.get("pricing") or {}
    rub = pricing.get("rub_per_gen")
    if isinstance(rub, (int, float)):
        return float(rub)
    usd = pricing.get("usd_per_gen")
    if isinstance(usd, (int, float)):
        return float(usd) * fx * markup
    return None

def main() -> int:
    print("═" * 70)
    print("DRY-RUN PAYLOAD VALIDATION (no network)")
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

    ok = warn = err = 0
    warn_lines = []
    err_lines = []

    for model_id, model in models.items():
        endpoint = (model or {}).get("endpoint")
        if not endpoint:
            # Not runnable
            continue

        input_schema = (model or {}).get("input_schema") or {}
        user_inputs, w = generate_user_inputs(model_id, input_schema)

        # Cost computability check (not fatal here)
        cost_rub = compute_cost_rub(model or {}, fx, markup)
        if cost_rub is None:
            w = w or "pricing missing (cannot compute cost)"

        try:
            payload = build_payload(model_id, user_inputs, data)
            if not isinstance(payload, dict) or not payload:
                raise ValueError("payload is empty or not dict")
            ok += 1
            if w:
                warn += 1
                warn_lines.append(f"⚠️  {model_id}: {w}")
        except Exception as e:
            err += 1
            err_lines.append(f"❌ {model_id}: {type(e).__name__}: {e}")

    total = ok + err
    print(f"\n📊 Runnable models validated: {total}")
    print(f"✅ OK: {ok}")
    print(f"⚠️  WARN: {warn}")
    print(f"❌ ERROR: {err}\n")

    if err_lines:
        print("ERRORS (first 15):")
        for line in err_lines[:15]:
            print(" ", line)
        if len(err_lines) > 15:
            print(f"  ... and {len(err_lines) - 15} more")
        print()

    if warn_lines:
        print("WARNINGS (first 15):")
        for line in warn_lines[:15]:
            print(" ", line)
        if len(warn_lines) > 15:
            print(f"  ... and {len(warn_lines) - 15} more")
        print()

    if err > 0:
        print("❌ Dry-run FAILED")
        print("═" * 70)
        return 1

    print("✅ Dry-run PASSED")
    print("═" * 70)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
