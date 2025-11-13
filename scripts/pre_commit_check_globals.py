#!/usr/bin/env python3
"""
Pre-commit hook to detect global variables in changed files.

This script checks only the changed files (staged for commit) for global variables
and prevents commits that introduce new global variables.

Exit codes:
- 0: No global variables found in changed files
- 1: Global variables found in changed files (blocks commit)
"""

import os
import re
import subprocess
import sys

# Exclusion patterns - files that are allowed to use global variables
EXCLUSION_PATTERNS = [
    r"tests/.*_test\.py",
    r"examples/.*\.py",
    r"scripts/detect_globals\.py",
    r".*migration.*\.py",
    r".*legacy.*\.py",
    r"src/marty_msf/core/di_container\.py",  # DI container itself needs globals
]


def should_exclude_file(file_path: str) -> bool:
    """Check if a file should be excluded from global variable checks."""
    for pattern in EXCLUSION_PATTERNS:
        if re.match(pattern, file_path):
            return True
    return False


def get_staged_python_files() -> list[str]:
    """Get list of staged Python files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        # Filter for Python files
        python_files = [f for f in files if f.endswith(".py") and os.path.exists(f)]
        return python_files
    except subprocess.CalledProcessError:
        return []


def get_staged_file_content(file_path: str) -> str:
    """Get the staged content of a file (what will be committed)."""
    try:
        result = subprocess.run(
            ["git", "show", f":{file_path}"], capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        # File might be newly added, read from filesystem
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return ""


def find_global_statements_in_content(content: str) -> list[tuple[int, str]]:
    """
    Find global statements in file content.

    Returns:
        List of (line_number, line_content) tuples
    """
    global_pattern = re.compile(r"^\s*global\s+\w+")
    results = []

    # Skip certain patterns that are acceptable
    skip_patterns = [
        r"global variables throughout",  # Documentation comments
        r"# global",  # Comments about globals
        r'""".*global.*"""',  # Docstring references
        r"'.*global.*'",  # String literals
        r'".*global.*"',  # String literals
    ]

    lines = content.split("\n")
    for line_num, line in enumerate(lines, 1):
        if global_pattern.match(line):
            # Check if this is an acceptable global usage
            skip_line = False
            for skip_pattern in skip_patterns:
                if re.search(skip_pattern, line, re.IGNORECASE):
                    skip_line = True
                    break

            if not skip_line:
                # Additional check: skip if this is in a migration/compatibility context
                # Look at surrounding lines for context
                context_lines = []
                start_idx = max(0, line_num - 3)
                end_idx = min(len(lines), line_num + 3)
                context_lines = lines[start_idx:end_idx]
                context = "\n".join(context_lines).lower()

                # Allow globals in migration scripts or compatibility layers
                if any(
                    keyword in context
                    for keyword in [
                        "migration",
                        "compatibility",
                        "backward compatibility",
                        "legacy",
                        "deprecated",
                        "transitional",
                    ]
                ):
                    continue

                results.append((line_num, line.strip()))

    return results


def main() -> int:
    """Main function."""
    staged_files = get_staged_python_files()

    if not staged_files:
        # No Python files staged, nothing to check
        return 0

    print("🔍 Checking staged files for global variables...")

    violations_found = False
    total_globals = 0

    for file_path in staged_files:
        # Skip excluded files
        if should_exclude_file(file_path):
            continue

        content = get_staged_file_content(file_path)
        if not content:
            continue

        global_statements = find_global_statements_in_content(content)

        if global_statements:
            violations_found = True
            total_globals += len(global_statements)
            print(f"\n❌ {file_path}")
            for line_num, line_content in global_statements:
                print(f"   Line {line_num}: {line_content}")

    if violations_found:
        print(f"\n🚫 COMMIT BLOCKED: Found {total_globals} global variable(s) in staged files!")
        print("\n💡 To fix this:")
        print("1. Replace global variables with dependency injection")
        print("2. Use the pattern from src/marty_msf/core/di_container.py")
        print("3. See GLOBAL_VARIABLE_MIGRATION.md for examples")
        print("4. Run 'python scripts/detect_globals.py' for detailed suggestions")
        print("\n📖 Dependency Injection Pattern:")
        print("   # Instead of:")
        print("   global my_service")
        print("   my_service = SomeService()")
        print("")
        print("   # Use:")
        print("   from marty_msf.core.di_container import get_service")
        print("   my_service = get_service(SomeService)")
        print("")
        print("🔧 If this is a legitimate use case (e.g., migration script),")
        print("   add appropriate context comments and patterns to the skip list.")
        return 1

    print("✅ No global variables found in staged files!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
