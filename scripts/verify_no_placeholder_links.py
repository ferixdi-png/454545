#!/usr/bin/env python3
"""Verify no placeholder links in code."""
import sys
import re
from pathlib import Path

def scan_files():
    """Scan for placeholder links."""
    root = Path(__file__).parent.parent
    
    # Files to scan
    patterns = [
        'bot/**/*.py',
        'app/**/*.py',
    ]
    
    placeholders = []
    
    for pattern in patterns:
        for file_path in root.glob(pattern):
            if '__pycache__' in str(file_path):
                continue
            
            try:
                content = file_path.read_text()
                
                # Check for placeholder bot links
                if 't.me/bot?start=' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if 't.me/bot?start=' in line:
                            placeholders.append((file_path, i, line.strip()))
                
            except Exception as e:
                print(f"⚠️ Error reading {file_path}: {e}")
    
    return placeholders


def main():
    """Main check."""
    placeholders = scan_files()
    
    if placeholders:
        print(f"❌ Found {len(placeholders)} placeholder links:")
        for file_path, line_num, line in placeholders:
            print(f"  {file_path}:{line_num} → {line}")
        return 1
    else:
        print("✅ No placeholder links found")
        return 0


if __name__ == '__main__':
    sys.exit(main())
