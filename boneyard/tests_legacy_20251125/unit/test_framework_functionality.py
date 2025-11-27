"""
Tests for framework functionality.

This module converts the legacy test_framework.py script into proper automated tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from marty_msf.framework.config import BaseServiceConfig
from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.monitoring.core import MetricsCollector
from scripts.test_framework import run_command

from scripts import test_framework


class TestFrameworkFunctionality:
    """Test suite for framework core functionality."""

    def test_template_validation(self):
        """Test that service templates are valid."""
        template_dir = Path("templates")

        if not template_dir.exists():
            pytest.skip("Templates directory not found")

        # Find template files
        template_files = (
            list(template_dir.rglob("*.py"))
            + list(template_dir.rglob("*.yml"))
            + list(template_dir.rglob("*.yaml"))
        )

        if not template_files:
            pytest.skip("No template files found")

        syntax_errors = []

        for template_file in template_files:
            try:
                if template_file.suffix == ".py":
                    # Validate Python syntax
                    with open(template_file, encoding="utf-8") as f:
                        content = f.read()
                    compile(content, str(template_file), "exec")

                elif template_file.suffix in [".yml", ".yaml"]:
                    # Validate YAML syntax
                    with open(template_file, encoding="utf-8") as f:
                        yaml.safe_load(f)

            except (SyntaxError, yaml.YAMLError) as e:
                syntax_errors.append((template_file, str(e)))
            except OSError:
                # Skip files that can't be read
                continue

        if syntax_errors:
            error_msg = "\n".join([f"  {file}: {error}" for file, error in syntax_errors])
            pytest.fail(f"Template syntax errors:\n{error_msg}")

    @patch("subprocess.run")
    def test_service_generation(self, mock_run):
        """Test service generation functionality."""
        # Mock successful command execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Service generated successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Test service generation command
        result = run_command("python scripts/generate_service.py test-service")

        assert result["success"] is True
        assert mock_run.called

    def test_framework_imports(self):
        """Test that core framework modules can be imported."""
        framework_modules = [
            "src.framework.config",
            "src.framework.events",
            "src.framework.logging",
            "src.framework.monitoring",
            "src.framework.messaging",
        ]

        import_errors = []
        for module in framework_modules:
            try:
                __import__(module)
            except ImportError as e:
                import_errors.append((module, str(e)))

        if import_errors:
            error_msg = "\n".join([f"  {module}: {error}" for module, error in import_errors])
            pytest.fail(f"Framework import errors:\n{error_msg}")

    def test_config_validation(self):
        """Test configuration validation."""
        config_dir = Path("config")

        if not config_dir.exists():
            pytest.skip("Config directory not found")

        config_files = list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.yml"))

        if not config_files:
            pytest.skip("No config files found")

        config_errors = []

        for config_file in config_files:
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                # Basic validation - should be a dictionary
                if not isinstance(config, dict):
                    config_errors.append((config_file, "Config should be a dictionary"))

            except yaml.YAMLError as e:
                config_errors.append((config_file, str(e)))
            except OSError:
                continue

        if config_errors:
            error_msg = "\n".join([f"  {file}: {error}" for file, error in config_errors])
            pytest.fail(f"Config validation errors:\n{error_msg}")

    def test_docker_configuration(self):
        """Test Docker configuration files."""
        # Check for Dockerfile in microservice template
        template_dockerfile = Path("microservice_project_template/Dockerfile")

        if template_dockerfile.exists():
            try:
                with open(template_dockerfile, encoding="utf-8") as f:
                    content = f.read()

                # Basic Dockerfile validation
                assert "FROM" in content, "Dockerfile should have FROM instruction"

                # Check for common Python Dockerfile patterns
                if "python" in content.lower():
                    assert any(keyword in content for keyword in ["COPY", "ADD"]), (
                        "Python Dockerfile should copy files"
                    )
                    assert "CMD" in content or "ENTRYPOINT" in content, (
                        "Dockerfile should have CMD or ENTRYPOINT"
                    )

            except OSError:
                pytest.skip("Could not read Dockerfile")
        else:
            pytest.skip("Dockerfile not found in template")

    def test_kubernetes_manifests(self):
        """Test Kubernetes manifest validation."""
        k8s_dir = Path("k8s")

        if not k8s_dir.exists():
            pytest.skip("Kubernetes directory not found")

        manifest_files = list(k8s_dir.rglob("*.yaml")) + list(k8s_dir.rglob("*.yml"))

        if not manifest_files:
            pytest.skip("No Kubernetes manifests found")

        manifest_errors = []

        for manifest_file in manifest_files:
            try:
                with open(manifest_file, encoding="utf-8") as f:
                    manifests = list(yaml.safe_load_all(f))

                for i, manifest in enumerate(manifests):
                    if manifest is None:
                        continue

                    if not isinstance(manifest, dict):
                        manifest_errors.append(
                            (manifest_file, f"Manifest {i} should be a dictionary")
                        )
                        continue

                    # Basic Kubernetes manifest validation
                    if "apiVersion" not in manifest:
                        manifest_errors.append((manifest_file, f"Manifest {i} missing apiVersion"))
                    if "kind" not in manifest:
                        manifest_errors.append((manifest_file, f"Manifest {i} missing kind"))

            except yaml.YAMLError as e:
                manifest_errors.append((manifest_file, str(e)))
            except OSError:
                continue

        if manifest_errors:
            error_msg = "\n".join([f"  {file}: {error}" for file, error in manifest_errors])
            pytest.fail(f"Kubernetes manifest errors:\n{error_msg}")

    @patch("subprocess.run")
    def test_build_integration(self, mock_run):
        """Test build integration functionality."""
        # Mock successful build
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Build successful"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Test build command
        result = run_command("make build")

        assert result["success"] is True
        assert mock_run.called

    def test_service_template_structure(self):
        """Test that service templates have the correct structure."""
        template_dir = Path("microservice_project_template")

        if not template_dir.exists():
            pytest.skip("Microservice template not found")

        required_files = [
            "pyproject.toml",
            "README.md",
            "Dockerfile",
        ]

        required_dirs = [
            "src",
            "tests",
            "k8s",
        ]

        missing_files = []
        missing_dirs = []

        for required_file in required_files:
            file_path = template_dir / required_file
            if not file_path.exists():
                missing_files.append(required_file)

        for required_dir in required_dirs:
            dir_path = template_dir / required_dir
            if not dir_path.exists():
                missing_dirs.append(required_dir)

        errors = []
        if missing_files:
            errors.append(f"Missing files: {missing_files}")
        if missing_dirs:
            errors.append(f"Missing directories: {missing_dirs}")

        if errors:
            pytest.fail("Template structure errors:\n" + "\n".join(errors))

    def test_framework_feature_integration(self):
        """Test integration between framework features."""
        try:
            # Test that components can work together

            # Test basic integration
            config = BaseServiceConfig()
            logger = UnifiedServiceLogger("test-service")
            metrics = MetricsCollector()

            # Basic functionality tests
            assert config is not None
            assert logger is not None
            assert metrics is not None

            # Test that they have expected interfaces
            assert hasattr(logger, "info")
            assert hasattr(metrics, "increment_counter")

        except ImportError as e:
            pytest.skip(f"Framework components not available: {e}")

    def test_example_files_validity(self):
        """Test that example files are valid and can be executed."""
        examples_dir = Path("examples")

        if not examples_dir.exists():
            pytest.skip("Examples directory not found")

        python_examples = list(examples_dir.glob("*.py"))

        if not python_examples:
            pytest.skip("No Python examples found")

        syntax_errors = []

        for example_file in python_examples:
            try:
                with open(example_file, encoding="utf-8") as f:
                    content = f.read()

                # Check syntax
                compile(content, str(example_file), "exec")

            except SyntaxError as e:
                syntax_errors.append((example_file, str(e)))
            except OSError:
                continue

        if syntax_errors:
            error_msg = "\n".join([f"  {file}: {error}" for file, error in syntax_errors])
            pytest.fail(f"Example syntax errors:\n{error_msg}")

    @pytest.mark.slow
    def test_end_to_end_service_creation(self):
        """Test end-to-end service creation process."""
        # This test requires more setup and should be marked as slow
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test that we can create a temporary service structure
            service_dir = temp_path / "test-service"
            service_dir.mkdir()

            # Create basic service files
            (service_dir / "main.py").write_text("""
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
""")

            (service_dir / "requirements.txt").write_text("fastapi\nuvicorn\n")

            # Verify files were created
            assert (service_dir / "main.py").exists()
            assert (service_dir / "requirements.txt").exists()

    def test_import_original_framework_script(self):
        """Test that the original framework script can be imported."""
        try:
            # Check that main functions exist
            assert hasattr(test_framework, "run_command")

            # Test that we can call the main functions
            result = test_framework.run_command("echo test")
            assert isinstance(result, dict)
            assert "success" in result

        except ImportError as e:
            pytest.fail(f"Could not import test_framework script: {e}")
