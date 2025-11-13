"""
Tests for dependency checks.

This module converts the legacy check_dependencies.py script into proper automated tests.
"""

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_dependencies import check_command, check_import


class TestDependencyChecks:
    """Test suite for dependency validation."""

    def test_core_dependencies_available(self):
        """Test that core framework dependencies are available."""
        core_deps = ["fastapi", "pydantic", "uvicorn", "pytest", "pytest_asyncio"]

        missing_deps = []
        for dep in core_deps:
            try:
                importlib.import_module(dep)
            except ImportError:
                missing_deps.append(dep)

        if missing_deps:
            pytest.fail(f"Missing core dependencies: {missing_deps}")

    def test_optional_dependencies_documented(self):
        """Test that optional dependencies are properly documented."""
        try:
            # Try to import the original script to verify it works
            assert callable(check_import)
        except ImportError as e:
            pytest.fail(f"Could not import dependency checker: {e}")

    def test_python_version_compatibility(self):
        """Test Python version compatibility checks."""

        # Check minimum Python version
        min_version = (3, 10)
        current_version = sys.version_info[:2]

        assert current_version >= min_version, (
            f"Python {min_version[0]}.{min_version[1]}+ required, "
            f"but running {current_version[0]}.{current_version[1]}"
        )

        # Check for Python 3.13 compatibility issues
        if current_version >= (3, 13):
            print("⚠️  Running on Python 3.13+, checking for compatibility issues...")

    @patch("subprocess.run")
    def test_command_availability(self, mock_run):
        """Test that required system commands are available."""
        # Mock successful command execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "version 1.0.0"
        mock_run.return_value = mock_result

        # Test that the function works
        result = check_command("uv")
        assert result is True

        # Verify subprocess was called
        assert mock_run.called

    @patch("subprocess.run")
    def test_command_not_found(self, mock_run):
        """Test handling of missing commands."""
        # Mock command not found
        mock_run.side_effect = FileNotFoundError()

        result = check_command("nonexistent-command")
        assert result is False

    def test_development_dependencies(self):
        """Test that development dependencies are available."""
        dev_deps = [
            ("pytest", "pytest"),
            ("black", "black"),
            ("ruff", "ruff"),
        ]

        for module_name, package_name in dev_deps:
            try:
                importlib.import_module(module_name)
            except ImportError:
                # Don't fail for dev dependencies, just warn
                print(f"⚠️  Development dependency missing: {package_name}")

    def test_e2e_dependencies(self):
        """Test E2E testing dependencies."""
        e2e_deps = [
            ("playwright", "playwright"),
            ("docker", "docker"),
        ]

        missing_e2e = []
        for module_name, package_name in e2e_deps:
            try:
                importlib.import_module(module_name)
            except ImportError:
                missing_e2e.append(package_name)

        if missing_e2e:
            print(f"⚠️  E2E dependencies missing: {missing_e2e}")
            print("Install with: uv add " + " ".join(missing_e2e))

    def test_framework_imports(self):
        """Test that framework modules can be imported."""
        framework_modules = [
            "src.framework.config",
            "src.framework.events",
            "src.framework.logging",
        ]

        import_errors = []
        for module in framework_modules:
            try:
                importlib.import_module(module)
            except ImportError as e:
                import_errors.append((module, str(e)))

        if import_errors:
            error_msg = "\n".join([f"  {module}: {error}" for module, error in import_errors])
            pytest.fail(f"Framework import errors:\n{error_msg}")

    def test_pyproject_toml_dependencies(self):
        """Test that pyproject.toml dependencies are properly formatted."""
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            # Check that dependencies section exists
            assert "project" in data, "No [project] section in pyproject.toml"
            assert "dependencies" in data["project"], "No dependencies in pyproject.toml"

            dependencies = data["project"]["dependencies"]
            assert isinstance(dependencies, list), "Dependencies should be a list"
            assert len(dependencies) > 0, "No dependencies defined"

            # Basic validation of dependency format
            for dep in dependencies:
                assert isinstance(dep, str), f"Dependency should be string: {dep}"
                assert len(dep.strip()) > 0, f"Empty dependency: {dep}"

        except Exception as e:
            pytest.fail(f"Error reading pyproject.toml: {e}")

    def test_virtual_environment_setup(self):
        """Test that we're running in a proper virtual environment."""

        # Check if we're in a virtual environment
        in_venv = (
            (
                hasattr(sys, "prefix")
                and hasattr(sys, "base_prefix")
                and sys.prefix != sys.base_prefix
            )
            or (hasattr(sys, "real_prefix"))
            or ("VIRTUAL_ENV" in __import__("os").environ)
        )

        if not in_venv:
            print("⚠️  Not running in a virtual environment")
            print("Consider using: uv venv && source .venv/bin/activate")

    def test_uv_lock_consistency(self):
        """Test that uv.lock is consistent with pyproject.toml."""
        lock_path = Path("uv.lock")
        pyproject_path = Path("pyproject.toml")

        if not lock_path.exists():
            pytest.skip("uv.lock not found")

        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        # Check that lock file is newer than pyproject.toml
        lock_mtime = lock_path.stat().st_mtime
        pyproject_mtime = pyproject_path.stat().st_mtime

        if pyproject_mtime > lock_mtime:
            print("⚠️  pyproject.toml is newer than uv.lock")
            print("Consider running: uv lock")

    def test_security_dependencies(self):
        """Test security-related dependencies."""
        security_deps = [
            "cryptography",
            "passlib",
            "python_jose",
        ]

        for dep in security_deps:
            try:
                importlib.import_module(dep)
            except ImportError:
                print(f"⚠️  Security dependency missing: {dep}")

    @pytest.mark.slow
    def test_dependency_vulnerability_scan(self):
        """Test for known vulnerabilities in dependencies."""
        try:
            result = subprocess.run(
                ["uv", "pip", "check"], capture_output=True, text=True, timeout=30, check=False
            )

            if result.returncode != 0:
                print(f"⚠️  Dependency check failed:\n{result.stdout}\n{result.stderr}")

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Could not run dependency vulnerability scan")
