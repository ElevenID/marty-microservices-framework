#!/usr/bin/env python3
"""
Pre-commit check for import placement

This script ensures all imports are at the top of Python files (after docstrings                         last_import_line = import_line

              elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef |
                          ast.If | ast.For | ast.While | ast.With | ast.AsyncWith |
                          ast.Try | ast.Assign | ast.AugAssign | ast.AnnAssign |
                          ast.Expr):  # For standalone expressions like function calls
                  # Skip if this is a module docstring      elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef |
                          ast.If | ast.For | ast.While | ast.With | ast.AsyncWith |
                          ast.Try | ast.Assign | ast.AugAssign | ast.AnnAssign |
                          ast.Expr):  # For standalone expressions like function calls comments).
Can optionally fix issues automatically.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Built-in exclusions to prevent processing sensitive directories/files
BUILT_IN_EXCLUSIONS = {
    # Virtual environments
    ".venv",
    "venv",
    ".env",
    "env",
    "ENV",
    # Package managers
    "node_modules",
    ".npm",
    ".yarn",
    # Version control
    ".git",
    ".svn",
    ".hg",
    # IDEs and editors
    ".vscode",
    ".idea",
    ".vs",
    # Python cache
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    # Build artifacts
    "build",
    "dist",
    ".egg-info",
    "*.egg-info",
    # Documentation builds
    "_build",
    ".sphinx-build",
    # Temporary files
    ".tmp",
    "tmp",
    "temp",
    # OS specific
    ".DS_Store",
    "Thumbs.db",
}


class ImportChecker:
    """Checks and optionally fixes import placement at the top of files."""

    def __init__(self, fix: bool = False):
        self.errors: list[tuple[str, int, str]] = []
        self.fixes: list[str] = []
        self.fix_mode = fix

    def is_safe_to_process(self, file_path: Path) -> bool:
        """Check if a file is safe to process (not in excluded directories)."""
        # Convert to absolute path for consistent checking
        abs_path = file_path.resolve()
        path_parts = abs_path.parts

        # Check if any part of the path matches built-in exclusions
        for part in path_parts:
            if part in BUILT_IN_EXCLUSIONS:
                return False
            # Check for pattern matches (like *.egg-info)
            for exclusion in BUILT_IN_EXCLUSIONS:
                if "*" in exclusion and part.endswith(exclusion.replace("*", "")):
                    return False

        # Only process Python files in reasonable source locations
        if not file_path.suffix == ".py":
            return False

        # Ensure we're not processing system or library files
        str_path = str(abs_path)
        if (
            "/site-packages/" in str_path
            or "/lib/python" in str_path
            or "/Library/Frameworks/Python.framework/" in str_path
        ):
            return False

        return True

    def check_file(self, file_path: Path) -> bool:
        """
        Check a single Python file for import placement issues.
        Optionally fix issues if fix_mode is enabled.

        Returns:
            True if file passes checks or was fixed, False otherwise
        """
        # Safety check - don't process files we shouldn't touch
        if not self.is_safe_to_process(file_path):
            return True  # Skip silently

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            self.errors.append((str(file_path), 0, f"Could not read file: {e}"))
            return False

        if not content.strip():
            return True  # Empty file is OK

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            # Be more specific about syntax errors
            error_type = "Syntax error"
            if "unexpected indent" in str(e).lower():
                error_type = "Indentation error (unexpected indent)"
            elif "inconsistent use of tabs and spaces" in str(e).lower():
                error_type = "Indentation error (mixed tabs and spaces)"
            elif "unindent does not match" in str(e).lower():
                error_type = "Indentation error (mismatched indentation)"

            self.errors.append((str(file_path), e.lineno or 0, f"{error_type}: {e}"))
            return False
        except Exception as e:
            self.errors.append((str(file_path), 0, f"Failed to parse file: {e}"))
            return False

        if self.fix_mode:
            return self._fix_import_placement(file_path, tree, content)
        else:
            return self._check_import_placement(file_path, tree, content)

    def _check_import_placement(self, file_path: Path, tree: ast.AST, content: str) -> bool:
        """Check that imports are at the top of the file."""
        lines = content.splitlines()

        # Find the first non-import statement that's not a docstring or comment
        first_non_import_line = None
        last_import_line = None

        # Skip module docstring and initial comments
        start_checking_line = self._get_start_line(tree, lines)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                import_line = node.lineno

                # Check if this import comes after non-import code
                if first_non_import_line and import_line > first_non_import_line:
                    import_stmt = lines[import_line - 1].strip()
                    self.errors.append(
                        (
                            str(file_path),
                            import_line,
                            f"Import statement found after non-import code: {import_stmt}",
                        )
                    )
                    return False

                if last_import_line is None or import_line > last_import_line:
                    last_import_line = import_line

            elif isinstance(
                node,
                ast.FunctionDef
                | ast.AsyncFunctionDef
                | ast.ClassDef
                | ast.If
                | ast.For
                | ast.While
                | ast.With
                | ast.AsyncWith
                | ast.Try
                | ast.Assign
                | ast.AugAssign
                | ast.AnnAssign
                | ast.Expr,
            ):  # For standalone expressions like function calls
                # Skip if this is a module docstring
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and node.lineno <= start_checking_line
                ):
                    continue

                # Skip if this is before we start checking
                if node.lineno < start_checking_line:
                    continue

                if first_non_import_line is None:
                    first_non_import_line = node.lineno

        return True

    def _get_start_line(self, tree: ast.AST, lines: list[str]) -> int:
        """
        Get the line number where we should start checking for imports.
        This skips the module docstring and initial comments.
        """
        start_line = 1

        # Skip shebang
        if lines and lines[0].startswith("#!"):
            start_line = 2

        # Skip encoding declaration
        for i in range(min(2, len(lines))):
            if re.match(r"#.*?coding[:=]", lines[i]):
                start_line = max(start_line, i + 2)
                break

        # Skip module docstring
        if (
            isinstance(tree, ast.Module)
            and tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            end_line = tree.body[0].end_lineno
            if end_line is not None:
                start_line = max(start_line, end_line + 1)

        # Skip initial comments and blank lines
        for i in range(start_line - 1, len(lines)):
            line = lines[i].strip()
            if line and not line.startswith("#"):
                start_line = i + 1
                break

        return start_line

    def _fix_import_placement(self, file_path: Path, tree: ast.AST, content: str) -> bool:
        """Fix import placement by moving imports to the top of the file."""
        lines = content.splitlines()
        start_checking_line = self._get_start_line(tree, lines) - 1  # Convert to 0-based

        # Collect all imports with their line numbers
        all_imports = []
        misplaced_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                import_info = {
                    "node": node,
                    "start_line": node.lineno - 1,  # 0-based
                    "end_line": (node.end_lineno - 1) if node.end_lineno else (node.lineno - 1),
                    "text_lines": [],
                }

                # Get the import text
                for i in range(import_info["start_line"], import_info["end_line"] + 1):
                    if i < len(lines):
                        import_info["text_lines"].append(lines[i])

                all_imports.append(import_info)

                # Check if this import is misplaced (after non-import code)
                if import_info["start_line"] > start_checking_line:
                    # Look for non-import code before this import
                    for check_node in ast.walk(tree):
                        if (
                            isinstance(
                                check_node,
                                ast.FunctionDef
                                | ast.AsyncFunctionDef
                                | ast.ClassDef
                                | ast.If
                                | ast.For
                                | ast.While
                                | ast.With
                                | ast.AsyncWith
                                | ast.Try
                                | ast.Assign
                                | ast.AugAssign
                                | ast.AnnAssign,
                            )
                            and check_node.lineno - 1 >= start_checking_line
                            and check_node.lineno - 1 < import_info["start_line"]
                        ):
                            misplaced_imports.append(import_info)
                            break

        if not misplaced_imports:
            return True  # No misplaced imports found

        # Build the new file content
        new_lines = []
        skip_lines = set()

        # Mark all misplaced import lines to skip
        for import_info in misplaced_imports:
            for i in range(import_info["start_line"], import_info["end_line"] + 1):
                skip_lines.add(i)

        # Copy lines excluding misplaced imports
        for i, line in enumerate(lines):
            if i not in skip_lines:
                new_lines.append(line)

        # Insert misplaced imports at the proper location
        import_texts = []
        for import_info in misplaced_imports:
            # Strip indentation from import lines and normalize them
            for line in import_info["text_lines"]:
                # Remove leading whitespace to ensure imports are at module level
                stripped_line = line.lstrip()
                if stripped_line:  # Only add non-empty lines
                    import_texts.append(stripped_line)

        # Insert imports at the start_checking_line position in new_lines
        insertion_point = start_checking_line
        # Adjust insertion point if we removed lines before it
        for skip_line in sorted(skip_lines):
            if skip_line < start_checking_line:
                insertion_point -= 1

        # Insert imports in reverse order to maintain positions
        for import_text in reversed(import_texts):
            new_lines.insert(insertion_point, import_text)

        # Write the fixed content back to the file with safety checks
        try:
            # Create a backup of the original content
            backup_content = content

            # Validate the new content can be parsed
            new_content = "\n".join(new_lines)
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                self.errors.append((str(file_path), 0, f"Fix would create syntax error: {e}"))
                return False

            # Write the fixed content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.fixes.append(str(file_path))
            return True

        except (OSError, UnicodeEncodeError) as e:
            self.errors.append((str(file_path), 0, f"Could not write fixed file: {e}"))
            # Try to restore the original content if we can
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(backup_content)
            except (OSError, UnicodeEncodeError):
                pass  # Don't make things worse
            return False

    def check_files(self, file_paths: list[Path]) -> bool:
        """
        Check multiple files for import placement issues.

        Returns:
            True if all files pass checks, False otherwise
        """
        all_passed = True

        for file_path in file_paths:
            if not file_path.suffix == ".py":
                continue

            if not self.check_file(file_path):
                all_passed = False

        return all_passed

    def print_errors(self) -> None:
        """Print all errors found during checking."""
        if not self.errors:
            return

        print("Import placement errors found:")
        print("=" * 50)

        for file_path, line_no, message in self.errors:
            print(f"{file_path}:{line_no}: {message}")

        print(f"\nTotal errors: {len(self.errors)}")


def is_safe_path(file_path: Path) -> bool:
    """Check if a file is safe to process (not in excluded directories)."""
    # Convert to absolute path for consistent checking
    abs_path = file_path.resolve()
    path_parts = abs_path.parts

    # Check if any part of the path matches built-in exclusions
    for part in path_parts:
        if part in BUILT_IN_EXCLUSIONS:
            return False
        # Check for pattern matches (like *.egg-info)
        for exclusion in BUILT_IN_EXCLUSIONS:
            if "*" in exclusion and part.endswith(exclusion.replace("*", "")):
                return False

    # Only process Python files in reasonable source locations
    if not file_path.suffix == ".py":
        return False

    # Ensure we're not processing system or library files
    str_path = str(abs_path)
    if (
        "/site-packages/" in str_path
        or "/lib/python" in str_path
        or "/Library/Frameworks/Python.framework/" in str_path
    ):
        return False

    return True


def get_python_files(paths: list[str]) -> list[Path]:
    """Get all Python files from the given paths, with built-in safety exclusions."""
    python_files = []

    for path_str in paths:
        path = Path(path_str)

        if path.is_file():
            # Only add if it's safe to process
            if is_safe_path(path):
                python_files.append(path)
        elif path.is_dir():
            # Walk directory but exclude unsafe paths
            for py_file in path.rglob("*.py"):
                if is_safe_path(py_file):
                    python_files.append(py_file)

    return python_files


def main() -> int:
    """Main entry point for the import checker."""
    parser = argparse.ArgumentParser(
        description="Check that imports are at the top of Python files"
    )
    parser.add_argument(
        "paths", nargs="*", default=["."], help="Paths to check (files or directories)"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Patterns to exclude (can be used multiple times)",
    )
    parser.add_argument(
        "--fix", action="store_true", help="Automatically fix import placement issues"
    )

    args = parser.parse_args()

    # Get all Python files
    python_files = get_python_files(args.paths)

    # Apply exclusions
    if args.exclude:
        excluded_files = []
        for file_path in python_files:
            file_str = str(file_path)
            if not any(pattern in file_str for pattern in args.exclude):
                excluded_files.append(file_path)
        python_files = excluded_files

    if not python_files:
        print("No Python files found to check.")
        return 0

    # Check files with optional fixing
    checker = ImportChecker(fix=args.fix)
    success = checker.check_files(python_files)

    # Print results based on what happened
    if checker.errors:
        print(f"\n💥 Encountered {len(checker.errors)} errors:")
        for file_path, line_num, message in checker.errors:
            print(f"  {file_path}:{line_num}: {message}")

    if checker.fixes:
        print(f"\n✅ Fixed import placement in {len(checker.fixes)} files:")
        for file_path in checker.fixes:
            print(f"  {file_path}")

    if not success and not checker.fixes:
        print("\n❌ Import placement violations found. Use --fix to automatically correct them.")
        return 1
    elif success and not checker.fixes and not checker.errors:
        print(f"✓ All {len(python_files)} Python files have properly placed imports.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
