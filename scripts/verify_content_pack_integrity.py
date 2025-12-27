#!/usr/bin/env python3
"""Verify content pack integrity (presets, referral rewards, layout usage)."""
import json
import sys
from pathlib import Path


def verify_referral_rewards():
    """Verify referral_rewards.json schema."""
    errors = []
    
    rewards_file = Path("app/ui/content/referral_rewards.json")
    
    if not rewards_file.exists():
        errors.append("❌ referral_rewards.json not found")
        return errors
    
    try:
        data = json.loads(rewards_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"❌ Invalid JSON in referral_rewards.json: {e}")
        return errors
    
    # Check required keys
    if "tiers" not in data:
        errors.append("❌ referral_rewards.json missing 'tiers'")
    elif not isinstance(data["tiers"], list):
        errors.append("❌ 'tiers' must be list")
    else:
        # Validate tiers
        for i, tier in enumerate(data["tiers"]):
            if "referrals_needed" not in tier:
                errors.append(f"❌ Tier {i} missing 'referrals_needed'")
            if "reward_amount" not in tier:
                errors.append(f"❌ Tier {i} missing 'reward_amount'")
            if "title" not in tier:
                errors.append(f"❌ Tier {i} missing 'title'")
    
    if "share_templates" not in data:
        errors.append("❌ referral_rewards.json missing 'share_templates'")
    elif not isinstance(data["share_templates"], list):
        errors.append("❌ 'share_templates' must be list")
    
    if "referral_bonus_per_user" not in data:
        errors.append("❌ referral_rewards.json missing 'referral_bonus_per_user'")
    
    return errors


def verify_presets_references():
    """Verify presets reference valid formats."""
    errors = []
    
    presets_file = Path("app/ui/content/presets.json")
    
    if not presets_file.exists():
        errors.append("⚠️  presets.json not found (skipping)")
        return errors
    
    try:
        data = json.loads(presets_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"❌ Invalid JSON in presets.json: {e}")
        return errors
    
    valid_formats = [
        "text-to-image",
        "image-to-image",
        "text-to-video",
        "image-to-video",
        "text-to-audio",
        "audio-to-audio",
        "image-upscale",
        "background-remove",
    ]
    
    if "presets" in data:
        for preset in data["presets"]:
            preset_format = preset.get("format")
            if preset_format and preset_format not in valid_formats:
                errors.append(f"❌ Preset '{preset.get('id')}' has invalid format: {preset_format}")
    
    return errors


def verify_layout_usage():
    """Basic check that layout.py is imported in key UI files."""
    errors = []
    
    layout_file = Path("app/ui/layout.py")
    
    if not layout_file.exists():
        errors.append("❌ app/ui/layout.py not found")
        return errors
    
    # Check that layout exports expected functions
    layout_text = layout_file.read_text(encoding="utf-8", errors="ignore")
    
    required_exports = [
        "def render_screen(",
        "def success_panel(",
        "def progress_message(",
        "def error_recovery(",
    ]
    
    for export in required_exports:
        if export not in layout_text:
            errors.append(f"❌ layout.py missing export: {export}")
    
    # Check that some UI modules import layout (basic check)
    ui_dir = Path("app/ui")
    if ui_dir.exists():
        ui_files = list(ui_dir.glob("*.py"))
        
        imports_layout = False
        for ui_file in ui_files:
            if ui_file.name in ["layout.py", "__init__.py"]:
                continue
            
            content = ui_file.read_text(encoding="utf-8", errors="ignore")
            if "from app.ui.layout import" in content or "from app.ui import layout" in content:
                imports_layout = True
                break
        
        if not imports_layout:
            errors.append("⚠️  No UI modules import layout.py yet (expected after integration)")
    
    return errors


def verify_tone_module():
    """Verify tone.py has required CTA labels."""
    errors = []
    
    tone_file = Path("app/ui/tone.py")
    
    if not tone_file.exists():
        errors.append("❌ app/ui/tone.py not found")
        return errors
    
    tone_text = tone_file.read_text(encoding="utf-8", errors="ignore")
    
    required_ctas = [
        "CTA_START",
        "CTA_BACK",
        "CTA_HOME",
        "CTA_FREE",
        "CTA_POPULAR",
        "CTA_PRESETS",
        "CTA_RETRY",
    ]
    
    for cta in required_ctas:
        if f"{cta} =" not in tone_text:
            errors.append(f"❌ tone.py missing CTA: {cta}")
    
    return errors


def verify_all():
    """Run all content pack verifications."""
    print("=" * 70)
    print("CONTENT PACK INTEGRITY VERIFICATION")
    print("=" * 70)
    
    all_errors = []
    
    # 1. Referral rewards
    print("\n1️⃣  Verifying referral_rewards.json...")
    errors = verify_referral_rewards()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   {e}")
    else:
        print("   ✅ referral_rewards.json OK")
    
    # 2. Presets references
    print("\n2️⃣  Verifying presets references...")
    errors = verify_presets_references()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   {e}")
    else:
        print("   ✅ Presets references OK")
    
    # 3. Layout module
    print("\n3️⃣  Verifying layout.py...")
    errors = verify_layout_usage()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   {e}")
    else:
        print("   ✅ layout.py OK")
    
    # 4. Tone module
    print("\n4️⃣  Verifying tone.py...")
    errors = verify_tone_module()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"   {e}")
    else:
        print("   ✅ tone.py OK")
    
    # Summary
    print("\n" + "=" * 70)
    if all_errors:
        print(f"❌ VERIFICATION FAILED: {len(all_errors)} issues")
        print("=" * 70)
        return 1
    else:
        print("✅ ALL CONTENT PACK CHECKS PASSED")
        print("=" * 70)
        return 0


if __name__ == "__main__":
    sys.exit(verify_all())
