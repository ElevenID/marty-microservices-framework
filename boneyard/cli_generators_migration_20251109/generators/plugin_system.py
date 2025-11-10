"""
Template Plugin System for Marty Microservices Framework

This module provides a extensible plugin architecture for custom service templates
and code generators, allowing teams to create domain-specific templates while
maintaining integration with the Phase 1-3 infrastructure.
"""

import builtins
import importlib
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template


class TemplateType(Enum):
    """Types of templates supported by the plugin system."""

    SERVICE = "service"
    COMPONENT = "component"
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT = "deployment"
    TEST = "test"
    CONFIGURATION = "configuration"


class PluginPhase(Enum):
    """Plugin execution phases."""

    PRE_GENERATION = "pre_generation"
    GENERATION = "generation"
    POST_GENERATION = "post_generation"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"


@dataclass
class TemplateMetadata:
    """Metadata for a template plugin."""

    name: str
    version: str
    description: str
    author: str
    template_type: TemplateType
    supported_phases: builtins.list[PluginPhase]
    dependencies: builtins.list[str] = field(default_factory=list)
    tags: builtins.list[str] = field(default_factory=list)
    schema_version: str = "1.0.0"


@dataclass
class TemplateContext:
    """Context passed to template plugins."""

    service_name: str
    service_config: builtins.dict[str, Any]
    framework_config: builtins.dict[str, Any]
    output_directory: Path
    template_variables: builtins.dict[str, Any]
    infrastructure_components: builtins.set[str]
    custom_data: builtins.dict[str, Any] = field(default_factory=dict)


class TemplatePlugin(ABC):
    """Base class for template plugins."""

    def __init__(self, metadata: TemplateMetadata):
        """Initialize the plugin with metadata."""
        self.metadata = metadata
        self._initialized = False

    @abstractmethod
    def get_metadata(self) -> TemplateMetadata:
        """Return plugin metadata."""

    @abstractmethod
    def initialize(self, framework_root: Path) -> None:
        """Initialize the plugin with framework root directory."""

    @abstractmethod
    def validate_context(self, context: TemplateContext) -> bool:
        """Validate that the plugin can handle the given context."""

    @abstractmethod
    def generate_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Generate templates and return mapping of file paths to content."""

    def pre_generation_hook(self, context: TemplateContext) -> TemplateContext:
        """Hook called before template generation."""
        return context

    def post_generation_hook(
        self, context: TemplateContext, generated_files: builtins.list[Path]
    ) -> None:
        """Hook called after template generation."""

    def validate_generated_files(
        self, context: TemplateContext, generated_files: builtins.list[Path]
    ) -> bool:
        """Validate generated files."""
        return True


class ServiceTemplatePlugin(TemplatePlugin):
    """Specialized plugin for service templates."""

    @abstractmethod
    def get_service_dependencies(self, context: TemplateContext) -> builtins.list[str]:
        """Return list of infrastructure dependencies for this service type."""

    @abstractmethod
    def get_deployment_manifest_templates(
        self, context: TemplateContext
    ) -> builtins.dict[str, str]:
        """Return Kubernetes deployment manifests for this service type."""

    @abstractmethod
    def get_helm_chart_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Return Helm chart templates for this service type."""


class ComponentTemplatePlugin(TemplatePlugin):
    """Specialized plugin for infrastructure component templates."""

    @abstractmethod
    def get_integration_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Return integration templates for this component."""

    @abstractmethod
    def get_configuration_schema(self) -> builtins.dict[str, Any]:
        """Return JSON schema for component configuration."""


class PluginRegistry:
    """Registry for managing template plugins."""

    def __init__(self, framework_root: Path):
        """Initialize the plugin registry."""
        self.framework_root = framework_root
        self.plugins: builtins.dict[str, TemplatePlugin] = {}
        self.plugins_by_type: builtins.dict[TemplateType, builtins.list[TemplatePlugin]] = {
            template_type: [] for template_type in TemplateType
        }
        self.plugins_by_phase: builtins.dict[PluginPhase, builtins.list[TemplatePlugin]] = {
            phase: [] for phase in PluginPhase
        }

        # Plugin discovery paths
        self.plugin_paths = [
            framework_root / "plugins",
            framework_root / "src" / "plugins",
            Path.home() / ".marty" / "plugins",
        ]

    def discover_plugins(self) -> None:
        """Discover and load plugins from plugin paths."""
        for plugin_path in self.plugin_paths:
            if plugin_path.exists():
                self._load_plugins_from_directory(plugin_path)

    def register_plugin(self, plugin: TemplatePlugin) -> None:
        """Register a plugin instance."""
        metadata = plugin.get_metadata()

        # Validate plugin
        if not self._validate_plugin(plugin):
            raise ValueError(f"Plugin validation failed: {metadata.name}")

        # Initialize plugin
        plugin.initialize(self.framework_root)

        # Register in various indexes
        self.plugins[metadata.name] = plugin
        self.plugins_by_type[metadata.template_type].append(plugin)

        for phase in metadata.supported_phases:
            self.plugins_by_phase[phase].append(plugin)

    def get_plugin(self, name: str) -> TemplatePlugin | None:
        """Get plugin by name."""
        return self.plugins.get(name)

    def get_plugins_by_type(self, template_type: TemplateType) -> builtins.list[TemplatePlugin]:
        """Get all plugins of a specific type."""
        return self.plugins_by_type.get(template_type, [])

    def get_plugins_by_phase(self, phase: PluginPhase) -> builtins.list[TemplatePlugin]:
        """Get all plugins that support a specific phase."""
        return self.plugins_by_phase.get(phase, [])

    def list_plugins(self) -> builtins.list[TemplateMetadata]:
        """List all registered plugins."""
        return [plugin.get_metadata() for plugin in self.plugins.values()]

    def _load_plugins_from_directory(self, plugin_dir: Path) -> None:
        """Load plugins from a directory."""
        if not plugin_dir.exists():
            return

        # Add plugin directory to Python path
        sys.path.insert(0, str(plugin_dir))

        try:
            # Look for plugin.py files
            for plugin_file in plugin_dir.rglob("plugin.py"):
                self._load_plugin_file(plugin_file)

            # Look for __init__.py files with plugins
            for init_file in plugin_dir.rglob("__init__.py"):
                if init_file.parent != plugin_dir:  # Skip root __init__.py
                    self._load_plugin_file(init_file)

        finally:
            # Remove from Python path
            if str(plugin_dir) in sys.path:
                sys.path.remove(str(plugin_dir))

    def _load_plugin_file(self, plugin_file: Path) -> None:
        """Load plugins from a Python file."""
        try:
            # Import the module
            module_name = plugin_file.stem
            if module_name == "__init__":
                module_name = plugin_file.parent.name

            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find plugin classes
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, TemplatePlugin)
                        and obj != TemplatePlugin
                        and not inspect.isabstract(obj)
                    ):
                        # Instantiate and register plugin
                        try:
                            plugin_instance = obj()
                            self.register_plugin(plugin_instance)
                        except Exception as e:
                            print(f"Warning: Failed to load plugin {name}: {e}")

        except Exception as e:
            print(f"Warning: Failed to load plugin file {plugin_file}: {e}")

    def _validate_plugin(self, plugin: TemplatePlugin) -> bool:
        """Validate a plugin instance."""
        try:
            metadata = plugin.get_metadata()

            # Check required fields
            if not all([metadata.name, metadata.version, metadata.template_type]):
                return False

            # Check if plugin has required methods
            required_methods = [
                "get_metadata",
                "initialize",
                "validate_context",
                "generate_templates",
            ]
            for method_name in required_methods:
                if not hasattr(plugin, method_name):
                    return False

            return True

        except Exception:
            return False


class TemplateEngine:
    """Template engine with plugin support."""

    def __init__(self, framework_root: Path):
        """Initialize the template engine."""
        self.framework_root = framework_root
        self.plugin_registry = PluginRegistry(framework_root)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(framework_root / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

        # Discover plugins
        self.plugin_registry.discover_plugins()

    def generate_service(
        self, context: TemplateContext, plugin_names: builtins.list[str] | None = None
    ) -> builtins.dict[str, builtins.list[Path]]:
        """Generate service using plugins."""
        results = {}

        # Determine which plugins to use
        if plugin_names:
            plugins = [self.plugin_registry.get_plugin(name) for name in plugin_names]
            plugins = [p for p in plugins if p is not None]
        else:
            plugins = self.plugin_registry.get_plugins_by_type(TemplateType.SERVICE)

        # Pre-generation phase
        for plugin in self.plugin_registry.get_plugins_by_phase(PluginPhase.PRE_GENERATION):
            if plugin in plugins:
                context = plugin.pre_generation_hook(context)

        # Generation phase
        generated_files = []
        for plugin in plugins:
            if plugin.validate_context(context):
                try:
                    templates = plugin.generate_templates(context)
                    files = self._write_templates(templates, context.output_directory)
                    generated_files.extend(files)
                    results[plugin.get_metadata().name] = files

                except Exception as e:
                    print(f"Warning: Plugin {plugin.get_metadata().name} failed: {e}")

        # Post-generation phase
        for plugin in self.plugin_registry.get_plugins_by_phase(PluginPhase.POST_GENERATION):
            if plugin in plugins:
                plugin.post_generation_hook(context, generated_files)

        # Validation phase
        for plugin in self.plugin_registry.get_plugins_by_phase(PluginPhase.VALIDATION):
            if plugin in plugins:
                if not plugin.validate_generated_files(context, generated_files):
                    print(f"Warning: Validation failed for plugin {plugin.get_metadata().name}")

        return results

    def _write_templates(
        self, templates: builtins.dict[str, str], output_dir: Path
    ) -> builtins.list[Path]:
        """Write templates to disk and return list of created files."""
        created_files = []

        for file_path, content in templates.items():
            full_path = output_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            created_files.append(full_path)

        return created_files


# Built-in plugins


class FastAPIServicePlugin(ServiceTemplatePlugin):
    """Built-in FastAPI service template plugin."""

    def get_metadata(self) -> TemplateMetadata:
        """Return plugin metadata."""
        return TemplateMetadata(
            name="fastapi-service",
            version="1.0.0",
            description="Enterprise FastAPI service with Phase 1-3 integration",
            author="Marty Framework Team",
            template_type=TemplateType.SERVICE,
            supported_phases=[PluginPhase.GENERATION, PluginPhase.VALIDATION],
            dependencies=["framework-config", "framework-observability"],
            tags=["rest", "api", "fastapi", "enterprise"],
        )

    def initialize(self, framework_root: Path) -> None:
        """Initialize the plugin."""
        self.framework_root = framework_root
        self.templates_dir = framework_root / "service" / "fastapi_service"
        self._initialized = True

    def validate_context(self, context: TemplateContext) -> bool:
        """Validate context for FastAPI service generation."""
        return context.template_variables.get("has_rest", False)

    def generate_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Generate FastAPI service templates."""
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")

        templates = {}

        # Load and render each template
        for template_file in self.templates_dir.glob("*.j2"):
            with open(template_file, encoding="utf-8") as f:
                template_content = f.read()

            template = Template(template_content)
            rendered = template.render(**context.template_variables)

            # Determine output path
            output_path = template_file.name.replace(".j2", "")
            if output_path == "service.py":
                output_path = f"app/services/{context.service_name}_service.py"
            elif output_path == "config.py":
                output_path = "app/core/config.py"

            templates[output_path] = rendered

        return templates

    def get_service_dependencies(self, context: TemplateContext) -> builtins.list[str]:
        """Return service dependencies."""
        return [
            "fastapi",
            "uvicorn",
            "pydantic",
            "framework-config",
            "framework-observability",
        ]

    def get_deployment_manifest_templates(
        self, context: TemplateContext
    ) -> builtins.dict[str, str]:
        """Return Kubernetes manifests."""
        return {
            "deployment.yaml": f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {context.service_name}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: {context.service_name}
  template:
    metadata:
      labels:
        app: {context.service_name}
    spec:
      containers:
      - name: {context.service_name}
        image: {context.service_name}:latest
        ports:
        - containerPort: {context.template_variables.get("http_port", 8000)}
"""
        }

    def get_helm_chart_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Return Helm chart templates."""
        return {
            "Chart.yaml": f"""apiVersion: v2
name: {context.service_name}
description: FastAPI service generated by Marty Framework
version: 1.0.0
appVersion: 1.0.0
""",
            "values.yaml": f"""replicaCount: 3
image:
  repository: {context.service_name}
  tag: latest
service:
  type: ClusterIP
  port: {context.template_variables.get("http_port", 8000)}
""",
        }


class GRPCServicePlugin(ServiceTemplatePlugin):
    """Built-in gRPC service template plugin."""

    def get_metadata(self) -> TemplateMetadata:
        """Return plugin metadata."""
        return TemplateMetadata(
            name="grpc-service",
            version="1.0.0",
            description="Enterprise gRPC service with Phase 1-3 integration",
            author="Marty Framework Team",
            template_type=TemplateType.SERVICE,
            supported_phases=[PluginPhase.GENERATION, PluginPhase.VALIDATION],
            dependencies=[
                "framework-grpc",
                "framework-config",
                "framework-observability",
            ],
            tags=["grpc", "rpc", "enterprise", "high-performance"],
        )

    def initialize(self, framework_root: Path) -> None:
        """Initialize the plugin."""
        self.framework_root = framework_root
        self.templates_dir = framework_root / "service" / "grpc_service"
        self._initialized = True

    def validate_context(self, context: TemplateContext) -> bool:
        """Validate context for gRPC service generation."""
        return context.template_variables.get("has_grpc", False)

    def generate_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Generate gRPC service templates."""
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")

        templates = {}

        # Load and render each template
        for template_file in self.templates_dir.glob("*.j2"):
            with open(template_file, encoding="utf-8") as f:
                template_content = f.read()

            template = Template(template_content)
            rendered = template.render(**context.template_variables)

            # Determine output path
            output_path = template_file.name.replace(".j2", "")
            templates[output_path] = rendered

        return templates

    def get_service_dependencies(self, context: TemplateContext) -> builtins.list[str]:
        """Return service dependencies."""
        return [
            "grpcio",
            "grpcio-tools",
            "framework-grpc",
            "framework-config",
            "framework-observability",
        ]

    def get_deployment_manifest_templates(
        self, context: TemplateContext
    ) -> builtins.dict[str, str]:
        """Return Kubernetes manifests."""
        return {
            "deployment.yaml": f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {context.service_name}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: {context.service_name}
  template:
    metadata:
      labels:
        app: {context.service_name}
    spec:
      containers:
      - name: {context.service_name}
        image: {context.service_name}:latest
        ports:
        - containerPort: {context.template_variables.get("grpc_port", 50051)}
"""
        }

    def get_helm_chart_templates(self, context: TemplateContext) -> builtins.dict[str, str]:
        """Return Helm chart templates."""
        return {
            "Chart.yaml": f"""apiVersion: v2
name: {context.service_name}
description: gRPC service generated by Marty Framework
version: 1.0.0
appVersion: 1.0.0
""",
            "values.yaml": f"""replicaCount: 3
image:
  repository: {context.service_name}
  tag: latest
service:
  type: ClusterIP
  port: {context.template_variables.get("grpc_port", 50051)}
""",
        }


# Plugin loader utility functions


def register_builtin_plugins(registry: PluginRegistry) -> None:
    """Register built-in plugins."""
    builtin_plugins = [
        FastAPIServicePlugin(),
        GRPCServicePlugin(),
    ]

    for plugin in builtin_plugins:
        registry.register_plugin(plugin)


def create_plugin_template(plugin_name: str, plugin_type: TemplateType, output_dir: Path) -> None:
    """Create a template for a new plugin."""
    plugin_dir = output_dir / plugin_name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Create plugin.py file
    plugin_template = f'''"""
{plugin_name.title().replace("_", " ")} Plugin for Marty Framework

This plugin provides custom template generation for {plugin_type.value} components.
"""

from pathlib import Path
from typing import Any

from marty_msf.framework.generators.plugin_system import (
    TemplatePlugin, TemplateMetadata, TemplateContext, TemplateType, PluginPhase
)


class {plugin_name.title().replace("_", "")}Plugin(TemplatePlugin):
    """Custom {plugin_name} plugin."""

    def get_metadata(self) -> TemplateMetadata:
        """Return plugin metadata."""
        return TemplateMetadata(
            name="{plugin_name}",
            version="1.0.0",
            description="Custom {plugin_name} template plugin",
            author="Your Name",
            template_type=TemplateType.{plugin_type.name},
            supported_phases=[PluginPhase.GENERATION],
            dependencies=[],
            tags=["custom", "{plugin_type.value}"]
        )

    def initialize(self, framework_root: Path) -> None:
        """Initialize the plugin."""
        self.framework_root = framework_root
        self.templates_dir = Path(__file__).parent / "templates"
        self._initialized = True

    def validate_context(self, context: TemplateContext) -> bool:
        """Validate context for template generation."""
        # Add your validation logic here
        return True

    def generate_templates(self, context: TemplateContext) -> Dict[str, str]:
        """Generate templates."""
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")

        templates = {{}}

        # Add your template generation logic here
        templates["example.py"] = f"""# Generated by {{plugin_name}} plugin
# Service: {{context.service_name}}

def main():
    print("Hello from {{plugin_name}} plugin!")

if __name__ == "__main__":
    main()
"""

        return templates
'''

    (plugin_dir / "plugin.py").write_text(plugin_template, encoding="utf-8")

    # Create templates directory
    templates_dir = plugin_dir / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Create example template
    example_template = """# {{ service_name }} - Generated by {{ plugin_name }}

def main():
    \"\"\"Entry point for {{ service_name }} service.\"\"\"
    print("Service {{ service_name }} starting...")

if __name__ == "__main__":
    main()
"""

    (templates_dir / "example.py.j2").write_text(example_template, encoding="utf-8")

    # Create README
    readme = f"""# {plugin_name.title().replace("_", " ")} Plugin

This plugin provides custom template generation for {plugin_type.value} components.

## Usage

1. Place your Jinja2 templates in the `templates/` directory
2. Implement the `generate_templates()` method in `plugin.py`
3. Register the plugin with the Marty Framework

## Template Variables

Your templates have access to all standard Marty Framework variables plus any custom variables you define.

## Development

To test your plugin:

```bash
python -m src.framework.generators.advanced_cli --interactive
```

Select your custom plugin when prompted.
"""

    (plugin_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Plugin template created at: {plugin_dir}")
    print(f"Edit {plugin_dir}/plugin.py to customize your plugin")
