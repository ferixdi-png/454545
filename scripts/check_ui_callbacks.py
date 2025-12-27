#!/usr/bin/env python3
"""
Check UI and callback logic consistency.
Ensures every button has a handler and no silent failures.
"""
import re
from pathlib import Path
from typing import Dict, Set, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_callback_data_in_code(file_path: Path) -> Set[str]:
    """Find all callback_data values in Python code."""
    callbacks = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Find callback_data="..." or callback_data='...'
            pattern = r'callback_data\s*=\s*["\']([^"\']+)["\']'
            matches = re.findall(pattern, content)
            callbacks.update(matches)
            
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
    
    return callbacks


def find_callback_handlers(file_path: Path) -> Dict[str, List[int]]:
    """Find all callback query handlers and their callback_data patterns."""
    handlers = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Find @router.callback_query() decorators
            for i, line in enumerate(lines):
                if '@router.callback_query' in line or '@dp.callback_query' in line:
                    # Look for callback_data filter in next few lines
                    for j in range(i+1, min(i+20, len(lines))):
                        if 'callback_data' in lines[j]:
                            # Extract callback_data pattern
                            if '==' in lines[j]:
                                match = re.search(r'==\s*["\']([^"\']+)["\']', lines[j])
                                if match:
                                    callback_data = match.group(1)
                                    if callback_data not in handlers:
                                        handlers[callback_data] = []
                                    handlers[callback_data].append(i+1)
                            elif 'if callback_data ==' in lines[j]:
                                match = re.search(r'if callback_data ==\s*["\']([^"\']+)["\']', lines[j])
                                if match:
                                    callback_data = match.group(1)
                                    if callback_data not in handlers:
                                        handlers[callback_data] = []
                                    handlers[callback_data].append(i+1)
                    
                    # Check if handler has else clause (fallback)
                    for j in range(i+1, min(i+30, len(lines))):
                        if 'else:' in lines[j] and 'Unknown callback_data' in content[max(0, j-5):j+5]:
                            handlers['*fallback*'] = [i+1]
    
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
    
    return handlers


def check_ui_callbacks_consistency() -> Dict:
    """Check consistency between UI buttons and callback handlers."""
    logger.info("Finding all buttons...")
    all_buttons = {}
    all_callback_data = set()
    
    root = Path(".")
    for py_file in root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        callbacks = find_callback_data_in_code(py_file)
        if callbacks:
            all_buttons[str(py_file)] = callbacks
            all_callback_data.update(callbacks)
    
    logger.info("Finding all handlers...")
    all_handlers = {}
    all_handled = set()
    
    for py_file in root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        file_handlers = find_callback_handlers(py_file)
        if file_handlers:
            all_handlers[str(py_file)] = file_handlers
            all_handled.update(file_handlers.keys())
    
    # Find missing handlers
    missing_handlers = all_callback_data - all_handled - {'*fallback*'}
    
    # Find unused handlers
    unused_handlers = all_handled - all_callback_data - {'*fallback*'}
    
    return {
        'all_buttons': all_buttons,
        'all_handlers': all_handlers,
        'all_callback_data': sorted(all_callback_data),
        'all_handled': sorted(all_handled),
        'missing_handlers': sorted(missing_handlers),
        'unused_handlers': sorted(unused_handlers),
        'has_fallback': '*fallback*' in all_handled
    }


if __name__ == "__main__":
    result = check_ui_callbacks_consistency()
    
    print("\n" + "=" * 60)
    print("UI/CALLBACK CONSISTENCY CHECK")
    print("=" * 60)
    print(f"\nTotal callback_data found: {len(result['all_callback_data'])}")
    print(f"Total handlers found: {len(result['all_handled'])}")
    
    if result['missing_handlers']:
        print(f"\n[MISSING] HANDLERS ({len(result['missing_handlers'])}):")
        for callback in result['missing_handlers']:
            print(f"  - {callback}")
    else:
        print("\n[OK] All buttons have handlers")
    
    if result['unused_handlers']:
        print(f"\n[UNUSED] HANDLERS ({len(result['unused_handlers'])}):")
        for callback in result['unused_handlers']:
            print(f"  - {callback}")
    else:
        print("\n[OK] No unused handlers")
    
    if result['has_fallback']:
        print("\n[OK] Fallback handler exists for unknown callbacks")
    else:
        print("\n[WARNING] No fallback handler for unknown callbacks")
    
    print("\n" + "=" * 60)
    print("DETAILS:")
    print("=" * 60)
    print("\nAll callback_data values:")
    for callback in result['all_callback_data']:
        print(f"  - {callback}")
    
    print("\nAll handlers:")
    for callback in result['all_handled']:
        print(f"  - {callback}")

