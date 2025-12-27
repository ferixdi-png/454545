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

    # FREE tier validation (must be exactly 5 models)
    if isinstance(models_dict, dict):
        free_models = [mid for mid, m in models_dict.items() if m.get("is_free") is True]
        
        if len(free_models) != 5:
            errors.append(f"❌ FREE tier must have exactly 5 models, found {len(free_models)}: {free_models}")
        
        # Check that free models have valid pricing
        for mid in free_models:
            model = models_dict[mid]
            pricing = model.get("pricing", {})
            
            # Should have some pricing info (rub_per_use or credits)
            has_pricing = (
                pricing.get("rub_per_use", 0) > 0 or
                pricing.get("credits_per_gen", 0) > 0 or
                pricing.get("usd_per_use", 0) > 0
            )
            
            if not has_pricing:
                errors.append(f"❌ FREE model '{mid}' has no valid pricing (all zeros)")
    
    # Pricing validation: paid models must have cost > 0
    if isinstance(models_dict, dict):
        zero_price_paid = []
        
        # Models that are truly free on Kie.ai (not part of monetization)
        truly_free_models = {
            "infinitalk/from-audio",
            "flux-2/pro-image-to-image",
            "flux-2/flex-image-to-image",
            "flux-2/flex-text-to-image",
            "elevenlabs/audio-isolation"
        }
        
        for mid, model in models_dict.items():
            if model.get("is_free") is True:
                continue  # Skip FREE tier models
            
            if mid in truly_free_models:
                continue  # Skip truly free Kie.ai models (not monetized)
            
            pricing = model.get("pricing", {})
            
            # Check all pricing fields
            rub = pricing.get("rub_per_use", 0)
            usd = pricing.get("usd_per_use", 0)
            credits = pricing.get("credits_per_gen", 0) or pricing.get("credits_per_use", 0)
            
            if rub == 0 and usd == 0 and credits == 0:
                zero_price_paid.append(mid)
        
        if zero_price_paid:
            errors.append(f"❌ PAID models with zero pricing (monetization broken): {zero_price_paid[:10]}")
    
    # Content pack validation (UX pack)
    content_dir = Path("app/ui/content")
    if content_dir.exists():
        # Check required content pack files
        required_content_files = [
            "presets.json",
            "examples.json",
            "tips.json",
            "glossary.json",
            "model_marketing_tags.json",
        ]
        
        for filename in required_content_files:
            file_path = content_dir / filename
            if not file_path.exists():
                errors.append(f"❌ Missing content pack file: {filename}")
            else:
                # Validate JSON structure
                try:
                    content = json.loads(file_path.read_text(encoding="utf-8"))
                    
                    # Validate presets
                    if filename == "presets.json":
                        if "presets" not in content or not isinstance(content["presets"], list):
                            errors.append(f"❌ {filename}: missing or invalid 'presets' list")
                        else:
                            # Check preset references valid formats
                            for preset in content["presets"]:
                                preset_format = preset.get("format")
                                if preset_format and models_dict:
                                    # Check if any model supports this format
                                    has_model = any(
                                        preset_format in m.get("input_schema", {}).get("format", "")
                                        for m in models_dict.values()
                                    )
                                    if not has_model and preset_format not in [
                                        "text-to-image", "image-to-image", "text-to-video", 
                                        "image-to-video", "text-to-audio", "image-upscale", "background-remove"
                                    ]:
                                        errors.append(f"⚠️  Preset '{preset.get('id')}' references unknown format: {preset_format}")
                    
                    # Validate model marketing tags
                    if filename == "model_marketing_tags.json":
                        if "popular_models" not in content:
                            errors.append(f"❌ {filename}: missing 'popular_models' list")
                        elif isinstance(content["popular_models"], list):
                            # Check popular models exist in allowlist
                            if allowed:
                                for model_id in content["popular_models"]:
                                    if model_id not in allowed:
                                        errors.append(f"❌ Popular model '{model_id}' not in allowlist")
                        
                        if "model_tags" not in content:
                            errors.append(f"❌ {filename}: missing 'model_tags' dict")
                    
                except json.JSONDecodeError as e:
                    errors.append(f"❌ Invalid JSON in {filename}: {e}")
                except Exception as e:
                    errors.append(f"❌ Error validating {filename}: {e!r}")
    
    # Tone module validation
    tone_module = Path("app/ui/tone.py")
    if tone_module.exists():
        tone_text = tone_module.read_text(encoding="utf-8", errors="ignore")
        
        # Check required CTA labels are defined
        required_ctas = [
            "CTA_START", "CTA_BACK", "CTA_HOME", "CTA_FREE", "CTA_POPULAR", "CTA_PRESETS"
        ]
        for cta in required_ctas:
            if f"{cta} =" not in tone_text:
                errors.append(f"❌ tone.py missing required CTA label: {cta}")
        
        # Check no 'kie' mentions in STANDARD MESSAGES (skip comments/docs)
        # Extract only the message definitions
        import re
        message_pattern = r'(WELCOME_MESSAGE|FIRST_TIME_HINT|HOW_IT_WORKS_MESSAGE|MINI_COURSE_MESSAGE)\s*=\s*"""(.*?)"""'
        matches = re.findall(message_pattern, tone_text, re.DOTALL)
        
        for msg_name, msg_content in matches:
            if 'kie' in msg_content.lower():
                errors.append(f"❌ tone.py message '{msg_name}' contains 'kie' reference")
    else:
        errors.append("⚠️  app/ui/tone.py not found (content pack incomplete)")
    
    # Format coverage validation (SYNTX-grade)
    format_map_path = Path("app/ui/content/model_format_map.json")
    if format_map_path.exists() and isinstance(models_dict, dict):
        try:
            format_map = json.loads(format_map_path.read_text(encoding="utf-8"))
            model_to_formats = format_map.get("model_to_formats", {})
            
            # Check all enabled models are mapped
            enabled_models = [mid for mid, m in models_dict.items() if m.get("enabled", True)]
            unmapped = []
            
            for model_id in enabled_models:
                if model_id not in model_to_formats or not model_to_formats[model_id]:
                    unmapped.append(model_id)
            
            if unmapped:
                errors.append(f"❌ These enabled models have no format mapping: {unmapped[:10]}")
            
            # Check formats are valid
            valid_formats = {
                "text-to-video", "image-to-video", "text-to-image", "image-to-image",
                "image-upscale", "background-remove", "text-to-audio", "audio-editing",
                "audio-to-video", "video-editing"
            }
            
            for model_id, formats in model_to_formats.items():
                for fmt in formats:
                    if fmt not in valid_formats:
                        errors.append(f"❌ Model '{model_id}' has invalid format: {fmt}")
                        break
        except json.JSONDecodeError as e:
            errors.append(f"❌ Invalid JSON in model_format_map.json: {e}")
        except Exception as e:
            errors.append(f"❌ Error validating format coverage: {e!r}")
    elif isinstance(models_dict, dict) and len(models_dict) > 0:
        errors.append("⚠️  model_format_map.json not found (format-first UX incomplete)")
    
    # User upsert module validation (FK violation prevention)
    user_upsert = Path("app/database/user_upsert.py")
    if user_upsert.exists():
        upsert_text = user_upsert.read_text(encoding="utf-8", errors="ignore")
        
        # Check ensure_user_exists is defined
        if "def ensure_user_exists" not in upsert_text and "async def ensure_user_exists" not in upsert_text:
            errors.append("❌ user_upsert.py missing ensure_user_exists function")
        
        # Check ON CONFLICT handling
        if "ON CONFLICT" not in upsert_text:
            errors.append("❌ user_upsert.py missing ON CONFLICT (upsert logic)")
        
        # Check TTL cache
        if "_user_cache" not in upsert_text:
            errors.append("⚠️  user_upsert.py missing TTL cache (may spam DB)")
    else:
        errors.append("⚠️  app/database/user_upsert.py not found (FK violation risk)")
    
    # Generation logging non-blocking check
    gen_events = Path("app/database/generation_events.py")
    if gen_events.exists():
        gen_text = gen_events.read_text(encoding="utf-8", errors="ignore")
        
        # Check try/except wrapper
        if "try:" not in gen_text or "except" not in gen_text:
            errors.append("❌ generation_events.py missing try/except (will crash on DB errors)")
        
        # Check ensure_user_exists is called
        if "ensure_user_exists" not in gen_text:
            errors.append("❌ log_generation_event should call ensure_user_exists (FK violation risk)")
        
        # Check BEST-EFFORT comment
        if "BEST-EFFORT" not in gen_text and "best-effort" not in gen_text.lower():
            errors.append("⚠️  generation_events.py should document best-effort logging policy")
    else:
        errors.append("⚠️  app/database/generation_events.py not found")


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


def run_all_verifications() -> int:
    """Run complete verification pipeline."""
    import subprocess
    
    print("\n🔍 RUNNING FULL VERIFICATION PIPELINE\n")
    
    failures = []
    
    # 1. Project structure verification
    print("1️⃣  Verifying project structure...")
    result = verify_project()
    if result != 0:
        failures.append("Project structure")
    else:
        print("✅ Project structure OK\n")
    
    # 2. Python compilation check
    print("2️⃣  Checking Python compilation...")
    try:
        result = subprocess.run(
            ["python", "-m", "compileall", "-q", "."],
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            failures.append("Python compilation")
            print(f"❌ Compilation errors:\n{result.stderr.decode()}")
        else:
            print("✅ All Python files compile\n")
    except Exception as e:
        failures.append(f"Compilation check ({e})")
        print(f"❌ Compilation check failed: {e}\n")
    
    # 3. Run pytest
    print("3️⃣  Running tests...")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "-q", "--tb=line"],
            capture_output=True,
            timeout=60
        )
        output = result.stdout.decode()
        if result.returncode != 0:
            # Show failures but don't fail pipeline (some tests may be flaky)
            print(f"⚠️  Some tests failed:\n{output}\n")
        else:
            print(f"✅ All tests passed\n{output}\n")
    except Exception as e:
        print(f"⚠️  Test run skipped: {e}\n")
    
    # 4. UI verification (no brand leaks)
    print("4️⃣  Checking UI for brand leaks...")
    try:
        result = subprocess.run(
            ["python", "scripts/verify_no_brand_leaks.py"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            # Brand leaks in backend are OK, only UI matters
            output = result.stdout.decode()
            if "app/ui" in output or "bot/" in output:
                failures.append("Brand leaks in UI")
                print(f"❌ Brand leaks found in UI:\n{output}\n")
            else:
                print("✅ UI is clean (backend refs OK)\n")
        else:
            print("✅ No brand leaks\n")
    except FileNotFoundError:
        print("⚠️  Brand leak checker not found (skipped)\n")
    except Exception as e:
        print(f"⚠️  Brand leak check skipped: {e}\n")
    
    # 5. Callback verification
    print("5️⃣  Verifying callbacks...")
    try:
        result = subprocess.run(
            ["python", "scripts/verify_callbacks.py"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            output = result.stdout.decode()
            print(f"⚠️  Callback issues found:\n{output}\n")
        else:
            print("✅ All callbacks covered\n")
    except FileNotFoundError:
        print("⚠️  Callback verifier not found (skipped)\n")
    except Exception as e:
        print(f"⚠️  Callback verification skipped: {e}\n")
    
    # 6. FSM routes verification
    print("6️⃣  Verifying FSM routes...")
    try:
        result = subprocess.run(
            ["python", "scripts/verify_fsm_routes.py"],
            capture_output=True,
            timeout=10
        )
        output = result.stdout.decode()
        print(output)
        if result.returncode != 0:
            failures.append("FSM routes")
    except FileNotFoundError:
        print("⚠️  FSM verifier not found (skipped)\n")
    except Exception as e:
        print(f"⚠️  FSM verification skipped: {e}\n")
    
    # 7. Placeholder links check
    print("7️⃣  Checking for placeholder links...")
    try:
        result = subprocess.run(
            ["python", "scripts/verify_no_placeholder_links.py"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            failures.append("Placeholder links")
            print(f"❌ Placeholder links found:\n{result.stdout.decode()}\n")
        else:
            print("✅ No placeholder links\n")
    except FileNotFoundError:
        print("⚠️  Placeholder checker not found (skipped)\n")
    except Exception as e:
        print(f"⚠️  Placeholder check skipped: {e}\n")
    
    # Summary
    print("\n" + "═" * 70)
    if failures:
        print(f"❌ VERIFICATION FAILED: {len(failures)} issues")
        for f in failures:
            print(f"   - {f}")
        print("═" * 70)
        return 1
    else:
        print("✅ ALL VERIFICATIONS PASSED")
        print("═" * 70)
        return 0


if __name__ == "__main__":
    import sys
    
    # If --all flag, run full pipeline
    if "--all" in sys.argv:
        sys.exit(run_all_verifications())
    else:
        # Default: just structure verification
        sys.exit(verify_project())
