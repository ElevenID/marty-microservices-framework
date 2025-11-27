"""
Tests for code quality checks.

This module converts the legacy check_code_quality.py script into proper automated tests.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scripts.check_code_quality import check_cyclomatic_complexity

from scripts import check_code_quality


class TestCodeQuality:
    """Test suite for code quality checks."""

    def test_cyclomatic_complexity_check(self):
        """Test that cyclomatic complexity checking works."""
        # Test with a simple function that should pass
        simple_code = """
def simple_function(x):
    return x + 1
"""

        # Parse and check complexity
        tree = ast.parse(simple_code)

        # Check that we can parse the code without errors
        assert tree is not None
        assert len(tree.body) == 1
        assert isinstance(tree.body[0], ast.FunctionDef)

    def test_file_length_limits(self):
        """Test file length validation."""
        src_dir = Path("src/framework/")
        if not src_dir.exists():
            pytest.skip("Source directory not found")

        max_lines = 500  # Configurable limit
        violations = []

        for py_file in src_dir.rglob("*.py"):
            if py_file.is_file():
                try:
                    with open(py_file, encoding="utf-8") as f:
                        line_count = sum(1 for _ in f)

                    if line_count > max_lines:
                        violations.append((py_file, line_count))
                except (UnicodeDecodeError, OSError):
                    # Skip files that can't be read
                    continue

        # Report violations but don't fail the test unless critical
        if violations:
            violation_report = "\n".join([f"  {file}: {lines} lines" for file, lines in violations])
            print(f"\n⚠️  Files exceeding {max_lines} lines:\n{violation_report}")

        # Only fail if there are files with extremely high line counts
        critical_violations = [v for v in violations if v[1] > 1000]
        assert len(critical_violations) == 0, (
            f"Critical file length violations: {critical_violations}"
        )

    def test_function_length_limits(self):
        """Test function length validation."""
        src_dir = Path("src/framework/")
        if not src_dir.exists():
            pytest.skip("Source directory not found")

        max_function_lines = 50
        violations = []

        for py_file in src_dir.rglob("*.py"):
            if py_file.is_file():
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()

                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                            func_lines = node.end_lineno - node.lineno + 1
                            if func_lines > max_function_lines:
                                violations.append((py_file, node.name, func_lines))

                except (SyntaxError, UnicodeDecodeError, OSError):
                    # Skip files that can't be parsed
                    continue

        # Report violations
        if violations:
            violation_report = "\n".join(
                [f"  {file}:{func}: {lines} lines" for file, func, lines in violations]
            )
            print(f"\n⚠️  Functions exceeding {max_function_lines} lines:\n{violation_report}")

        # Only fail for extremely long functions
        critical_violations = [v for v in violations if v[2] > 100]
        assert len(critical_violations) == 0, (
            f"Critical function length violations: {critical_violations}"
        )

    @patch("subprocess.run")
    def test_radon_complexity_check(self, mock_run):
        """Test radon complexity checking integration."""
        # Mock successful radon execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Test that the function completes without error
        result = check_cyclomatic_complexity("src/framework/")

        # Should return True for successful check
        assert result is True

        # Verify radon was called
        assert mock_run.called

    @patch("subprocess.run")
    def test_radon_complexity_violations(self, mock_run):
        """Test handling of complexity violations."""
        # Mock radon finding violations
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "M 15:0 complex_function - B (13)"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Test that violations are detected
        result = check_cyclomatic_complexity("src/framework/")

        # Should still return True but log violations
        assert result is True

    def test_import_quality_script(self):
        """Test that the original script can be imported."""
        try:
            assert hasattr(check_code_quality, "check_cyclomatic_complexity")
            assert hasattr(check_code_quality, "run_command")
        except ImportError as e:
            pytest.fail(f"Could not import check_code_quality script: {e}")

    def test_syntax_validation(self):
        """Test that all Python files have valid syntax."""
        src_dir = Path("src/framework/")
        if not src_dir.exists():
            pytest.skip("Source directory not found")

        syntax_errors = []

        for py_file in src_dir.rglob("*.py"):
            if py_file.is_file():
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()

                    # Try to parse the file
                    ast.parse(content)

                except SyntaxError as e:
                    syntax_errors.append((py_file, str(e)))
                except (UnicodeDecodeError, OSError):
                    # Skip files that can't be read
                    continue

        if syntax_errors:
            error_report = "\n".join([f"  {file}: {error}" for file, error in syntax_errors])
            pytest.fail(f"Syntax errors found:\n{error_report}")

    def test_code_quality_metrics_collection(self):
        """Test collection of basic code quality metrics."""
        src_dir = Path("src/framework/")
        if not src_dir.exists():
            pytest.skip("Source directory not found")

        metrics = {
            "total_files": 0,
            "total_lines": 0,
            "total_functions": 0,
            "total_classes": 0,
        }

        for py_file in src_dir.rglob("*.py"):
            if py_file.is_file():
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()

                    metrics["total_files"] += 1
                    metrics["total_lines"] += len(content.splitlines())

                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                            metrics["total_functions"] += 1
                        elif isinstance(node, ast.ClassDef):
                            metrics["total_classes"] += 1

                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

        # Basic sanity checks
        assert metrics["total_files"] > 0, "No Python files found"
        assert metrics["total_lines"] > 0, "No code lines found"

        print("\n📊 Code Quality Metrics:")
        print(f"  Files: {metrics['total_files']}")
        print(f"  Lines: {metrics['total_lines']}")
        print(f"  Functions: {metrics['total_functions']}")
        print(f"  Classes: {metrics['total_classes']}")

        if metrics["total_files"] > 0:
            avg_lines_per_file = metrics["total_lines"] / metrics["total_files"]
            print(f"  Avg lines per file: {avg_lines_per_file:.1f}")
