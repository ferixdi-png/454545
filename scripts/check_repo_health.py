#!/usr/bin/env python3
"""Repository health check - prevents large files from bloating the repo.

This script validates:
- No files larger than MAX_FILE_SIZE_MB in git
- Cache/data/artifacts folders not tracked by git
- No large binaries/archives committed
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Configuration
MAX_FILE_SIZE_MB = 5  # Maximum size for any single file in repo
FORBIDDEN_EXTENSIONS = {'.zip', '.tar', '.tar.gz', '.rar', '.7z', '.bak', '.backup'}
FORBIDDEN_DIRECTORIES = {'cache', 'data', 'artifacts', 'archive', '__pycache__', '.pytest_cache'}


def get_git_tracked_files() -> List[str]:
    """Get list of all files tracked by git."""
    try:
        result = subprocess.run(
            ['git', 'ls-files', '--cached'],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        print("❌ Error: Not a git repository or git not available")
        sys.exit(1)


def check_file_size(file_path: str) -> Tuple[bool, float]:
    """Check if file exceeds size limit. Returns (is_ok, size_mb)."""
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        return size_mb <= MAX_FILE_SIZE_MB, size_mb
    except OSError:
        return True, 0.0  # File doesn't exist (was deleted)


def check_forbidden_extension(file_path: str) -> bool:
    """Check if file has a forbidden extension."""
    path = Path(file_path)
    return any(file_path.endswith(ext) for ext in FORBIDDEN_EXTENSIONS)


def check_forbidden_directory(file_path: str) -> bool:
    """Check if file is in a forbidden directory."""
    parts = Path(file_path).parts
    return any(forbidden in parts for forbidden in FORBIDDEN_DIRECTORIES)


def main():
    """Run repository health checks."""
    print("🔍 Running repository health check...")
    print(f"   Max file size: {MAX_FILE_SIZE_MB} MB")
    print(f"   Forbidden extensions: {', '.join(FORBIDDEN_EXTENSIONS)}")
    print(f"   Forbidden directories: {', '.join(FORBIDDEN_DIRECTORIES)}")
    print()

    tracked_files = get_git_tracked_files()
    if not tracked_files or tracked_files == ['']:
        print("✅ No tracked files found")
        return

    errors = []
    warnings = []

    for file_path in tracked_files:
        if not file_path:
            continue

        # Check forbidden directories
        if check_forbidden_directory(file_path):
            errors.append(f"❌ Forbidden directory: {file_path}")
            continue

        # Check forbidden extensions
        if check_forbidden_extension(file_path):
            errors.append(f"❌ Forbidden file type: {file_path}")
            continue

        # Check file size
        is_ok, size_mb = check_file_size(file_path)
        if not is_ok:
            errors.append(f"❌ File too large ({size_mb:.2f} MB): {file_path}")
        elif size_mb > MAX_FILE_SIZE_MB * 0.7:  # Warning at 70% threshold
            warnings.append(f"⚠️  Large file ({size_mb:.2f} MB): {file_path}")

    # Report results
    print(f"✅ Checked {len(tracked_files)} tracked files")
    print()

    if warnings:
        print(f"⚠️  {len(warnings)} warnings:")
        for warning in warnings[:10]:  # Show first 10
            print(f"   {warning}")
        if len(warnings) > 10:
            print(f"   ... and {len(warnings) - 10} more")
        print()

    if errors:
        print(f"❌ {len(errors)} errors found:")
        for error in errors[:20]:  # Show first 20
            print(f"   {error}")
        if len(errors) > 20:
            print(f"   ... and {len(errors) - 20} more")
        print()
        print("Fix these issues before committing:")
        print("  1. Remove from git: git rm --cached <file>")
        print("  2. Add to .gitignore")
        print("  3. Clean history: git filter-repo --invert-paths --path <file>")
        sys.exit(1)

    print("✅ Repository health check passed!")
    print()

    # Show repo size
    try:
        result = subprocess.run(['du', '-sh', '.git'], capture_output=True, text=True)
        if result.returncode == 0:
            size = result.stdout.split()[0]
            print(f"📦 Repository size: {size}")
    except Exception:
        pass


if __name__ == '__main__':
    main()
