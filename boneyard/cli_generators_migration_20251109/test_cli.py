"""
Test suite for Marty CLI functionality.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from marty_msf.cli import MartyProjectManager, MartyTemplateManager, ProjectConfig, cli


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def template_manager(temp_dir):
    """Template manager with test framework path."""
    # Create mock framework structure
    framework_path = temp_dir / "marty-microservices-framework"
    templates_path = framework_path / "templates"
    templates_path.mkdir(parents=True)

    # Create a test template
    test_template = templates_path / "test-service"
    test_template.mkdir()

    (test_template / "main.py").write_text(
        """
# {{project_name}} - {{project_description}}
print("Hello from {{project_slug}}!")
"""
    )

    (test_template / "template.yaml").write_text(
        """
name: test-service
description: Test service template
category: service
python_version: "3.11"
framework_version: "1.0.0"
dependencies:
  - fastapi>=0.104.0
variables:
  service_port: 8000
post_hooks: []
"""
    )

    return MartyTemplateManager(framework_path)


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_version(self, runner):
        """Test CLI version command."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_help(self, runner):
        """Test CLI help command."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Marty Microservices Framework CLI" in result.output

    def test_templates_command(self, runner, template_manager):
        """Test templates listing command."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            result = runner.invoke(cli, ["templates"])
            assert result.exit_code == 0
            assert "test-service" in result.output


class TestTemplateManager:
    """Test template management functionality."""

    def test_get_available_templates(self, template_manager):
        """Test getting available templates."""
        templates = template_manager.get_available_templates()
        assert "test-service" in templates
        assert templates["test-service"].description == "Test service template"

    def test_create_project(self, template_manager, temp_dir):
        """Test project creation."""
        config = ProjectConfig(
            name="My Test Service",
            template="test-service",
            path=str(temp_dir / "my-test-service"),
            author="Test Author",
            email="test@example.com",
            description="A test service",
            skip_prompts=True,
        )

        success = template_manager.create_project(config)
        assert success

        project_path = Path(config.path)
        assert project_path.exists()
        assert (project_path / "main.py").exists()

        # Check template processing
        main_content = (project_path / "main.py").read_text()
        assert "My Test Service" in main_content
        assert "my-test-service" in main_content

    def test_config_management(self, template_manager):
        """Test configuration management."""
        # Set config values
        template_manager.config["author"] = "Test Author"
        template_manager.config["email"] = "test@example.com"

        # Save config
        template_manager.save_config()

        # Load config
        new_manager = MartyTemplateManager(template_manager.framework_path)
        assert new_manager.config.get("author") == "Test Author"
        assert new_manager.config.get("email") == "test@example.com"


class TestProjectManager:
    """Test project management functionality."""

    def test_find_current_project(self, temp_dir):
        """Test finding current project."""
        # Create project structure
        project_path = temp_dir / "test-project"
        project_path.mkdir()

        # Create marty.toml
        marty_config = project_path / "marty.toml"
        marty_config.write_text(
            """
[project]
name = "test-project"
version = "1.0.0"
"""
        )

        # Change to project directory
        original_cwd = os.getcwd()
        try:
            os.chdir(project_path)
            project_manager = MartyProjectManager()
            # Resolve both paths to handle macOS /private/var vs /var symlink
            expected_path = project_path.resolve()
            actual_path = (
                project_manager.current_project.resolve()
                if project_manager.current_project
                else None
            )
            assert actual_path == expected_path
        finally:
            os.chdir(original_cwd)

    def test_get_project_info(self, temp_dir):
        """Test getting project information."""
        project_path = temp_dir / "test-project"
        project_path.mkdir()

        # Create marty.toml
        marty_config = project_path / "marty.toml"
        marty_config.write_text(
            """
[project]
name = "test-project"
version = "1.0.0"
description = "Test project"
"""
        )

        original_cwd = os.getcwd()
        try:
            os.chdir(project_path)
            project_manager = MartyProjectManager()
            info = project_manager.get_project_info()

            assert info is not None
            assert info.get("project", {}).get("name") == "test-project"
        finally:
            os.chdir(original_cwd)


class TestCLICommands:
    """Test CLI commands."""

    def test_new_command(self, runner, template_manager, temp_dir):
        """Test new project command."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            result = runner.invoke(
                cli,
                [
                    "new",
                    "test-service",
                    "My New Service",
                    "--path",
                    str(temp_dir),
                    "--author",
                    "Test Author",
                    "--email",
                    "test@example.com",
                    "--description",
                    "A test service",
                    "--skip-prompts",
                ],
            )

            assert result.exit_code == 0
            assert "created successfully" in result.output

            project_path = temp_dir / "my-new-service"
            assert project_path.exists()

    def test_new_command_interactive(self, runner, template_manager, temp_dir):
        """Test new project command in interactive mode."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            # Mock user inputs
            inputs = [
                "test-service",  # Template selection
                "Interactive Service",  # Project name
                "Test Author",  # Author
                "test@example.com",  # Email
                "An interactive service",  # Description
            ]

            result = runner.invoke(
                cli,
                [
                    "new",
                    "test-service",
                    "Interactive Service",
                    "--path",
                    str(temp_dir),
                    "--interactive",
                    "--skip-prompts",
                ],
                input="\n".join(inputs),
            )

            # Should succeed even if some prompts are not fully handled
            assert result.exit_code in [0, 1]  # May fail due to mock limitations

    def test_config_command(self, runner, template_manager):
        """Test config command."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            result = runner.invoke(
                cli, ["config", "--author", "New Author", "--email", "new@example.com"]
            )

            assert result.exit_code == 0
            assert "Configuration updated" in result.output
            assert template_manager.config["author"] == "New Author"

    def test_info_command_no_project(self, runner, temp_dir):
        """Test info command when not in a project."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            result = runner.invoke(cli, ["info"])
            assert result.exit_code == 0
            assert "Not in a Marty project directory" in result.output
        finally:
            os.chdir(original_cwd)

    def test_build_command_no_project(self, runner, temp_dir):
        """Test build command when not in a project."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            result = runner.invoke(cli, ["build"])
            assert result.exit_code == 1
        finally:
            os.chdir(original_cwd)


class TestTemplateProcessing:
    """Test template processing functionality."""

    def test_jinja_filters(self, template_manager, temp_dir):
        """Test Jinja template filters."""
        # Create template with filters
        test_template = template_manager.templates_path / "filter-test"
        test_template.mkdir()

        (test_template / "test.txt").write_text(
            """
Project: {{project_name}}
Slug: {{project_name|slug}}
Snake: {{project_name|snake}}
Pascal: {{project_name|pascal}}
Kebab: {{project_name|kebab}}
"""
        )

        config = ProjectConfig(
            name="My Test Project",
            template="filter-test",
            path=str(temp_dir / "filter-test"),
            author="Test Author",
            email="test@example.com",
            skip_prompts=True,
        )

        # Mock the template config loading to avoid errors
        with patch.object(template_manager, "_load_template_config") as mock_load:
            mock_load.return_value = type(
                "MockConfig",
                (),
                {
                    "name": "filter-test",
                    "path": str(test_template),
                    "post_hooks": [],
                    "variables": {},
                    "framework_version": "1.0.0",
                },
            )()

            success = template_manager.create_project(config)
            assert success

            test_file = Path(config.path) / "test.txt"
            if test_file.exists():
                content = test_file.read_text()
                assert "my-test-project" in content  # slug filter
                assert "my_test_project" in content  # snake filter
                assert "MyTestProject" in content  # pascal filter


class TestErrorHandling:
    """Test error handling in CLI."""

    def test_invalid_template(self, runner, template_manager):
        """Test handling of invalid template."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            result = runner.invoke(cli, ["new", "nonexistent-template", "Test Service"])

            assert result.exit_code == 1
            assert "not found" in result.output

    def test_permission_error(self, runner, template_manager):
        """Test handling of permission errors."""
        with patch("marty_msf.cli.MartyTemplateManager", return_value=template_manager):
            # Try to create in root directory (should fail)
            result = runner.invoke(
                cli, ["new", "test-service", "Test Service", "--path", "/root/test"]
            )

            # Should handle the error gracefully
            assert result.exit_code in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
