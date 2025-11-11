#!/usr/bin/env python3
"""
Fix import indentation in Python files.
This script fixes files that were corrupted by the import order checker.
"""

import ast
import re
import sys
from pathlib import Path


def fix_import_indentation(file_path: Path) -> bool:
    """Fix indentation of imports at the top of a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError) as e:
        print(f"❌ Could not read {file_path}: {e}")
        return False

    # Skip empty files
    if not content.strip():
        return True

    lines = content.splitlines(keepends=True)
    new_lines = []

    # Process each line
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty try blocks that only contain imports
        if stripped == "try:" and i + 1 < len(lines):
            # Look ahead to see if this is a try block with only imports
            try_content = []
            j = i + 1
            found_imports_only = True
            found_except = False

            # Collect content until we find except or end of file
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith("except"):
                    found_except = True
                    # Skip the except block
                    while j < len(lines) and (
                        lines[j].startswith(" ")
                        or lines[j].startswith("\t")
                        or lines[j].strip().startswith("except")
                    ):
                        j += 1
                    break
                elif next_line and not next_line.startswith(("import ", "from ")):
                    found_imports_only = False
                    break
                elif next_line.startswith(("import ", "from ")):
                    try_content.append(next_line)
                j += 1

            # If this try block only contains imports, extract them
            if found_imports_only and found_except and try_content:
                print("🔧 Removing try-catch wrapper around imports")
                for import_line in try_content:
                    new_lines.append(import_line.strip() + "\n")
                i = j  # Skip to after the except block
                continue

        # If this is an import line with wrong indentation, fix it
        if (stripped.startswith("import ") or stripped.startswith("from ")) and line.startswith(
            (" ", "\t")
        ):
            # This is an indented import - normalize it to module level
            new_lines.append(stripped + "\n")
            print(f"🔧 Fixed indented import: {stripped}")
        else:
            new_lines.append(line)

        i += 1

    # Only write if we made changes
    new_content = "".join(new_lines)
    if new_content != content:
        try:
            # Validate the new content can be parsed
            ast.parse(new_content)

            # Write the fixed content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            print(f"✅ Fixed {file_path}")
            return True

        except SyntaxError as e:
            print(f"❌ Would create syntax error in {file_path}: {e}")
            return False
        except (OSError, UnicodeEncodeError) as e:
            print(f"❌ Could not write {file_path}: {e}")
            return False

    return True


def main():
    """Fix import indentation in all Python files."""
    if len(sys.argv) > 1:
        # Process specific files
        files = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Process all Python files in the project
        project_root = Path(__file__).parent.parent
        files = list(project_root.rglob("*.py"))
        # Filter out some directories
        files = [
            f
            for f in files
            if not any(part in str(f) for part in [".venv", "__pycache__", ".git", "node_modules"])
        ]

    print(f"🔍 Processing {len(files)} Python files...")

    fixed_count = 0
    error_count = 0

    for file_path in files:
        if file_path.is_file() and file_path.suffix == ".py":
            try:
                if fix_import_indentation(file_path):
                    fixed_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"❌ Unexpected error processing {file_path}: {e}")
                error_count += 1

    print("\n📊 Summary:")
    print(f"   ✅ Files processed: {fixed_count}")
    print(f"   ❌ Errors: {error_count}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
