#!/usr/bin/env python3
"""
Dev setup helper - быстрая настройка окружения для локальной разработки.
"""
import os
import sys
from pathlib import Path

def check_python_version():
    """Check Python version."""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        print(f"   Current: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True

def check_env_file():
    """Check .env file exists."""
    env_path = Path(".env")
    if env_path.exists():
        print("✅ .env file exists")
        return True
    
    print("⚠️  .env file missing")
    print("\n📝 Creating .env template...")
    
    template = """# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_BotFather
ADMIN_ID=your_telegram_user_id

# Kie.ai API
KIE_API_KEY=kie_your_api_key

# Bot Mode (polling for local, webhook for production)
BOT_MODE=polling

# Database (auto-creates SQLite for local dev)
# DATABASE_URL=postgresql://... (only for production)
"""
    
    env_path.write_text(template)
    print("✅ Created .env template")
    print("\n⚠️  IMPORTANT: Fill in your actual tokens in .env file!")
    return False

def check_requirements():
    """Check if requirements are installed."""
    try:
        import aiogram
        import asyncpg
        print("✅ Requirements installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("\n💡 Run: pip install -r requirements.txt")
        return False

def check_source_of_truth():
    """Check SOURCE_OF_TRUTH file."""
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not sot_path.exists():
        print("❌ SOURCE_OF_TRUTH missing")
        return False
    
    import json
    try:
        data = json.loads(sot_path.read_text())
        models = data.get('models', {})
        print(f"✅ SOURCE_OF_TRUTH: {len(models)} models")
        return True
    except Exception as e:
        print(f"❌ SOURCE_OF_TRUTH parse error: {e}")
        return False

def run_verifications():
    """Run verification scripts."""
    print("\n" + "="*70)
    print("🔍 Running verifications...")
    print("="*70)
    
    import subprocess
    
    result = subprocess.run(
        ["python", "scripts/check_all.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ All verifications passed")
        return True
    else:
        print("⚠️  Some verifications failed")
        print(result.stdout)
        return False

def main():
    """Main setup flow."""
    print("="*70)
    print("🚀 Kie.ai Bot - Dev Setup Helper")
    print("="*70)
    print()
    
    checks = [
        ("Python version", check_python_version),
        ("Requirements", check_requirements),
        ("SOURCE_OF_TRUTH", check_source_of_truth),
        (".env file", check_env_file),
    ]
    
    all_ok = True
    for name, check_func in checks:
        print(f"\n🔍 Checking {name}...")
        if not check_func():
            all_ok = False
    
    print("\n" + "="*70)
    
    if all_ok:
        print("✅ Setup complete!")
        print("\n📝 Next steps:")
        print("   1. Fill in .env with your tokens")
        print("   2. Run: python main_render.py")
        print("   3. Test: send /start to your bot")
        print("\n🔗 Guides:")
        print("   - QUICK_START_DEV.md - full developer guide")
        print("   - CONTRIBUTING.md - how to contribute")
        
        # Run verifications
        run_verifications()
    else:
        print("⚠️  Setup incomplete - fix issues above")
        print("\n📖 See QUICK_START_DEV.md for detailed instructions")
    
    print("="*70)
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
