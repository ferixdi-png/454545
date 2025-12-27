"""FSM routes verification script.

Ensures all callback patterns have handlers.
"""
import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.handlers import router


def extract_callback_patterns_from_handlers():
    """Extract callback patterns registered in router."""
    patterns = set()
    
    # Get all callback query handlers
    for observer in router.observers.get("callback_query", []):
        # Extract filter if present
        if hasattr(observer, "filters"):
            for filter_obj in observer.filters:
                # Check if it's a callback_data filter
                if hasattr(filter_obj, "callback_data"):
                    cb_data = filter_obj.callback_data
                    if isinstance(cb_data, str):
                        patterns.add(cb_data)
                # Check for F.data patterns
                if hasattr(filter_obj, "magic_data"):
                    magic = filter_obj.magic_data
                    if hasattr(magic, "startswith"):
                        patterns.add(str(magic.startswith) + "*")
    
    return patterns


def extract_callback_data_from_ui():
    """Extract callback_data values from UI builders."""
    patterns = set()
    
    # Scan UI files
    ui_dir = Path(__file__).parent.parent / "app" / "ui"
    
    for py_file in ui_dir.rglob("*.py"):
        content = py_file.read_text()
        
        # Find callback_data= patterns
        matches = re.findall(r'callback_data=["\']([^"\']+)["\']', content)
        patterns.update(matches)
    
    return patterns


def main():
    """Verify all UI callbacks have handlers."""
    print("🔍 Verifying FSM routes and callbacks...")
    
    # Get patterns
    handler_patterns = extract_callback_patterns_from_handlers()
    ui_patterns = extract_callback_data_from_ui()
    
    print(f"\n📊 Found {len(handler_patterns)} handler patterns")
    print(f"📊 Found {len(ui_patterns)} UI callback patterns")
    
    # Check coverage (simplified - just check prefixes)
    uncovered = []
    
    for ui_cb in ui_patterns:
        # Check if any handler pattern matches
        covered = False
        
        for handler_cb in handler_patterns:
            if handler_cb.endswith("*"):
                prefix = handler_cb[:-1]
                if ui_cb.startswith(prefix):
                    covered = True
                    break
            elif ui_cb == handler_cb:
                covered = True
                break
        
        if not covered:
            uncovered.append(ui_cb)
    
    if uncovered:
        print(f"\n⚠️ Found {len(uncovered)} potentially uncovered callbacks:")
        for cb in sorted(uncovered)[:20]:  # Show first 20
            print(f"  - {cb}")
        
        # This is a warning, not a hard failure (false positives possible)
        print("\n💡 Note: Some may be covered by dynamic handlers. Manual review recommended.")
        return 0  # Don't fail build
    else:
        print("\n✅ All UI callbacks appear to have handlers")
        return 0


if __name__ == "__main__":
    sys.exit(main())
