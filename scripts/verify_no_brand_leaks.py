#!/usr/bin/env python3
"""Verify no "kie.ai" brand mentions in code."""
import sys
import re
from pathlib import Path

def scan_files():
    """Scan for brand leaks."""
    root = Path(__file__).parent.parent
    
    # Files to scan
    patterns = [
        'bot/**/*.py',
        'app/**/*.py',
    ]
    
    leaks = []
    
    for pattern in patterns:
        for file_path in root.glob(pattern):
            if '__pycache__' in str(file_path):
                continue
            
            try:
                content = file_path.read_text()
                
                # Check for kie.ai mentions
                if 'kie.ai' in content.lower():
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if 'kie.ai' in line.lower():
                            leaks.append((file_path, i, line.strip()))
                
            except Exception as e:
                print(f"⚠️ Error reading {file_path}: {e}")
    
    return leaks


def main():
    """Main check."""
    leaks = scan_files()
    
    if leaks:
        print(f"❌ Found {len(leaks)} brand leaks:")
        for file_path, line_num, line in leaks:
            print(f"  {file_path}:{line_num} → {line}")
        return 1
    else:
        print("✅ No brand leaks found")
        return 0


if __name__ == '__main__':
    sys.exit(main())
