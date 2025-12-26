#!/usr/bin/env python3
"""
Verify project invariants.

Hard invariants (production):
- models/ALLOWED_MODEL_IDS.txt is the canonical allowlist
- allowlist must contain exactly 42 unique model_ids
- models/KIE_SOURCE_OF_TRUTH.json must contain exactly those 42 model_ids (1:1)
- critical runtime entrypoint main_render.py must import aiogram Bot/Dispatcher
- required env vars must be documented
- pricing functions must not crash
- webhook endpoints must be defined
"""
import json
import os
import sys
from pathlib import Path

def load_allowed_model_ids() -> list[str]:
    p = Path("models/ALLOWED_MODEL_IDS.txt")
    if not p.exists():
        return []
    ids: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        ids.append(s)
    # dedup preserve order
    seen = set()
    out: list[str] = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out

def verify_project() -> int:
    errors: list[str] = []

    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not sot_path.exists():
        errors.append("❌ Missing models/KIE_SOURCE_OF_TRUTH.json")
    else:
        try:
            sot_raw = json.loads(sot_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"❌ Failed to parse models/KIE_SOURCE_OF_TRUTH.json: {e!r}")
            sot_raw = None

    allowed = load_allowed_model_ids()
    if not allowed:
        errors.append("❌ ALLOWED_MODEL_IDS.txt missing or empty")
    else:
        if len(allowed) != 42:
            errors.append(f"❌ Allowlist must contain exactly 42 unique ids, got {len(allowed)}")
        if len(set(allowed)) != len(allowed):
            errors.append("❌ Allowlist contains duplicates (should be deduped already)")

    models_dict = None
    if isinstance(sot_raw, dict):
        if "models" in sot_raw and isinstance(sot_raw.get("models"), dict):
            models_dict = sot_raw["models"]
        elif all(isinstance(v, dict) for v in sot_raw.values()):
            # fallback legacy
            models_dict = sot_raw
        else:
            errors.append("❌ SOURCE_OF_TRUTH invalid structure: expected {'models': {...}}")
    elif sot_raw is not None:
        errors.append(f"❌ SOURCE_OF_TRUTH must be dict, got {type(sot_raw)}")

    # strict allowlist match
    if allowed and isinstance(models_dict, dict):
        keys = list(models_dict.keys())
        if set(keys) != set(allowed):
            extra = sorted(list(set(keys) - set(allowed)))[:10]
            missing = sorted(list(set(allowed) - set(keys)))[:10]
            errors.append(f"❌ SOURCE_OF_TRUTH model_ids must match allowlist 1:1. extra={extra} missing={missing}")

    # validate model schemas
    if isinstance(models_dict, dict):
        for model_id, model in models_dict.items():
            if not isinstance(model_id, str) or not model_id.strip():
                errors.append(f"❌ Invalid model_id: {repr(model_id)}")
                continue
            if not isinstance(model, dict):
                errors.append(f"❌ Model {model_id} is not dict: {type(model)}")
                continue

            endpoint = model.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint.strip():
                errors.append(f"❌ {model_id}: missing/invalid 'endpoint'")

            input_schema = model.get("input_schema")
            if not isinstance(input_schema, dict):
                errors.append(f"❌ {model_id}: missing/invalid 'input_schema' (dict required)")

            pricing = model.get("pricing")
            if not isinstance(pricing, dict):
                errors.append(f"❌ {model_id}: missing/invalid 'pricing' (dict required)")

            tags = model.get("tags")
            if tags is not None and not isinstance(tags, list):
                errors.append(f"❌ {model_id}: 'tags' must be list if present")

            # UI example prompts help avoid empty UX
            uiex = model.get("ui_example_prompts")
            if uiex is not None and not isinstance(uiex, list):
                errors.append(f"❌ {model_id}: 'ui_example_prompts' must be list if present")

    # entrypoint sanity
    mr = Path("main_render.py")
    if not mr.exists():
        errors.append("❌ Missing main_render.py")
    else:
        mr_text = mr.read_text(encoding="utf-8", errors="ignore")
        if "from aiogram import Bot, Dispatcher" not in mr_text:
            errors.append("❌ main_render.py must import: from aiogram import Bot, Dispatcher")
        if "DefaultBotProperties" not in mr_text or "ParseMode" not in mr_text:
            errors.append("❌ main_render.py must import DefaultBotProperties and ParseMode (aiogram v3)")
        # logger must be defined at module import time (Render crash guard)
        if "logger =" not in mr_text:
            errors.append("❌ main_render.py must define module-level 'logger' (logging.getLogger)")
        if "from app.utils.healthcheck" not in mr_text:
            errors.append("❌ main_render.py must import app.utils.healthcheck (start/stop/set_health_state)")
        if "from app.utils.startup_validation" not in mr_text:
            errors.append("❌ main_render.py must import app.utils.startup_validation (validate_startup)")

    # requirements sanity
    req = Path("requirements.txt")
    if req.exists():
        req_text = req.read_text(encoding="utf-8", errors="ignore").lower()
        if "aiogram" not in req_text:
            errors.append("❌ requirements.txt must include aiogram")
    else:
        errors.append("❌ Missing requirements.txt")

    # Repository health check
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/check_repo_health.py"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append("❌ Repository health check failed (large files or forbidden directories in git)")
            # Show first few lines of error
            error_lines = result.stdout.strip().split('\n')
            for line in error_lines[-5:]:  # Last 5 lines usually have the errors
                if '❌' in line:
                    errors.append(f"   {line}")
    except Exception as e:
        errors.append(f"⚠️  Repository health check skipped: {e}")

    # ENV vars check (required for production)
    required_env_vars = [
        "TELEGRAM_BOT_TOKEN",
        "KIE_API_KEY",
        "ADMIN_ID",
    ]
    
    optional_but_recommended = [
        "DATABASE_URL",  # For persistence
        "WEBHOOK_BASE_URL",  # For webhook mode
        "TELEGRAM_WEBHOOK_SECRET_TOKEN",  # For webhook security
    ]
    
    # Check if env vars are documented (in README or config example)
    env_example = Path("config.json.example")
    readme = Path("README.md")
    
    if readme.exists():
        readme_text = readme.read_text(encoding="utf-8", errors="ignore")
        for var in required_env_vars:
            if var not in readme_text:
                errors.append(f"⚠️  Required env var '{var}' not documented in README.md")
    else:
        errors.append("❌ README.md missing")

    # Webhook endpoints check
    webhook_server = Path("app/webhook_server.py")
    if webhook_server.exists():
        ws_text = webhook_server.read_text(encoding="utf-8", errors="ignore")
        
        # Check healthz endpoint
        if '/healthz' not in ws_text:
            errors.append("❌ Webhook server missing /healthz endpoint (liveness probe)")
        
        # Check readyz endpoint
        if '/readyz' not in ws_text:
            errors.append("❌ Webhook server missing /readyz endpoint (readiness probe)")
        
        # Check secret validation
        if 'secret_guard' not in ws_text and 'X-Telegram-Bot-Api-Secret-Token' not in ws_text:
            errors.append("⚠️  Webhook server missing secret token validation (security risk)")
    else:
        errors.append("❌ app/webhook_server.py missing")

    # Pricing module check (must not crash on import)
    try:
        # Temporarily set env vars to avoid errors
        os.environ.setdefault("KIE_API_KEY", "test_key_for_verification")
        os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
        
        from app.payments.pricing import calculate_kie_cost, calculate_user_price, format_price_rub
        
        # Test basic pricing functions don't crash
        test_model = {
            "model_id": "test",
            "pricing": {"credits_per_use": 100}
        }
        
        try:
            kie_cost = calculate_kie_cost(test_model, {}, None)
            user_price = calculate_user_price(kie_cost)
            formatted = format_price_rub(user_price)
            
            if not isinstance(kie_cost, (int, float)):
                errors.append(f"❌ calculate_kie_cost returned invalid type: {type(kie_cost)}")
            if not isinstance(user_price, (int, float)):
                errors.append(f"❌ calculate_user_price returned invalid type: {type(user_price)}")
            if not isinstance(formatted, str):
                errors.append(f"❌ format_price_rub returned invalid type: {type(formatted)}")
        except Exception as e:
            errors.append(f"❌ Pricing functions crashed: {e!r}")
            
    except ImportError as e:
        errors.append(f"❌ Failed to import pricing module: {e!r}")
    except Exception as e:
        errors.append(f"⚠️  Pricing module check skipped: {e!r}")

    print("═" * 70)
    print("PROJECT VERIFICATION")
    print("═" * 70)
    if errors:
        for e in errors:
            print(e)
        print("═" * 70)
        print("❌ Verification FAILED")
        return 1
    print("✅ All critical checks passed!")
    print("═" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(verify_project())
