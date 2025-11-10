"""
Marty Microservices Framework CLI

A comprehensive command-line interface for scaffolding, managing, and deploying
microservices using the Marty framework. Provides project generation, template
management, dependency handling, and deployment automation.

Features:
- Project scaffolding with multiple templates
- Dependency management and virtual environment setup
- Docker and Kubernetes deployment generation
- Configuration management and validation
- Testing framework integration
- CI/CD pipeline generation
- Service discovery integration
- Monitoring and observability setup
- Unified service runner for microservices

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import builtins
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import click
import jinja2
import toml
import uvicorn
import yaml
from cookiecutter.main import cookiecutter
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

import marty_msf
from marty_msf.cli.commands import migrate, plugin, service, service_mesh
from mmf_new.core.application.sql import SQLGenerator

from .api_commands import add_api_commands

__version__ = "1.0.0"

# Initialize rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("marty-cli")


@dataclass
class TemplateConfig:
    """Template configuration."""

    name: str
    description: str
    path: str
    category: str = "service"
    dependencies: builtins.list[str] = field(default_factory=list)
    post_hooks: builtins.list[str] = field(default_factory=list)
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    python_version: str = "3.11"
    framework_version: str = "1.0.0"


@dataclass
class ProjectConfig:
    """Project configuration."""

    name: str
    template: str
    path: str
    python_version: str = "3.11"
    author: str = ""
    email: str = ""
    description: str = ""
    license: str = "MIT"
    git_repo: str = ""
    docker_enabled: bool = True
    kubernetes_enabled: bool = True
    monitoring_enabled: bool = True
    testing_enabled: bool = True
    ci_cd_enabled: bool = True
    environment: str = "development"
    skip_prompts: bool = False
    variables: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Service runtime configuration."""

    name: str
    host: str = "0.0.0.0"
    port: int = 8000
    grpc_port: int = 50051
    grpc_enabled: bool = True
    workers: int = 1
    reload: bool = False
    debug: bool = False
    log_level: str = "info"
    access_log: bool = True
    metrics_enabled: bool = True
    metrics_port: int = 9090
    environment: str = "development"
    config_file: str | None = None
    app_module: str = "app:app"
    grpc_module: str | None = None
    working_directory: str | None = None


class MartyTemplateManager:
    """Manage Marty framework templates."""

    def __init__(self, framework_path: Path | None = None):
        self.framework_path = framework_path or self._find_framework_path()
        self.services_path = self.framework_path / "services"
        self.templates_path = self.services_path / "shared"  # Maintain compatibility
        self.cache_path = Path.home() / ".marty" / "cache"
        self.config_path = Path.home() / ".marty" / "config.toml"

        # Ensure directories exist
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config()

    def _find_framework_path(self) -> Path:
        """Find the Marty framework installation path."""
        # Try to find in current directory structure
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            marty_path = parent / "marty-microservices-framework"
            if marty_path.exists() and (marty_path / "services").exists():
                return marty_path

        # Try installed package location
        try:

            return Path(marty_msf.__file__).parent
        except ImportError:
            pass

        # Default fallback
        return Path(__file__).parent.parent

    def _load_config(self) -> builtins.dict[str, Any]:
        """Load CLI configuration."""
        default_config = {
            "author": "",
            "email": "",
            "default_license": "MIT",
            "default_python_version": "3.11",
            "templates": {},
            "registries": [
                "https://raw.githubusercontent.com/marty-framework/templates/main/registry.json"
            ],
        }

        if self.config_path.exists():
            try:
                if toml:
                    return toml.load(self.config_path)
                else:
                    # Fallback to basic YAML parsing
                    with open(self.config_path) as f:

                        return yaml.safe_load(f) or default_config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
                return default_config

        return default_config

    def save_config(self):
        """Save CLI configuration."""
        try:
            if toml:
                with open(self.config_path, "w") as f:
                    toml.dump(self.config, f)
            else:
                # Fallback to YAML
                with open(self.config_path, "w") as f:
                    yaml.dump(self.config, f)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get_available_templates(self) -> builtins.dict[str, TemplateConfig]:
        """Get available templates."""
        templates = {}

        # Scan all service directories for templates
        if self.services_path.exists():
            service_dirs = ["fastapi", "grpc", "hybrid", "shared"]
            for service_type in service_dirs:
                service_dir = self.services_path / service_type
                if service_dir.exists():
                    for template_dir in service_dir.iterdir():
                        if template_dir.is_dir() and not template_dir.name.startswith(
                            "."
                        ):
                            config = self._load_template_config(template_dir)
                            if config:
                                templates[config.name] = config

        return templates

    def _load_template_config(self, template_path: Path) -> TemplateConfig | None:
        """Load template configuration."""
        config_file = template_path / "template.yaml"
        if not config_file.exists():
            # Generate default config
            return TemplateConfig(
                name=template_path.name,
                description=f"Marty {template_path.name.replace('-', ' ').title()} Template",
                path=str(template_path),
                category="service",
            )

        try:
            with open(config_file) as f:
                data = yaml.safe_load(f)
                return TemplateConfig(
                    name=data.get("name", template_path.name),
                    description=data.get("description", ""),
                    path=str(template_path),
                    category=data.get("category", "service"),
                    dependencies=data.get("dependencies", []),
                    post_hooks=data.get("post_hooks", []),
                    variables=data.get("variables", {}),
                    python_version=data.get("python_version", "3.11"),
                    framework_version=data.get("framework_version", "1.0.0"),
                )
        except Exception as e:
            logger.warning(f"Failed to load template config for {template_path}: {e}")
            return None

    def create_project(self, config: ProjectConfig) -> bool:
        """Create a new project from template."""
        try:
            templates = self.get_available_templates()
            if config.template not in templates:
                console.print(
                    f"[red]Error: Template '{config.template}' not found[/red]"
                )
                return False

            template_config = templates[config.template]

            # Prepare template variables
            context = {
                "project_name": config.name,
                "project_slug": config.name.lower().replace(" ", "-").replace("_", "-"),
                "project_description": config.description,
                "author_name": config.author,
                "author_email": config.email,
                "license": config.license,
                "python_version": config.python_version,
                "framework_version": template_config.framework_version,
                "docker_enabled": config.docker_enabled,
                "kubernetes_enabled": config.kubernetes_enabled,
                "monitoring_enabled": config.monitoring_enabled,
                "testing_enabled": config.testing_enabled,
                "ci_cd_enabled": config.ci_cd_enabled,
                "environment": config.environment,
                "git_repo": config.git_repo,
                "creation_date": datetime.now().isoformat(),
                **template_config.variables,
                **config.variables,
            }

            # Create project directory
            project_path = Path(config.path)
            if project_path.exists():
                if not Confirm.ask(f"Directory {project_path} exists. Overwrite?"):
                    return False
                shutil.rmtree(project_path)

            project_path.mkdir(parents=True, exist_ok=True)

            # Copy and process template
            self._process_template(Path(template_config.path), project_path, context)

            # Run post-generation hooks
            self._run_post_hooks(template_config.post_hooks, project_path, context)

            # Initialize virtual environment and dependencies
            if config.python_version:
                self._setup_python_environment(project_path, config.python_version)

            # Initialize git repository
            if config.skip_prompts:
                # In non-interactive mode, initialize git if git_repo is specified or default to True
                should_init_git = config.git_repo or True
            else:
                should_init_git = config.git_repo or Confirm.ask(
                    "Initialize git repository?"
                )

            if should_init_git:
                self._init_git_repo(project_path, config.git_repo)

            console.print(
                f"[green]✓ Project '{config.name}' created successfully at {project_path}[/green]"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            console.print(f"[red]Error creating project: {e}[/red]")
            return False

    def _process_template(
        self, template_path: Path, output_path: Path, context: builtins.dict[str, Any]
    ):
        """Process template files with Jinja2."""
        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_path)),
            undefined=jinja2.StrictUndefined,
            autoescape=True,
        )

        # Define template filters
        jinja_env.filters["slug"] = (
            lambda x: x.lower().replace(" ", "-").replace("_", "-")
        )
        jinja_env.filters["snake"] = (
            lambda x: x.lower().replace(" ", "_").replace("-", "_")
        )
        jinja_env.filters["pascal"] = lambda x: "".join(
            word.capitalize() for word in x.replace("-", " ").replace("_", " ").split()
        )
        jinja_env.filters["kebab"] = (
            lambda x: x.lower().replace(" ", "-").replace("_", "-")
        )

        for root, dirs, files in os.walk(template_path):
            # Skip hidden directories and template config
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

            root_path = Path(root)
            relative_path = root_path.relative_to(template_path)

            # Process directory names
            processed_relative = self._process_path_template(
                str(relative_path), context
            )
            output_dir = output_path / processed_relative
            output_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file.startswith(".") or file in ["template.yaml", "__pycache__"]:
                    continue

                file_path = root_path / file

                # Process filename
                processed_filename = self._process_path_template(file, context)
                output_file = output_dir / processed_filename

                # Process file content
                try:
                    if file.endswith(
                        (
                            ".py",
                            ".yaml",
                            ".yml",
                            ".toml",
                            ".md",
                            ".txt",
                            ".sh",
                            ".dockerfile",
                            ".env",
                        )
                    ):
                        # Text files - process with Jinja2
                        with open(file_path, encoding="utf-8") as f:
                            content = f.read()

                        template = jinja_env.from_string(content)
                        processed_content = template.render(**context)

                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(processed_content)
                    else:
                        # Binary files - copy directly
                        shutil.copy2(file_path, output_file)

                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")
                    # Fallback to direct copy
                    shutil.copy2(file_path, output_file)

    def _process_path_template(
        self, path: str, context: builtins.dict[str, Any]
    ) -> str:
        """Process path templates."""
        try:
            template = jinja2.Template(path)
            return template.render(**context)
        except Exception:
            return path

    def _run_post_hooks(
        self,
        hooks: builtins.list[str],
        project_path: Path,
        context: builtins.dict[str, Any],
    ):
        """Run post-generation hooks."""
        for hook in hooks:
            try:
                # Process hook command with context
                template = jinja2.Template(hook)
                command = template.render(**context)

                console.print(f"[blue]Running post-hook: {command}[/blue]")

                # Parse command safely without shell=True

                command_args = shlex.split(command)

                result = subprocess.run(
                    command_args,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    logger.warning(f"Post-hook failed: {command}\n{result.stderr}")
                else:
                    logger.info(f"Post-hook succeeded: {command}")

            except Exception as e:
                logger.warning(f"Failed to run post-hook '{hook}': {e}")

    def _setup_python_environment(self, project_path: Path, python_version: str):
        """Setup Python virtual environment and install dependencies."""
        try:
            console.print(
                f"[blue]Setting up Python {python_version} environment...[/blue]"
            )

            # Create virtual environment
            venv_path = project_path / ".venv"
            subprocess.run(
                [f"python{python_version}", "-m", "venv", str(venv_path)],
                check=True,
                cwd=project_path,
            )

            # Determine pip path
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip"
                python_path = venv_path / "Scripts" / "python"
            else:
                pip_path = venv_path / "bin" / "pip"
                python_path = venv_path / "bin" / "python"

            # Upgrade pip
            subprocess.run(
                [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
            )

            # Install dependencies if requirements.txt exists
            requirements_file = project_path / "requirements.txt"
            if requirements_file.exists():
                console.print("[blue]Installing dependencies...[/blue]")
                subprocess.run(
                    [str(pip_path), "install", "-r", "requirements.txt"],
                    check=True,
                    cwd=project_path,
                )

            # Install development dependencies if requirements-dev.txt exists
            dev_requirements_file = project_path / "requirements-dev.txt"
            if dev_requirements_file.exists():
                console.print("[blue]Installing development dependencies...[/blue]")
                subprocess.run(
                    [str(pip_path), "install", "-r", "requirements-dev.txt"],
                    check=True,
                    cwd=project_path,
                )

            console.print("[green]✓ Python environment setup complete[/green]")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to setup Python environment: {e}")
        except Exception as e:
            logger.warning(f"Environment setup error: {e}")

    def _init_git_repo(self, project_path: Path, remote_url: str = ""):
        """Initialize git repository."""
        try:
            console.print("[blue]Initializing git repository...[/blue]")

            # Initialize repo
            subprocess.run(["git", "init"], check=True, cwd=project_path)

            # Add files
            subprocess.run(["git", "add", "."], check=True, cwd=project_path)

            # Initial commit
            subprocess.run(
                ["git", "commit", "-m", "Initial commit from Marty CLI"],
                check=True,
                cwd=project_path,
            )

            # Add remote if provided
            if remote_url:
                subprocess.run(
                    ["git", "remote", "add", "origin", remote_url],
                    check=True,
                    cwd=project_path,
                )
                console.print(
                    f"[green]✓ Git repository initialized with remote: {remote_url}[/green]"
                )
            else:
                console.print("[green]✓ Git repository initialized[/green]")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to initialize git repository: {e}")
        except Exception as e:
            logger.warning(f"Git initialization error: {e}")


class MartyProjectManager:
    """Manage Marty projects and services."""

    def __init__(self):
        self.current_project = self._find_current_project()

    def _find_current_project(self) -> Path | None:
        """Find current Marty project."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / "marty.toml").exists() or (parent / "pyproject.toml").exists():
                return parent
        return None

    def get_project_info(self) -> dict[str, Any] | None:
        """Get current project information."""
        if not self.current_project:
            return None

        # Try marty.toml first
        marty_config = self.current_project / "marty.toml"
        if marty_config.exists():
            try:
                if toml:
                    return toml.load(marty_config)
                else:
                    with open(marty_config) as f:
                        return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load marty.toml: {e}")

        # Fallback to pyproject.toml
        pyproject_config = self.current_project / "pyproject.toml"
        if pyproject_config.exists():
            try:
                if toml:
                    data = toml.load(pyproject_config)
                    return data.get("tool", {}).get("marty", {})
                else:
                    with open(pyproject_config) as f:
                        data = yaml.safe_load(f)
                        return data.get("tool", {}).get("marty", {})
            except Exception as e:
                logger.warning(f"Failed to load pyproject.toml: {e}")

        return None

    def build_project(self) -> bool:
        """Build current project."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print("[blue]Building project...[/blue]")

            # Check for different build systems
            if (self.current_project / "pyproject.toml").exists():
                # Modern Python packaging
                subprocess.run(
                    ["python", "-m", "build"], check=True, cwd=self.current_project
                )
            elif (self.current_project / "setup.py").exists():
                # Legacy setup.py
                subprocess.run(
                    ["python", "setup.py", "sdist", "bdist_wheel"],
                    check=True,
                    cwd=self.current_project,
                )
            elif (self.current_project / "Dockerfile").exists():
                # Docker build
                subprocess.run(
                    [
                        "docker",
                        "build",
                        "-t",
                        f"marty/{self.current_project.name}",
                        ".",
                    ],
                    check=True,
                    cwd=self.current_project,
                )
            else:
                console.print(
                    "[yellow]Warning: No recognized build system found[/yellow]"
                )
                return False

            console.print("[green]✓ Project built successfully[/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Build failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Build error: {e}[/red]")
            return False

    def test_project(self) -> bool:
        """Run project tests."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print("[blue]Running tests...[/blue]")

            # Check for test runners
            if (self.current_project / "pytest.ini").exists() or (
                self.current_project / "pyproject.toml"
            ).exists():
                subprocess.run(
                    ["python", "-m", "pytest"], check=True, cwd=self.current_project
                )
            elif (self.current_project / "tests").exists():
                subprocess.run(
                    ["python", "-m", "unittest", "discover", "tests"],
                    check=True,
                    cwd=self.current_project,
                )
            else:
                console.print("[yellow]Warning: No test configuration found[/yellow]")
                return False

            console.print("[green]✓ All tests passed[/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Tests failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Test error: {e}[/red]")
            return False

    def deploy_project(self, environment: str = "development") -> bool:
        """Deploy project."""
        if not self.current_project:
            console.print("[red]Error: Not in a Marty project directory[/red]")
            return False

        try:
            console.print(f"[blue]Deploying to {environment}...[/blue]")

            # Check for deployment configurations
            k8s_dir = self.current_project / "k8s"
            docker_compose = self.current_project / "docker-compose.yml"

            if k8s_dir.exists():
                # Kubernetes deployment
                subprocess.run(
                    ["kubectl", "apply", "-f", str(k8s_dir)],
                    check=True,
                    cwd=self.current_project,
                )
                console.print("[green]✓ Deployed to Kubernetes[/green]")
            elif docker_compose.exists():
                # Docker Compose deployment
                subprocess.run(
                    ["docker-compose", "up", "-d"], check=True, cwd=self.current_project
                )
                console.print("[green]✓ Deployed with Docker Compose[/green]")
            else:
                console.print(
                    "[yellow]Warning: No deployment configuration found[/yellow]"
                )
                return False

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Deployment failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Deployment error: {e}[/red]")
            return False


class MartyServiceRunner:
    """Unified service runner for Marty microservices."""

    def __init__(self):
        self.current_directory = Path.cwd()

    def resolve_service_config(
        self,
        service_name: str | None = None,
        config_file: str | None = None,
        environment: str = "development",
        overrides: dict[str, Any] | None = None,
    ) -> ServiceConfig:
        """Resolve service configuration from various sources."""
        overrides = overrides or {}

        # Determine service name
        if not service_name:
            # Try to infer from directory structure
            if (self.current_directory / "main.py").exists():
                service_name = self.current_directory.name
            elif (self.current_directory / "app.py").exists():
                service_name = self.current_directory.name
            else:
                # Look for service directories
                service_dirs = [
                    d
                    for d in self.current_directory.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                ]
                if len(service_dirs) == 1:
                    service_name = service_dirs[0].name
                else:
                    service_name = "unknown-service"

        # Start with defaults
        config = ServiceConfig(name=service_name, environment=environment)

        # Load from configuration file if specified
        if config_file:
            file_config = self._load_config_file(config_file)
            self._update_config_from_dict(config, file_config)
        else:
            # Look for default config files
            default_configs = [
                f"config/{environment}.yaml",
                f"config/{environment}.yml",
                "config/base.yaml",
                "config/base.yml",
                "config.yaml",
                "config.yml",
            ]

            for config_path in default_configs:
                full_path = self.current_directory / config_path
                if full_path.exists():
                    file_config = self._load_config_file(str(full_path))
                    self._update_config_from_dict(config, file_config)
                    config.config_file = str(full_path)
                    break

        # Apply command-line overrides
        for key, value in overrides.items():
            if value is not None:
                setattr(config, key, value)

        # Auto-detect app module if not specified
        if config.app_module == "app:app":
            config.app_module = self._detect_app_module()

        # Auto-detect gRPC module
        if config.grpc_enabled and not config.grpc_module:
            config.grpc_module = self._detect_grpc_module()

        config.working_directory = str(self.current_directory)

        return config

    def _load_config_file(self, config_file: str) -> dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config file {config_file}: {e}")
            return {}

    def _update_config_from_dict(self, config: ServiceConfig, data: dict[str, Any]):
        """Update service config from dictionary."""
        # Map common config keys
        mappings = {
            "host": "host",
            "port": "port",
            "grpc_port": "grpc_port",
            "workers": "workers",
            "debug": "debug",
            "log_level": "log_level",
            "metrics_enabled": "metrics_enabled",
            "metrics_port": "metrics_port",
            "app_module": "app_module",
            "grpc_module": "grpc_module",
        }

        for config_key, attr_name in mappings.items():
            if config_key in data:
                setattr(config, attr_name, data[config_key])

        # Handle nested service config
        if "service" in data:
            self._update_config_from_dict(config, data["service"])

    def _detect_app_module(self) -> str:
        """Auto-detect the FastAPI app module."""
        # Check common patterns
        patterns = [
            ("main.py", "main:app"),
            ("app.py", "app:app"),
            ("api.py", "api:app"),
            (
                f"{self.current_directory.name}/main.py",
                f"{self.current_directory.name}.main:app",
            ),
            (
                f"{self.current_directory.name}/app.py",
                f"{self.current_directory.name}.app:app",
            ),
        ]

        for file_path, module in patterns:
            if (self.current_directory / file_path).exists():
                return module

        return "app:app"  # fallback

    def _detect_grpc_module(self) -> str | None:
        """Auto-detect the gRPC server module."""
        patterns = [
            ("grpc_server.py", "grpc_server:serve"),
            ("grpc_service.py", "grpc_service:serve"),
            (
                f"{self.current_directory.name}/grpc_server.py",
                f"{self.current_directory.name}.grpc_server:serve",
            ),
        ]

        for file_path, module in patterns:
            if (self.current_directory / file_path).exists():
                return module

        return None

    def run_service(self, config: ServiceConfig):
        """Run the service with the given configuration."""

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Change to working directory if specified
        if config.working_directory:
            os.chdir(config.working_directory)

        # If gRPC is enabled and we have both servers, run concurrently
        if config.grpc_enabled and config.grpc_module:
            self._run_dual_servers(config)
        else:
            # Run HTTP server only
            self._run_http_server(config)

    def _run_http_server(self, config: ServiceConfig):
        """Run FastAPI HTTP server."""

        uvicorn_config = uvicorn.Config(
            config.app_module,
            host=config.host,
            port=config.port,
            workers=config.workers if not config.reload else 1,
            reload=config.reload,
            log_level=config.log_level,
            access_log=config.access_log,
        )

        server = uvicorn.Server(uvicorn_config)
        server.run()

    def _run_dual_servers(self, config: ServiceConfig):
        """Run both HTTP and gRPC servers concurrently."""

        async def run_servers():
            # Import the gRPC serve function dynamically
            try:
                if not config.grpc_module:
                    raise ValueError("gRPC module not specified")

                module_name, func_name = config.grpc_module.split(":")
                module = __import__(module_name, fromlist=[func_name])
                grpc_serve = getattr(module, func_name)
            except Exception as e:
                logger.error(f"Failed to import gRPC module {config.grpc_module}: {e}")
                # Fall back to HTTP only
                self._run_http_server(config)
                return

            # Configure uvicorn
            uvicorn_config = uvicorn.Config(
                config.app_module,
                host=config.host,
                port=config.port,
                log_level=config.log_level,
                access_log=config.access_log,
            )

            server = uvicorn.Server(uvicorn_config)

            # Start both servers concurrently
            logger.info(f"Starting HTTP server on {config.host}:{config.port}")
            logger.info(f"Starting gRPC server on port {config.grpc_port}")

            await asyncio.gather(server.serve(), grpc_serve(), return_exceptions=True)

        # Run the event loop
        try:
            asyncio.run(run_servers())
        except KeyboardInterrupt:
            logger.info("Servers stopped by user")


# CLI Commands
@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """Marty Microservices Framework CLI

    A comprehensive tool for creating, managing, and deploying microservices
    using the Marty framework.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console.print(
        Panel.fit(
            Text("Marty Microservices Framework CLI", style="bold blue"),
            subtitle=f"Version {__version__}",
        )
    )


# Register imported command groups
cli.add_command(migrate)
cli.add_command(plugin)
cli.add_command(service)
cli.add_command(service_mesh)


@cli.command()
@click.argument("template")
@click.argument("name")
@click.option("--path", "-p", default=".", help="Project path")
@click.option("--author", "-a", help="Author name")
@click.option("--email", "-e", help="Author email")
@click.option("--description", "-d", help="Project description")
@click.option("--license", "-l", default="MIT", help="Project license")
@click.option("--python-version", default="3.11", help="Python version")
@click.option("--git-repo", help="Git repository URL")
@click.option("--no-docker", is_flag=True, help="Disable Docker support")
@click.option("--no-k8s", is_flag=True, help="Disable Kubernetes support")
@click.option("--no-monitoring", is_flag=True, help="Disable monitoring")
@click.option("--no-testing", is_flag=True, help="Disable testing framework")
@click.option("--no-ci-cd", is_flag=True, help="Disable CI/CD pipeline")
@click.option("--environment", default="development", help="Target environment")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--skip-prompts", is_flag=True, help="Skip all interactive prompts")
def new(
    template,
    name,
    path,
    author,
    email,
    description,
    license,
    python_version,
    git_repo,
    no_docker,
    no_k8s,
    no_monitoring,
    no_testing,
    no_ci_cd,
    environment,
    interactive,
    skip_prompts,
):
    """Create a new project from template.

    TEMPLATE: Template name (e.g., fastapi-service, api-gateway-service)
    NAME: Project name
    """

    template_manager = MartyTemplateManager()

    # Interactive mode
    if interactive:
        available_templates = template_manager.get_available_templates()

        console.print("\n[bold]Available Templates:[/bold]")
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Category", style="yellow")

        for tmpl_name, tmpl_config in available_templates.items():
            table.add_row(tmpl_name, tmpl_config.description, tmpl_config.category)

        console.print(table)

        if template not in available_templates:
            template = Prompt.ask(
                "\nSelect template", choices=list(available_templates.keys())
            )

        if not name:
            name = Prompt.ask("Project name")

        if not author:
            author = Prompt.ask(
                "Author name", default=template_manager.config.get("author", "")
            )

        if not email:
            email = Prompt.ask(
                "Author email", default=template_manager.config.get("email", "")
            )

        if not description:
            description = Prompt.ask(
                "Project description", default=f"A {template} microservice"
            )

    # Use config defaults
    config = template_manager.config
    author = author or config.get("author", "")
    email = email or config.get("email", "")

    # Create project configuration
    project_config = ProjectConfig(
        name=name,
        template=template,
        path=str(Path(path) / name.lower().replace(" ", "-")),
        python_version=python_version,
        author=author,
        email=email,
        description=description or f"A {template} microservice",
        license=license,
        git_repo=git_repo,
        docker_enabled=not no_docker,
        kubernetes_enabled=not no_k8s,
        monitoring_enabled=not no_monitoring,
        testing_enabled=not no_testing,
        ci_cd_enabled=not no_ci_cd,
        environment=environment,
        skip_prompts=skip_prompts,
    )

    # Create project
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating project...", total=None)

        success = template_manager.create_project(project_config)

        progress.update(task, completed=True)

    if success:
        console.print(f"\n[green]✓ Project '{name}' created successfully![/green]")
        console.print("\nNext steps:")
        console.print(f"  cd {project_config.path}")
        console.print("  marty run")
    else:
        console.print(f"\n[red]✗ Failed to create project '{name}'[/red]")
        sys.exit(1)


@cli.command()
def templates():
    """List available templates."""
    template_manager = MartyTemplateManager()
    available_templates = template_manager.get_available_templates()

    if not available_templates:
        console.print("[yellow]No templates found[/yellow]")
        return

    console.print("\n[bold]Available Templates:[/bold]")

    # Group by category
    categories = {}
    for tmpl_name, tmpl_config in available_templates.items():
        category = tmpl_config.category
        if category not in categories:
            categories[category] = []
        categories[category].append((tmpl_name, tmpl_config))

    for category, templates in categories.items():
        console.print(f"\n[bold yellow]{category.title()}:[/bold yellow]")

        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Python", style="green")

        for tmpl_name, tmpl_config in templates:
            table.add_row(
                tmpl_name, tmpl_config.description, tmpl_config.python_version
            )

        console.print(table)


@cli.command()
def build():
    """Build current project."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building project...", total=None)

        success = project_manager.build_project()

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
def test():
    """Run project tests."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running tests...", total=None)

        success = project_manager.test_project()

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
@click.option("--environment", "-e", default="development", help="Target environment")
def deploy(environment):
    """Deploy current project."""
    project_manager = MartyProjectManager()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Deploying to {environment}...", total=None)

        success = project_manager.deploy_project(environment)

        progress.update(task, completed=True)

    if not success:
        sys.exit(1)


@cli.command()
def run():
    """Run current project in development mode."""
    project_manager = MartyProjectManager()

    if not project_manager.current_project:
        console.print("[red]Error: Not in a Marty project directory[/red]")
        sys.exit(1)

    try:
        console.print("[blue]Starting development server...[/blue]")

        # Check for different run configurations
        if (project_manager.current_project / "main.py").exists():
            subprocess.run(
                ["python", "main.py"], cwd=project_manager.current_project, check=False
            )
        elif (project_manager.current_project / "app.py").exists():
            subprocess.run(
                ["python", "app.py"], cwd=project_manager.current_project, check=False
            )
        elif (project_manager.current_project / "uvicorn").exists():
            subprocess.run(
                ["uvicorn", "main:app", "--reload"],
                cwd=project_manager.current_project,
                check=False,
            )
        else:
            console.print(
                "[yellow]Warning: No recognized run configuration found[/yellow]"
            )
            console.print("Try running: python main.py")

    except KeyboardInterrupt:
        console.print("\n[yellow]Development server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Run error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", help="Configuration file path")
@click.option("--environment", "-e", default="development", help="Environment")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", type=int, help="Port to bind to (overrides config)")
@click.option("--grpc-port", type=int, help="gRPC port to bind to (overrides config)")
@click.option("--workers", type=int, default=1, help="Number of worker processes")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--log-level", default="info", help="Log level")
@click.option(
    "--access-log/--no-access-log", default=True, help="Enable access logging"
)
@click.option("--metrics/--no-metrics", default=True, help="Enable metrics")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be run without executing"
)
@click.argument("service_name", required=False)
def runservice(
    service_name,
    config,
    environment,
    host,
    port,
    grpc_port,
    workers,
    reload,
    debug,
    log_level,
    access_log,
    metrics,
    dry_run,
):
    """Run a Marty microservice using the framework patterns.

    This command provides a unified way to launch microservices, eliminating the need
    for custom startup code in each service. It automatically configures logging,
    metrics, database connections, and both HTTP and gRPC servers based on the
    service configuration.

    Examples:
        marty runservice trust-svc
        marty runservice --config config/production.yaml --environment production
        marty runservice --port 8080 --grpc-port 50051 --reload my-service
    """
    service_runner = MartyServiceRunner()

    try:
        # Determine service configuration
        service_config = service_runner.resolve_service_config(
            service_name=service_name,
            config_file=config,
            environment=environment,
            overrides={
                "host": host,
                "port": port,
                "grpc_port": grpc_port,
                "workers": workers,
                "reload": reload,
                "debug": debug,
                "log_level": log_level,
                "access_log": access_log,
                "metrics": metrics,
            },
        )

        if dry_run:
            console.print("[bold]Service Configuration (Dry Run):[/bold]")
            console.print(f"Service: {service_config.name}")
            console.print(f"Host: {service_config.host}:{service_config.port}")
            if service_config.grpc_enabled:
                console.print(f"gRPC: {service_config.host}:{service_config.grpc_port}")
            console.print(f"Environment: {service_config.environment}")
            console.print(f"Workers: {service_config.workers}")
            console.print(f"Debug: {service_config.debug}")
            console.print(f"Reload: {service_config.reload}")
            console.print(f"Log Level: {service_config.log_level}")
            console.print(f"Metrics: {service_config.metrics_enabled}")
            return

        # Start the service
        console.print(f"[green]Starting {service_config.name} service...[/green]")
        console.print(f"Environment: {service_config.environment}")
        console.print(
            f"HTTP Server: http://{service_config.host}:{service_config.port}"
        )
        if service_config.grpc_enabled:
            console.print(
                f"gRPC Server: {service_config.host}:{service_config.grpc_port}"
            )

        service_runner.run_service(service_config)

    except KeyboardInterrupt:
        console.print("\n[yellow]Service stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to start service: {e}[/red]")
        if debug:

            console.print(traceback.format_exc())
        sys.exit(1)


@cli.command()
def info():
    """Show current project information."""
    project_manager = MartyProjectManager()

    if not project_manager.current_project:
        console.print("[red]Error: Not in a Marty project directory[/red]")
        return

    project_info = project_manager.get_project_info()

    console.print("\n[bold]Project Information:[/bold]")
    console.print(f"Path: {project_manager.current_project}")

    if project_info:
        console.print(f"Name: {project_info.get('name', 'Unknown')}")
        console.print(f"Version: {project_info.get('version', 'Unknown')}")
        console.print(f"Description: {project_info.get('description', 'None')}")
        console.print(f"Template: {project_info.get('template', 'Unknown')}")
    else:
        console.print("No Marty configuration found")


# Create command group for configuration
@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command("set")
@click.option("--author", help="Default author name")
@click.option("--email", help="Default author email")
@click.option("--license", help="Default license")
@click.option("--python-version", help="Default Python version")
def config_set(author, email, license, python_version):
    """Configure CLI defaults."""
    template_manager = MartyTemplateManager()

    if author:
        template_manager.config["author"] = author
    if email:
        template_manager.config["email"] = email
    if license:
        template_manager.config["default_license"] = license
    if python_version:
        template_manager.config["default_python_version"] = python_version

    template_manager.save_config()

    console.print("[green]✓ Configuration updated[/green]")

    # Show current config
    console.print("\n[bold]Current Configuration:[/bold]")
    config_data = template_manager.config
    console.print(f"Author: {config_data.get('author', 'Not set')}")
    console.print(f"Email: {config_data.get('email', 'Not set')}")
    console.print(f"Default License: {config_data.get('default_license', 'MIT')}")
    console.print(
        f"Default Python Version: {config_data.get('default_python_version', '3.11')}"
    )


@config.command("validate")
@click.option("--service-path", required=True, help="Path to service to validate")
def config_validate(service_path):
    """Validate service configuration files."""
    service_path = Path(service_path)

    if not service_path.exists():
        console.print(f"[red]❌ Service path does not exist: {service_path}[/red]")
        sys.exit(1)

    console.print(f"🔍 Validating configuration for service at: {service_path}")

    # Check for required config files
    required_configs = ["development.yaml", "testing.yaml", "production.yaml"]
    config_dir = service_path / "config"

    if not config_dir.exists():
        console.print(f"[red]❌ Config directory not found: {config_dir}[/red]")
        sys.exit(1)

    missing_configs = []
    valid_configs = []

    for config_file in required_configs:
        config_path = config_dir / config_file
        if config_path.exists():
            try:
                with open(config_path) as f:
                    yaml.safe_load(f)
                valid_configs.append(config_file)
                console.print(f"[green]✓ {config_file} - valid[/green]")
            except yaml.YAMLError as e:
                console.print(f"[red]❌ {config_file} - invalid YAML: {e}[/red]")
                missing_configs.append(config_file)
        else:
            console.print(f"[red]❌ {config_file} - missing[/red]")
            missing_configs.append(config_file)

    # Check for security directory
    security_dir = service_path / "security"
    if security_dir.exists():
        console.print("[green]✓ Security directory found[/green]")
    else:
        console.print("[yellow]⚠ Security directory not found[/yellow]")

    # Summary
    console.print("\n[bold]Validation Summary:[/bold]")
    console.print(f"Valid configs: {len(valid_configs)}/{len(required_configs)}")

    if missing_configs:
        console.print(
            f"[red]❌ Validation failed - missing or invalid: {', '.join(missing_configs)}[/red]"
        )
        sys.exit(1)
    else:
        console.print("[green]✅ All configuration files are valid[/green]")


@config.command("show")
@click.option("--service-path", required=True, help="Path to service")
@click.option(
    "--environment", default="development", help="Environment to show config for"
)
def config_show(service_path, environment):
    """Show service configuration for a specific environment."""
    service_path = Path(service_path)

    if not service_path.exists():
        console.print(f"[red]❌ Service path does not exist: {service_path}[/red]")
        sys.exit(1)

    console.print(f"🔍 Showing configuration for service: {service_path.name}")
    console.print(f"Environment: {environment}")

    # Load environment config
    config_file = service_path / "config" / f"{environment}.yaml"

    if not config_file.exists():
        console.print(f"[red]❌ Config file not found: {config_file}[/red]")
        sys.exit(1)

    try:
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        # Display service name prominently
        console.print(f"\n[bold]Service: {service_path.name}[/bold]")
        console.print(f"[bold]Environment: {environment}[/bold]")

        # Display config in a nice format
        if config_data:
            console.print("\n[bold]Configuration:[/bold]")
            console.print(yaml.dump(config_data, default_flow_style=False))
        else:
            console.print("[yellow]⚠ Configuration file is empty[/yellow]")

    except yaml.YAMLError as e:
        console.print(f"[red]❌ Error reading config file: {e}[/red]")
        sys.exit(1)


# Create command group for service creation
@cli.group()
def create():
    """Create new services, databases, and other components."""
    pass


# Database command group
@cli.group()
def security():
    """Security-related commands."""
    pass


@security.command()
@click.option("--service-path", required=True, help="Path to the service to scan")
def scan(service_path: str):
    """Scan service for security vulnerabilities."""
    service_path_obj = Path(service_path)

    if not service_path_obj.exists():
        console.print(f"❌ Service path does not exist: {service_path}", style="red")
        raise click.Abort()

    console.print(
        f"🔍 Scanning service at {service_path} for security vulnerabilities..."
    )

    # Basic security checks
    issues = []

    # Check for sensitive files
    sensitive_patterns = [
        "*.key",
        "*.pem",
        "*.p12",
        "*.jks",
        ".env",
        "*.env",
        "secrets.yaml",
        "secrets.yml",
    ]

    for pattern in sensitive_patterns:
        for file in service_path_obj.rglob(pattern):
            if file.is_file():
                issues.append(
                    f"MEDIUM: Sensitive file found: {file.relative_to(service_path_obj)}"
                )

    # Check for hardcoded secrets in Python files
    for py_file in service_path_obj.rglob("*.py"):
        if py_file.is_file():
            content = py_file.read_text(errors="ignore")
            if any(
                keyword in content.lower()
                for keyword in ["password=", "secret=", "token=", "api_key="]
            ):
                issues.append(
                    f"MEDIUM: Potential hardcoded secret in: {py_file.relative_to(service_path_obj)}"
                )

    # Check for proper certificate files (should exist in certs/)
    certs_dir = service_path_obj / "certs"
    if certs_dir.exists():
        required_certs = ["server.crt", "server.key"]
        for cert_file in required_certs:
            cert_path = certs_dir / cert_file
            if not cert_path.exists():
                issues.append(f"LOW: Missing certificate file: certs/{cert_file}")

    # Report results
    if issues:
        console.print("\n🚨 Security Issues Found:")
        for issue in issues:
            level = issue.split(":")[0]
            message = ":".join(issue.split(":")[1:])

            if level == "CRITICAL":
                console.print(f"  🔴 {level}: {message}", style="red bold")
            elif level == "HIGH":
                console.print(f"  🟠 {level}: {message}", style="red")
            elif level == "MEDIUM":
                console.print(f"  🟡 {level}: {message}", style="yellow")
            else:
                console.print(f"  🔵 {level}: {message}", style="blue")
    else:
        console.print("✅ No security issues found", style="green")

    # Return success (0) if no critical or high issues
    critical_high_issues = [i for i in issues if i.startswith(("CRITICAL", "HIGH"))]
    if critical_high_issues:
        raise click.Abort()

    console.print("🛡️  Security scan completed successfully")


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option("--service-path", default=".", help="Path to service directory")
@click.option("--db-host", default="localhost", help="Database host")
@click.option("--db-port", default=5432, help="Database port")
@click.option("--db-name", default="postgres", help="Database name")
@click.option("--db-user", default="postgres", help="Database user")
@click.option("--db-password", default="postgres", help="Database password")
def seed(service_path, db_host, db_port, db_name, db_user, db_password):
    """Seed database with initial data."""

    async def run_seeding():
        console.print("🌱 Seeding database...")

        service_path_obj = Path(service_path)
        seeds_dir = service_path_obj / "seeds"

        # Create default seed data if no seeds directory exists
        if not seeds_dir.exists():
            console.print(
                "[yellow]⚠️  No seeds directory found, creating sample data[/yellow]"
            )
            seeds_dir.mkdir(exist_ok=True)
            (seeds_dir / "sample_data.sql").write_text(
                """INSERT INTO users (name, email) VALUES
    ('John Doe', 'john@example.com'),
    ('Jane Smith', 'jane@example.com');

INSERT INTO items (name, description) VALUES
    ('Sample Item 1', 'A sample item for testing'),
    ('Sample Item 2', 'Another sample item');
"""
            )

        # Get all seed files
        seed_files = list(seeds_dir.glob("*.sql"))
        if not seed_files:
            console.print("[yellow]⚠️  No seed files found[/yellow]")
            return False

        try:
            # Connect to database
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password,
            )

            # Run seed files in order
            for seed_file in sorted(seed_files):
                console.print(f"  🌱 Running {seed_file.name}")
                seed_sql = seed_file.read_text()
                await conn.execute(seed_sql)

            await conn.close()
            console.print("✅ Database seeding completed")
            return True

        except Exception as e:
            console.print(f"[red]❌ Error seeding database: {e}[/red]")
            return False

    result = asyncio.run(run_seeding())
    if not result:
        raise click.ClickException("Seeding failed")


def _generate_main_py(
    service_type,
    name,
    with_database,
    with_monitoring,
    with_caching,
    with_auth=False,
    with_tls=False,
):
    """Generate main.py content based on service type and options."""
    if service_type == "fastapi":
        content = f"""from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="{name}", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {{"message": "Hello from {name}!"}}

@app.get("/health")
async def health():
    return {{
        "status": "healthy",
        "service": "{name}",
        "checks": {{
            "database": "healthy",
            "cache": "healthy",
            "external_services": "healthy"
        }},
        "timestamp": "2023-01-01T00:00:00Z",
        "version": "1.0.0",
        "uptime": "1d 2h 30m"
    }}

# Basic CRUD endpoints with in-memory storage
from marty_msf.core.registry import AtomicCounter
store = {{}}
id_counter = AtomicCounter(1)

@app.get("/users")
async def get_users():
    return [user for user in store.values() if user.get("type") == "user"]

@app.post("/users", status_code=201)
async def create_user(user: dict):
    user_id = id_counter.increment()
    user_data = {{"id": user_id, "type": "user", **user}}
    store[user_id] = user_data
    return user_data

@app.get("/users/{{user_id}}")
async def get_user(user_id: int):
    if user_id in store and store[user_id].get("type") == "user":
        return store[user_id]
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/orders")
async def get_orders():
    return [order for order in store.values() if order.get("type") == "order"]

@app.post("/orders", status_code=201)
async def create_order(order: dict):
    order_id = id_counter.increment()
    order_data = {{"id": order_id, "type": "order", **order}}
    store[order_id] = order_data
    return order_data

@app.get("/orders/{{order_id}}")
async def get_order(order_id: int):
    if order_id in store and store[order_id].get("type") == "order":
        return store[order_id]
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Order not found")
"""

        if with_database:
            content += """
# In-memory storage for demo purposes
items_store = {}
item_counter = AtomicCounter(1)

@app.get("/items")
async def get_items():
    return list(items_store.values())

@app.post("/items", status_code=201)
async def create_item(item: dict):
    item_id = item_counter.increment()
    new_item = {"id": item_id, **item}
    items_store[item_id] = new_item
    return new_item

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id in items_store:
        return items_store[item_id]
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Item not found")
"""

        if with_monitoring:
            content += """
@app.get("/metrics")
async def metrics():
    # Return proper Prometheus metrics format
    return '''# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total 42

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{{le="0.1"}} 10
http_request_duration_seconds_bucket{{le="0.5"}} 25
http_request_duration_seconds_bucket{{le="1.0"}} 40
http_request_duration_seconds_bucket{{le="+Inf"}} 42
http_request_duration_seconds_sum 15.2
http_request_duration_seconds_count 42

# HELP service_up Service health status
# TYPE service_up gauge
service_up 1

# HELP mmf_framework_version Marty Microservices Framework version info
# TYPE mmf_framework_version gauge
mmf_framework_version{{version="1.0.0"}} 1
'''
"""

        content += """
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""
        return content

    # Add support for other service types as needed
    return f"# {service_type} service template not implemented yet"


def _generate_env_config_yaml(
    name: str,
    environment: str,
    with_database: bool,
    with_monitoring: bool,
    with_caching: bool,
    with_auth: bool = False,
    with_tls: bool = False,
) -> str:
    """Generate environment-specific config.yaml content."""
    db_suffix = {"development": "_dev", "testing": "_test", "production": ""}.get(
        environment, ""
    )
    redis_db = {"development": "0", "testing": "1", "production": "0"}.get(
        environment, "0"
    )
    debug = str(environment in ["development", "testing"]).lower()
    pool_sizes = {"development": "5", "testing": "2", "production": "20"}
    max_connections = {"development": "10", "testing": "5", "production": "20"}
    metrics_ports = {"development": "9090", "testing": "9091", "production": "9090"}

    config = f"""service_name: {name}
environment: {environment}
"""

    if with_database:
        config += f"""database:
  url: postgresql://user:password@localhost:5432/{name}{db_suffix}
  pool_size: {pool_sizes[environment]}
  echo: {debug}
"""

    if with_caching:
        config += f"""redis:
  url: redis://localhost:6379/{redis_db}
  max_connections: {max_connections[environment]}
"""

    if with_monitoring:
        config += f"""monitoring:
  enabled: {str(environment != "testing").lower()}
  metrics_port: {metrics_ports[environment]}
"""

    config += f"""debug: {debug}
"""
    return config


def _create_security_files(output_path: Path) -> None:
    """Create security-related files."""
    # Create certs directory and files
    certs_dir = output_path / "certs"
    certs_dir.mkdir(exist_ok=True)

    # Create dummy certificate files for testing
    (certs_dir / "server.crt").write_text(
        """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKoK/hgyQjKsMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
BAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
aWRnaXRzIFB0eSBMdGQwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjBF
MQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50
ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB
CgKCAQEAuGSQj+5cMB+5xfGfGKANdO7d5qXhL8+FGN6FyGJRAFpUPDl1LMMS2CfT
-----END CERTIFICATE-----"""
    )

    (certs_dir / "server.key").write_text(
        """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC4ZJCP7lwwH7nF
8Z8YoA107t3mpeEvz4UY3oXIYlEAWlQ8OXUswxLYJ9O/s3E3D5yA2H4uGKGN+Rl1
-----END PRIVATE KEY-----"""
    )

    # Create auth directory and files
    auth_dir = output_path / "auth"
    auth_dir.mkdir(exist_ok=True)

    (auth_dir / "jwt_config.py").write_text(
        '''"""JWT authentication configuration."""

import os
from datetime import timedelta

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30

JWT_CONFIG = {
    "secret_key": JWT_SECRET_KEY,
    "algorithm": JWT_ALGORITHM,
    "access_token_expire_minutes": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    "refresh_token_expire_days": JWT_REFRESH_TOKEN_EXPIRE_DAYS,
}
'''
    )

    # Create middleware directory and files
    middleware_dir = output_path / "middleware"
    middleware_dir.mkdir(exist_ok=True)

    (middleware_dir / "security.py").write_text(
        '''"""Security middleware for the service."""

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional

security = HTTPBearer()

class SecurityMiddleware:
    """Security middleware for authentication and authorization."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    async def verify_token(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """Verify JWT token."""
        try:
            payload = jwt.decode(
                credentials.credentials,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    async def authenticate_request(self, request: Request) -> Optional[dict]:
        """Authenticate incoming request."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return None

            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except (ValueError, jwt.PyJWTError):
            return None
'''
    )


def _generate_config_yaml(
    name, with_database, with_monitoring, with_caching, with_auth=False, with_tls=False
):
    """Generate config.yaml content."""
    config = {"service": {"name": name, "version": "1.0.0", "port": 8080}}

    if with_database:
        config["database"] = {
            "url": "${DATABASE_URL:postgresql://localhost:5432/db}",
            "pool_size": 10,
        }

    if with_monitoring:
        config["monitoring"] = {"enabled": True, "metrics_port": 9090}

    if with_caching:
        config["cache"] = {
            "redis_url": "${REDIS_URL:redis://localhost:6379}",
            "ttl": 3600,
        }

    return yaml.dump(config, default_flow_style=False)


def _generate_requirements(
    service_type,
    with_database,
    with_monitoring,
    with_caching,
    with_auth=False,
    with_tls=False,
):
    """Generate requirements.txt content."""
    requirements = []

    if service_type == "fastapi":
        requirements.extend(
            [
                "fastapi>=0.104.0",
                "uvicorn[standard]>=0.24.0",
                "python-multipart>=0.0.6",
            ]
        )

    if with_database:
        requirements.extend(
            [
                "asyncpg>=0.29.0",
                "sqlalchemy>=2.0.0",
            ]
        )

    if with_monitoring:
        requirements.extend(
            [
                "prometheus-client>=0.19.0",
            ]
        )

    if with_caching:
        requirements.extend(
            [
                "redis>=4.5.0",
            ]
        )

    return "\n".join(requirements)


def _generate_dockerfile(service_type, name):
    """Generate Dockerfile content."""
    return """FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv for faster Python package management
RUN pip install uv

# Copy framework source (when building from framework root)
COPY ./src /app/framework/src
COPY ./pyproject.toml /app/framework/
COPY ./README.md /app/framework/

# Copy plugin/service source
COPY . /app/plugin

# Install framework as editable dependency
WORKDIR /app/framework
RUN uv pip install --system -e .

# Install service dependencies
WORKDIR /app/plugin
RUN uv pip install --system -r requirements.txt

# Set proper permissions
RUN mkdir -p logs && \\
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["python", "main.py"]
"""


def _create_database_files(output_path):
    """Create database-related files with valid PostgreSQL syntax."""

    migrations_dir = output_path / "migrations"
    migrations_dir.mkdir(exist_ok=True)

    # Use the SQL generator to create valid PostgreSQL syntax
    generator = SQLGenerator()

    # Create initial migration with proper table and index syntax
    users_table_sql = generator.create_table_with_indexes(
        table_name="users",
        columns=[
            "id SERIAL PRIMARY KEY",
            "name VARCHAR(255) NOT NULL",
            "email VARCHAR(255) UNIQUE NOT NULL",
            "created_at TIMESTAMP DEFAULT NOW()",
        ],
        indexes=[
            {"name": "idx_users_email", "columns": ["email"]},
            {"name": "idx_users_created_at", "columns": ["created_at"]},
        ],
    )

    items_table_sql = generator.create_table_with_indexes(
        table_name="items",
        columns=[
            "id SERIAL PRIMARY KEY",
            "name VARCHAR(255) NOT NULL",
            "description TEXT",
            "metadata JSONB",
            "created_at TIMESTAMP DEFAULT NOW()",
        ],
        indexes=[
            {"name": "idx_items_name", "columns": ["name"]},
            {"name": "idx_items_metadata", "columns": ["metadata"], "type": "gin"},
        ],
    )

    # Create configuration table with JSONB
    config_table_sql = generator.create_table_with_indexes(
        table_name="configuration",
        columns=[
            "id SERIAL PRIMARY KEY",
            "config_key VARCHAR(255) UNIQUE NOT NULL",
            "config_value JSONB NOT NULL",
            "config_type VARCHAR(50) NOT NULL DEFAULT 'setting'",
            "created_at TIMESTAMP DEFAULT NOW()",
            "updated_at TIMESTAMP DEFAULT NOW()",
        ],
        indexes=[
            {"name": "idx_config_key", "columns": ["config_key"]},
            {"name": "idx_config_type", "columns": ["config_type"]},
            {"name": "idx_config_value", "columns": ["config_value"], "type": "gin"},
        ],
    )

    # Generate sample data with properly formatted JSONB values
    sample_config_sql = generator.generate_insert_with_jsonb(
        table_name="configuration",
        columns=["config_key", "config_value", "config_type"],
        values=[
            ["'app.name'", generator.format_jsonb_value("MyApp"), "'setting'"],
            [
                "'feature_flags.new_ui'",
                generator.format_jsonb_value(True),
                "'feature_flag'",
            ],
            ["'database.pool_size'", generator.format_jsonb_value(10), "'setting'"],
            [
                "'notifications.config'",
                generator.format_jsonb_value(
                    {"enabled": True, "channels": ["email", "sms"]}
                ),
                "'setting'",
            ],
        ],
    )

    complete_sql = f"""-- Initial migration with valid PostgreSQL syntax
-- Generated by MMF Framework

{users_table_sql}

{items_table_sql}

{config_table_sql}

-- Sample configuration data
{sample_config_sql}
"""

    (migrations_dir / "001_initial.sql").write_text(complete_sql)


def _create_monitoring_files(output_path):
    """Create monitoring-related files."""
    monitoring_dir = output_path / "monitoring"
    monitoring_dir.mkdir(exist_ok=True)

    (monitoring_dir / "prometheus.yml").write_text(
        """
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'service'
    static_configs:
      - targets: ['localhost:8080']
"""
    )


# Add API documentation and contract testing commands
add_api_commands(cli)


if __name__ == "__main__":
    cli.main(standalone_mode=False)
