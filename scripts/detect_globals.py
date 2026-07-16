#!/usr/bin/env python3
"""
Global Variable Detection Script

This script helps identify remaining global variables in the codebase
and provides suggestions for migration to dependency injection.

Usage:
    python scripts/detect_globals.py [directory]
"""

import os
import re
import sys
from pathlib import Path


def find_global_statements(directory: str) -> list[tuple[str, int, str]]:
    """
    Find all global statements in Python files.

    Returns:
        List of (file_path, line_number, line_content) tuples
    """
    global_pattern = re.compile(r"^\s*global\s+\w+")
    results = []

    for root, dirs, files in os.walk(directory):
        # Skip cache directories and other non-source directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if global_pattern.match(line):
                                results.append((file_path, line_num, line.strip()))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return results


def suggest_migration(global_statements: list[tuple[str, int, str]]) -> None:
    """Print migration suggestions for global statements."""

    if not global_statements:
        print("✅ No global statements found!")
        return

    print(f"🔍 Found {len(global_statements)} global statements to migrate:\n")

    # Group by file
    by_file = {}
    for file_path, line_num, line_content in global_statements:
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append((line_num, line_content))

    for file_path, statements in by_file.items():
        print(f"📁 {file_path}")
        for line_num, line_content in statements:
            print(f"   Line {line_num}: {line_content}")

            # Extract variable name for suggestions
            match = re.search(r"global\s+(\w+)", line_content)
            if match:
                var_name = match.group(1)
                print("   💡 Suggestion: Replace with dependency injection")
                print(f"      1. Create factory for service containing '{var_name}'")
                print("      2. Use get_service() pattern instead of global access")
                print("      3. Register service in factories.py")
        print()


def main():
    """Main entry point."""
    directory = sys.argv[1] if len(sys.argv) > 1 else "mmf"

    if not os.path.exists(directory):
        print(f"❌ Directory '{directory}' does not exist")
        sys.exit(1)

    print(f"🔍 Scanning {directory} for global variables...\n")

    global_statements = find_global_statements(directory)
    suggest_migration(global_statements)

    print("\n📖 Migration Guide:")
    print("1. Review the Dependency Injection pattern in mmf/core/di_container.py")
    print("2. Create service factories following examples in mmf/security/factories.py")
    print("3. Update service functions to use get_service() pattern")
    print("4. Add backward compatibility with auto-registration")
    print("5. Verify with MyPy: uv run --isolated mypy <your_file>.py")
    print("\n📄 See GLOBAL_VARIABLE_MIGRATION.md for detailed examples")


if __name__ == "__main__":
    main()
