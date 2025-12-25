#!/usr/bin/env python3
"""
Verify ALL files required for deployment exist and are tracked in git.
"""
import os
import sys
from pathlib import Path

def get_all_py_files(root_dir):
    """Get all Python files recursively."""
    files = []
    for root, dirs, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))
    return files

def check_imports_in_file(filepath):
    """Extract imports from Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        imports = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('from ') or line.startswith('import '):
                imports.append(line)
        return imports
    except Exception as e:
        return [f"ERROR: {e}"]

def find_missing_modules():
    """Find all modules that are imported but don't exist."""
    root = Path('.')
    all_files = get_all_py_files('app') + get_all_py_files('bot')
    all_files.append('main_render.py')
    
    missing = []
    for filepath in all_files:
        if not os.path.exists(filepath):
            continue
        
        imports = check_imports_in_file(filepath)
        for imp in imports:
            if 'from app.' in imp or 'import app.' in imp:
                # Extract module path
                if 'from app.' in imp:
                    module = imp.split('from ')[1].split(' import')[0].strip()
                elif 'import app.' in imp:
                    module = imp.split('import ')[1].split(' as')[0].strip()
                else:
                    continue
                
                # Convert to file path
                module_path = module.replace('.', '/')
                py_file = f"{module_path}.py"
                init_file = f"{module_path}/__init__.py"
                
                if not os.path.exists(py_file) and not os.path.exists(init_file):
                    # Check if it's a submodule
                    parts = module.split('.')
                    for i in range(len(parts), 0, -1):
                        check_path = '/'.join(parts[:i]) + '.py'
                        if os.path.exists(check_path):
                            break
                        check_init = '/'.join(parts[:i]) + '/__init__.py'
                        if os.path.exists(check_init):
                            break
                    else:
                        missing.append((filepath, module, py_file))
    
    return missing

if __name__ == "__main__":
    print("Checking all files...")
    missing = find_missing_modules()
    
    if missing:
        print(f"\n❌ FOUND {len(missing)} MISSING MODULES:\n")
        for filepath, module, expected_file in missing:
            print(f"  File: {filepath}")
            print(f"  Import: {module}")
            print(f"  Expected: {expected_file}")
            print()
        sys.exit(1)
    else:
        print("✅ All imported modules exist!")
        sys.exit(0)

