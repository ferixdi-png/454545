#!/usr/bin/env python3
"""
Verify all callback_data have handlers.

CRITICAL: No orphaned callbacks allowed in production.
"""
import re
from pathlib import Path


def extract_callbacks_from_buttons(file_path: Path) -> set:
    """Extract all callback_data strings from InlineKeyboardButton calls."""
    callbacks = set()
    content = file_path.read_text()
    
    # Pattern: callback_data="something" or callback_data=f"something:{var}"
    patterns = [
        r'callback_data\s*=\s*["\']([^"\']+)["\']',  # Static
        r'callback_data\s*=\s*f["\']([^"\'{}]+)',     # F-string prefix
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            callback = match.group(1)
            # Extract prefix for dynamic callbacks (e.g., "cat:" from "cat:{category}")
            if ':' in callback:
                prefix = callback.split(':')[0] + ':'
                callbacks.add(prefix)
            else:
                callbacks.add(callback)
    
    return callbacks


def extract_handlers(file_path: Path) -> set:
    """Extract all callback patterns from @router.callback_query decorators."""
    handlers = set()
    content = file_path.read_text()
    
    # Pattern: F.data == "something" or F.data.startswith("prefix:")
    patterns = [
        r'F\.data\s*==\s*["\']([^"\']+)["\']',         # Exact match
        r'F\.data\.startswith\(["\']([^"\']+)["\']\)', # Prefix match
        r'F\.data\.in_\(\{[^}]*["\']([^"\']+)["\'][^}]*\}\)',  # in_ set
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            handler = match.group(1)
            # Normalize prefix
            if handler.endswith(':'):
                handlers.add(handler)
            elif ':' in handler:
                # For exact matches like "cat:something", add prefix
                prefix = handler.split(':')[0] + ':'
                handlers.add(prefix)
                handlers.add(handler)  # Also add exact
            else:
                handlers.add(handler)
    
    return handlers


def main():
    print("="*80)
    print("🔍 CALLBACK WIRING VERIFICATION")
    print("="*80)
    print()
    
    # Find all handler files
    handler_dir = Path("bot/handlers")
    if not handler_dir.exists():
        print("❌ bot/handlers directory not found")
        return 1
    
    handler_files = list(handler_dir.glob("*.py"))
    
    # Collect all callbacks and handlers
    all_callbacks = set()
    all_handlers = set()
    
    for file in handler_files:
        if file.name == "__init__.py":
            continue
        
        callbacks = extract_callbacks_from_buttons(file)
        handlers = extract_handlers(file)
        
        all_callbacks.update(callbacks)
        all_handlers.update(handlers)
        
        print(f"📄 {file.name}")
        print(f"   Callbacks defined: {len(callbacks)}")
        print(f"   Handlers defined: {len(handlers)}")
    
    print()
    print("="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total callbacks: {len(all_callbacks)}")
    print(f"Total handlers: {len(all_handlers)}")
    print()
    
    # Find orphaned callbacks (callback without handler)
    orphaned = set()
    for callback in all_callbacks:
        # Check if there's a matching handler
        matched = False
        for handler in all_handlers:
            if callback == handler:
                matched = True
                break
            # Check prefix match
            if handler.endswith(':') and callback.startswith(handler):
                matched = True
                break
        
        if not matched:
            orphaned.add(callback)
    
    if orphaned:
        print("❌ ORPHANED CALLBACKS (no handler):")
        for cb in sorted(orphaned):
            print(f"   - {cb}")
        print()
        return 1
    else:
        print("✅ ALL CALLBACKS HAVE HANDLERS")
        print()
    
    # Find unused handlers (handler without any callback)
    unused = set()
    for handler in all_handlers:
        # Check if any callback uses this handler
        matched = False
        for callback in all_callbacks:
            if callback == handler:
                matched = True
                break
            if handler.endswith(':') and callback.startswith(handler):
                matched = True
                break
        
        if not matched:
            unused.add(handler)
    
    if unused:
        print("⚠️ UNUSED HANDLERS (defined but no callback uses them):")
        for h in sorted(unused):
            print(f"   - {h}")
        print()
        print("Note: These might be for future use or external triggers")
    
    print("="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80)
    return 0


if __name__ == "__main__":
    exit(main())
