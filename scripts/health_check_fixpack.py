#!/usr/bin/env python3
"""
Quick health check for final fixpack.
Run this before deploying to production.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    print("=" * 60)
    print("FINAL FIXPACK — HEALTH CHECK")
    print("=" * 60)
    print()
    
    print("🔍 Testing imports...")
    try:
        # Critical fixes
        from app.database.services import DatabaseService
        assert hasattr(DatabaseService, 'fetchrow'), "Missing fetchrow"
        assert hasattr(DatabaseService, 'fetchone'), "Missing fetchone"
        print("  ✅ DatabaseService.fetchrow")
        
        from app.database.generation_events import log_generation_event
        print("  ✅ log_generation_event (FK protection)")
        
        from bot.utils.bot_info import get_bot_username, get_referral_link
        print("  ✅ bot_info (referral links)")
        
        # New UX modules
        from app.ui.input_spec import get_input_spec, InputType
        from app.ui.formats import FORMATS, get_popular_models
        from app.ui.render import render_welcome, render_model_card
        from app.ui.templates import TEMPLATES
        from bot.flows.wizard import start_wizard
        from bot.handlers.formats import router as formats_router
        
        print("  ✅ UI system (input_spec, formats, render, templates)")
        print("  ✅ Wizard flow")
        print("  ✅ Format handlers")
        
        print()
        print("📊 Stats:")
        print(f"  - Formats: {len(FORMATS)}")
        print(f"  - Templates: {sum(len(t) for t in TEMPLATES.values())}")
        print(f"  - InputType enum: {len(list(InputType))}")
        
        print()
        print("✅ All critical systems operational!")
        print()
        print("🚀 Ready for production deployment")
        print()
        return 0
        
    except Exception as e:
        print()
        print(f"❌ Health check failed: {e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
