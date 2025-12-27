#!/usr/bin/env python3
"""
Project verification script for SYNTX-grade UX.

Runs comprehensive checks:
- Unit tests
- Static analysis (no "kie.ai" in UI)
- Placeholder link detection
- Import sanity checks
"""
import sys
import subprocess
from pathlib import Path
import re


def run_command(cmd: list, description: str) -> bool:
    """Run command and return success status."""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description}: PASSED")
            return True
        else:
            print(f"❌ {description}: FAILED")
            return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False


def check_no_kie_in_ui() -> bool:
    """Check that 'kie.ai' does not appear in UI files."""
    print(f"\n{'='*60}")
    print("🔍 Checking for 'kie.ai' mentions in UI")
    print(f"{'='*60}")
    
    ui_files = [
        "bot/handlers/marketing.py",
        "app/ui/templates.py",
        "app/ui/model_profile.py",
        "app/ui/formats.py",
    ]
    
    violations = []
    
    for file_path in ui_files:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            continue
        
        content = full_path.read_text()
        
        # Check for "kie.ai" (case insensitive)
        if re.search(r"\bkie\.ai\b", content, re.IGNORECASE):
            violations.append(file_path)
    
    if violations:
        print(f"❌ Found 'kie.ai' in: {', '.join(violations)}")
        return False
    else:
        print("✅ No 'kie.ai' mentions in UI files")
        return True


def check_placeholder_links() -> bool:
    """Check for placeholder bot links."""
    print(f"\n{'='*60}")
    print("🔍 Checking for placeholder bot links")
    print(f"{'='*60}")
    
    files_to_check = [
        "bot/handlers/marketing.py",
        "bot/utils/bot_info.py",
    ]
    
    placeholder_patterns = [
        r"t\.me/bot\?",
        r"https://t\.me/bot\?start=",
    ]
    
    violations = []
    
    for file_path in files_to_check:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            continue
        
        content = full_path.read_text()
        
        for pattern in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file_path}: {pattern}")
    
    if violations:
        print(f"❌ Found placeholder links in:\n" + "\n".join(violations))
        return False
    else:
        print("✅ No placeholder bot links found")
        return True


def main():
    """Run all verification checks."""
    print("🚀 SYNTX-Grade UX Verification")
    print("=" * 60)
    
    results = []
    
    # 1. Run unit tests
    results.append(run_command(
        ["python", "-m", "pytest", "tests/test_format_first_ux.py", "-v"],
        "Format-first UX tests"
    ))
    
    results.append(run_command(
        ["python", "-m", "pytest", "tests/test_wizard_mandatory_inputs.py", "-v"],
        "Wizard mandatory inputs tests"
    ))
    
    results.append(run_command(
        ["python", "-m", "pytest", "tests/test_media_proxy_signing.py", "-v"],
        "Media proxy signing tests"
    ))
    
    results.append(run_command(
        ["python", "-m", "pytest", "tests/test_user_upsert_fk.py", "-v"],
        "User upsert FK tests"
    ))
    
    results.append(run_command(
        ["python", "-m", "pytest", "tests/test_no_placeholder_links.py", "-v"],
        "No placeholder links tests"
    ))
    
    # 2. Static checks
    results.append(check_no_kie_in_ui())
    results.append(check_placeholder_links())
    
    # 3. Import sanity check
    results.append(run_command(
        ["python", "-c", "import app.webhook_server; import bot.flows.wizard; import app.database.services"],
        "Import sanity check"
    ))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 VERIFICATION SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL CHECKS PASSED - Ready for deployment!")
        return 0
    else:
        print(f"❌ {total - passed} CHECKS FAILED - Fix issues before deploying")
        return 1


if __name__ == "__main__":
    sys.exit(main())
