#!/usr/bin/env python3
"""
Advanced syntax error fixer for complex import and structure issues.
Handles empty try blocks, misplaced imports, and complex indentation patterns.
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional


class ComplexSyntaxFixer:
    """Advanced syntax error fixer."""

    def __init__(self):
        self.files_processed = 0
        self.files_fixed = 0
        self.errors = []

        # Exclusions for safety
        self.exclusions = {
            '.venv', 'node_modules', '__pycache__', '.git', '.pytest_cache',
            '.mypy_cache', '.ruff_cache', 'site-packages', 'dist', 'build',
            '.tox', 'htmlcov', '.coverage'
        }

    def should_exclude_path(self, path: Path) -> bool:
        """Check if path should be excluded."""
        path_parts = path.parts
        return any(exclusion in path_parts for exclusion in self.exclusions)

    def extract_imports_and_code(self, content: str) -> tuple[list[str], list[str], str]:
        """Extract imports, try-except blocks, and remaining code."""
        lines = content.split('\n')
        imports = []
        try_blocks = []
        remaining_lines = []

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            # Skip empty lines and comments at the start
            if not stripped or stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                remaining_lines.append(line)
                i += 1
                continue

            # Handle imports (various indentation levels)
            if self.is_import_line(stripped):
                # Normalize import to no indentation
                import_content = stripped
                imports.append(import_content)
                i += 1
                continue

            # Handle try-except blocks that might contain imports
            if stripped.startswith('try:'):
                try_start = i
                i += 1

                # Look for the except block
                try_content = []
                except_content = []
                in_try = True

                while i < len(lines):
                    current_line = lines[i].rstrip()
                    current_stripped = current_line.strip()

                    if current_stripped.startswith('except'):
                        in_try = False
                        except_content.append(current_line)
                        i += 1

                        # Collect except block content
                        while i < len(lines):
                            next_line = lines[i].rstrip()
                            next_stripped = next_line.strip()

                            if next_stripped and not next_line.startswith(' ') and not next_line.startswith('\t'):
                                break

                            except_content.append(next_line)
                            i += 1
                        break
                    elif in_try:
                        # Check if this is an import in the try block
                        if self.is_import_line(current_stripped):
                            imports.append(current_stripped)
                        else:
                            try_content.append(current_line)

                    i += 1

                # Reconstruct try-except if there was actual content
                if try_content or except_content:
                    try_block = [lines[try_start]]
                    if try_content:
                        try_block.extend(try_content)
                    else:
                        try_block.append('    pass')  # Add pass to empty try
                    try_block.extend(except_content)
                    try_blocks.extend(try_block)

                continue

            # Regular code line
            remaining_lines.append(line)
            i += 1

        return imports, try_blocks, '\n'.join(remaining_lines)

    def is_import_line(self, line: str) -> bool:
        """Check if line is an import statement."""
        return (line.startswith('import ') or
                line.startswith('from ') or
                line.startswith('__import__'))

    def fix_file_content(self, content: str) -> str | None:
        """Fix syntax errors in file content."""
        try:
            # First try to parse - if it works, no fix needed
            ast.parse(content)
            return None
        except SyntaxError:
            pass

        lines = content.split('\n')

        # Find module docstring and preserve it
        docstring_lines = []
        code_start_idx = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                docstring_lines.append(line)
                continue
            elif stripped.startswith('"""') or stripped.startswith("'''"):
                # Handle docstring
                quote = '"""' if stripped.startswith('"""') else "'''"
                docstring_lines.append(line)

                if stripped.count(quote) >= 2:
                    # Single line docstring
                    code_start_idx = i + 1
                    break
                else:
                    # Multi-line docstring
                    for j in range(i + 1, len(lines)):
                        docstring_lines.append(lines[j])
                        if quote in lines[j]:
                            code_start_idx = j + 1
                            break
                    break
            else:
                code_start_idx = i
                break

        # Extract imports and code from the remaining content
        remaining_content = '\n'.join(lines[code_start_idx:])
        imports, try_blocks, other_code = self.extract_imports_and_code(remaining_content)

        # Remove duplicates while preserving order
        unique_imports = []
        seen = set()
        for imp in imports:
            if imp not in seen:
                unique_imports.append(imp)
                seen.add(imp)

        # Reconstruct file
        result_lines = []

        # Add preserved docstring/header
        if docstring_lines:
            result_lines.extend(docstring_lines)
            if unique_imports or try_blocks or other_code.strip():
                result_lines.append('')  # Blank line after docstring

        # Add imports
        if unique_imports:
            result_lines.extend(unique_imports)
            if try_blocks or other_code.strip():
                result_lines.append('')  # Blank line after imports

        # Add try blocks
        if try_blocks:
            result_lines.extend(try_blocks)
            if other_code.strip():
                result_lines.append('')  # Blank line after try blocks

        # Add remaining code
        if other_code.strip():
            result_lines.append(other_code)

        result = '\n'.join(result_lines)

        # Final cleanup
        result = self.clean_extra_newlines(result)

        # Verify the fix worked
        try:
            ast.parse(result)
            return result
        except SyntaxError as e:
            self.errors.append(f"Still has syntax error after fix: {e}")
            return None

    def clean_extra_newlines(self, content: str) -> str:
        """Clean excessive newlines."""
        # Replace multiple consecutive newlines with at most 2
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Ensure file ends with exactly one newline
        content = content.rstrip('\n') + '\n'

        return content

    def fix_file(self, file_path: Path) -> bool:
        """Fix a single file."""
        self.files_processed += 1

        try:
            with open(file_path, encoding='utf-8') as f:
                original_content = f.read()

            fixed_content = self.fix_file_content(original_content)

            if fixed_content is not None and fixed_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)

                print(f"✅ Fixed: {file_path}")
                self.files_fixed += 1
                return True
            elif fixed_content is None:
                print(f"❌ Could not fix: {file_path}")
                return False
            else:
                # File was already correct
                return True

        except Exception as e:
            error_msg = f"Error processing {file_path}: {e}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

    def fix_workspace(self, workspace_path: Path) -> None:
        """Fix all Python files in workspace."""
        print(f"🔧 Starting complex syntax error fixing in {workspace_path}")

        # Find all Python files
        python_files = []
        for file_path in workspace_path.rglob("*.py"):
            if not self.should_exclude_path(file_path):
                python_files.append(file_path)

        print(f"📁 Found {len(python_files)} Python files to check")

        # Process files
        for file_path in python_files:
            self.fix_file(file_path)

        # Report results
        print("\n📊 Processing complete:")
        print(f"   📄 Files processed: {self.files_processed}")
        print(f"   ✅ Files fixed: {self.files_fixed}")
        print(f"   ❌ Errors: {len(self.errors)}")

        if self.errors:
            print("\n❌ Errors encountered:")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"   • {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more errors")


def main():
    """Main function."""
    workspace_path = Path(__file__).parent.parent

    fixer = ComplexSyntaxFixer()
    fixer.fix_workspace(workspace_path)


if __name__ == "__main__":
    main()
