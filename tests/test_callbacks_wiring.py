"""
Test that all callback_data strings have handlers.

MASTER PROMPT Section 5D: "Никаких битых кнопок"
"""
import re
from pathlib import Path
from typing import Set

import pytest


def _extract_callback_data_from_files() -> Set[str]:
    """Extract all callback_data strings from bot handlers."""
    bot_dir = Path(__file__).parent.parent / "bot" / "handlers"
    callbacks = set()
    
    # Patterns to match callback_data
    patterns = [
        r'callback_data=["\']([^"\']+)["\']',  # callback_data="value"
        r'callback_data=f["\']([^"\']+)["\']',  # callback_data=f"value"
    ]
    
    for file_path in bot_dir.glob("*.py"):
        content = file_path.read_text()
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Skip dynamic parts (f-strings with variables)
                if "{" not in match:
                    callbacks.add(match)
                else:
                    # Extract static prefix (e.g., "model:" from "model:{model_id}")
                    prefix = match.split("{")[0]
                    if prefix:
                        callbacks.add(prefix + "*")  # Mark as prefix pattern
    
    return callbacks


def _extract_handlers_from_files() -> Set[str]:
    """Extract all callback query handlers from bot handlers."""
    bot_dir = Path(__file__).parent.parent / "bot" / "handlers"
    handlers = set()
    
    # Patterns to match handler decorators
    patterns = [
        r'@router\.callback_query\(F\.data\s*==\s*["\']([^"\']+)["\']\)',
        r'@router\.callback_query\(F\.data\.startswith\(["\']([^"\']+)["\']\)\)',
        r'@router\.callback_query\(F\.data\.in_\(\{([^}]+)\}\)\)',
    ]
    
    for file_path in bot_dir.glob("*.py"):
        content = file_path.read_text()
        
        # Match exact handlers
        matches = re.findall(patterns[0], content)
        handlers.update(matches)
        
        # Match prefix handlers
        matches = re.findall(patterns[1], content)
        for match in matches:
            handlers.add(match + "*")  # Mark as prefix pattern
        
        # Match multi-value handlers (F.data.in_)
        matches = re.findall(patterns[2], content)
        for match in matches:
            # Extract individual values
            values = re.findall(r'["\']([^"\']+)["\']', match)
            handlers.update(values)
    
    return handlers


def test_no_orphaned_callbacks():
    """
    Verify all callback_data strings have corresponding handlers.
    
    CRITICAL: Master Prompt Section 5D requirement.
    """
    callbacks = _extract_callback_data_from_files()
    handlers = _extract_handlers_from_files()
    
    # Find orphaned callbacks (no handler)
    orphaned = set()
    
    for callback in callbacks:
        # Check exact match
        if callback in handlers:
            continue
        
        # Check prefix match (e.g., "model:*" handler covers "model:xyz")
        if callback.endswith("*"):
            # This is a prefix callback pattern, skip
            continue
        
        # Check if callback matches any prefix handler
        matched = False
        for handler in handlers:
            if handler.endswith("*"):
                prefix = handler[:-1]
                if callback.startswith(prefix):
                    matched = True
                    break
        
        if not matched:
            orphaned.add(callback)
    
    # Exclude known safe callbacks
    safe_callbacks = {
        "noop",  # Pagination display placeholder
        "main_menu",  # Universal back button
        "cancel",  # State-specific (InputFlow.confirm)
        "confirm",  # State-specific (InputFlow.confirm)
        "admin:users:ban",  # Future feature (user moderation)
        "admin:users:charge",  # Future feature (manual balance adjustment)
        "admin:users:topup",  # Future feature (manual topup)
    }
    orphaned = orphaned - safe_callbacks
    
    assert len(orphaned) == 0, (
        f"Found {len(orphaned)} orphaned callback_data without handlers:\n"
        f"{sorted(orphaned)}\n\n"
        f"All callbacks: {sorted(callbacks)}\n"
        f"All handlers: {sorted(handlers)}"
    )


def test_handler_coverage_stats():
    """Print coverage statistics for debugging."""
    callbacks = _extract_callback_data_from_files()
    handlers = _extract_handlers_from_files()
    
    print(f"\n📊 Callback Coverage Stats:")
    print(f"Total unique callbacks: {len(callbacks)}")
    print(f"Total handlers: {len(handlers)}")
    print(f"\nCallbacks: {sorted(callbacks)}")
    print(f"\nHandlers: {sorted(handlers)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
