#!/usr/bin/env python3
"""
Advanced Service Generation CLI for Marty Microservices Framework

This enhanced CLI provides intelligent service generation with:
- Interactive prompts and configuration wizards
- Dependency analysis and automatic integration
- Phase 1-3 infrastructure integration
- Template validation and customization
- Project structure optimization
- Real-time dependency resolution
"""

import builtins
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import click
import questionary
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

# Framework imports
sys.path.append(str(Path(__file__).resolve().parents[3]))


class ServiceType(Enum):
    """Available service types for generation."""

    GRPC = "grpc_service"
    FASTAPI = "fastapi_service"
    HYBRID = "hybrid_service"
    AUTH = "auth_service"
    CACHING = "caching_service"
    DATABASE = "database_service"
    MESSAGE_QUEUE = "message_queue_service"
    CUSTOM = "custom"


class InfrastructureComponent(Enum):
    """Phase 1-3 infrastructure components."""

    # Phase 1 - Core
    CONFIG_MANAGEMENT = "config_management"
    GRPC_FACTORY = "grpc_factory"
    OBSERVABILITY = "observability"
    HEALTH_MONITORING = "health_monitoring"

    # Phase 2 - Enterprise
    ADVANCED_CONFIG = "advanced_config"
    CACHE_LAYER = "cache_layer"
    MESSAGE_QUEUE = "message_queue"
    EVENT_STREAMING = "event_streaming"
    API_GATEWAY = "api_gateway"

    # Phase 3 - Deployment
    KUBERNETES = "kubernetes"
    HELM_CHARTS = "helm_charts"
    CI_CD_PIPELINE = "ci_cd_pipeline"
    MONITORING_STACK = "monitoring_stack"
    SERVICE_MESH = "service_mesh"


@dataclass
class ServiceDependency:
    """Represents a service dependency."""

    name: str
    version: str
    component: InfrastructureComponent
    required: bool = True
    description: str = ""
    config_key: str | None = None


@dataclass
class ServiceConfiguration:
    """Complete service configuration."""

    name: str
    type: ServiceType
    description: str
    version: str = "1.0.0"
    author: str = ""
    email: str = ""

    # Infrastructure integration
    dependencies: builtins.list[ServiceDependency] = field(default_factory=list)
    infrastructure_components: builtins.set[InfrastructureComponent] = field(default_factory=set)

    # Service-specific settings
    grpc_port: int = 50051
    http_port: int = 8000
    metrics_port: int = 9090

    # Database settings
    use_database: bool = False
    database_type: str = "postgresql"

    # Cache settings
    use_cache: bool = False
    cache_backend: str = "redis"

    # Message queue settings
    use_messaging: bool = False
    messaging_backend: str = "rabbitmq"

    # Event streaming settings
    use_events: bool = False
    event_backend: str = "kafka"

    # API Gateway integration
    use_api_gateway: bool = False
    gateway_routes: builtins.list[str] = field(default_factory=list)

    # Deployment settings
    use_kubernetes: bool = True
    use_helm: bool = True
    use_service_mesh: bool = True

    # Custom template variables
    custom_vars: builtins.dict[str, Any] = field(default_factory=dict)


class InfrastructureDependencyResolver:
    """Resolves and manages infrastructure dependencies."""

    DEPENDENCY_MAP = {
        # Phase 1 dependencies
        InfrastructureComponent.CONFIG_MANAGEMENT: ServiceDependency(
            name="framework-config",
            version="1.0.0",
            component=InfrastructureComponent.CONFIG_MANAGEMENT,
            description="Base configuration management",
            config_key="config.base",
        ),
        InfrastructureComponent.GRPC_FACTORY: ServiceDependency(
            name="framework-grpc",
            version="1.0.0",
            component=InfrastructureComponent.GRPC_FACTORY,
            description="gRPC service factory with DI",
            config_key="grpc.factory",
        ),
        InfrastructureComponent.OBSERVABILITY: ServiceDependency(
            name="framework-observability",
            version="1.0.0",
            component=InfrastructureComponent.OBSERVABILITY,
            description="OpenTelemetry tracing and metrics",
            config_key="observability.telemetry",
        ),
        # Phase 2 dependencies
        InfrastructureComponent.ADVANCED_CONFIG: ServiceDependency(
            name="framework-config-advanced",
            version="2.0.0",
            component=InfrastructureComponent.ADVANCED_CONFIG,
            description="Advanced config with secrets management",
            config_key="config.advanced",
        ),
        InfrastructureComponent.CACHE_LAYER: ServiceDependency(
            name="framework-cache",
            version="2.0.0",
            component=InfrastructureComponent.CACHE_LAYER,
            description="Multi-backend caching (Redis, Memcached)",
            config_key="cache.layer",
        ),
        InfrastructureComponent.MESSAGE_QUEUE: ServiceDependency(
            name="framework-messaging",
            version="2.0.0",
            component=InfrastructureComponent.MESSAGE_QUEUE,
            description="Message queue (RabbitMQ, AWS SQS)",
            config_key="messaging.queue",
        ),
        InfrastructureComponent.EVENT_STREAMING: ServiceDependency(
            name="framework-events",
            version="2.0.0",
            component=InfrastructureComponent.EVENT_STREAMING,
            description="Event streaming (Kafka, AWS Kinesis)",
            config_key="events.streaming",
        ),
        InfrastructureComponent.API_GATEWAY: ServiceDependency(
            name="framework-gateway",
            version="2.0.0",
            component=InfrastructureComponent.API_GATEWAY,
            description="API Gateway integration",
            config_key="gateway.api",
        ),
        # Phase 3 dependencies
        InfrastructureComponent.KUBERNETES: ServiceDependency(
            name="framework-k8s",
            version="3.0.0",
            component=InfrastructureComponent.KUBERNETES,
            description="Kubernetes deployment manifests",
            config_key="kubernetes.deployment",
        ),
        InfrastructureComponent.HELM_CHARTS: ServiceDependency(
            name="framework-helm",
            version="3.0.0",
            component=InfrastructureComponent.HELM_CHARTS,
            description="Helm chart templates",
            config_key="helm.charts",
        ),
        InfrastructureComponent.SERVICE_MESH: ServiceDependency(
            name="framework-istio",
            version="3.0.0",
            component=InfrastructureComponent.SERVICE_MESH,
            description="Istio service mesh integration",
            config_key="service_mesh.istio",
        ),
    }

    # Component dependencies (what requires what)
    COMPONENT_DEPENDENCIES = {
        InfrastructureComponent.GRPC_FACTORY: [InfrastructureComponent.CONFIG_MANAGEMENT],
        InfrastructureComponent.OBSERVABILITY: [InfrastructureComponent.CONFIG_MANAGEMENT],
        InfrastructureComponent.ADVANCED_CONFIG: [InfrastructureComponent.CONFIG_MANAGEMENT],
        InfrastructureComponent.CACHE_LAYER: [
            InfrastructureComponent.CONFIG_MANAGEMENT,
            InfrastructureComponent.ADVANCED_CONFIG,
        ],
        InfrastructureComponent.MESSAGE_QUEUE: [
            InfrastructureComponent.CONFIG_MANAGEMENT,
            InfrastructureComponent.ADVANCED_CONFIG,
        ],
        InfrastructureComponent.EVENT_STREAMING: [
            InfrastructureComponent.CONFIG_MANAGEMENT,
            InfrastructureComponent.ADVANCED_CONFIG,
            InfrastructureComponent.MESSAGE_QUEUE,
        ],
        InfrastructureComponent.API_GATEWAY: [
            InfrastructureComponent.CONFIG_MANAGEMENT,
            InfrastructureComponent.GRPC_FACTORY,
            InfrastructureComponent.OBSERVABILITY,
        ],
        InfrastructureComponent.HELM_CHARTS: [InfrastructureComponent.KUBERNETES],
        InfrastructureComponent.SERVICE_MESH: [
            InfrastructureComponent.KUBERNETES,
            InfrastructureComponent.OBSERVABILITY,
        ],
    }

    def resolve_dependencies(
        self, components: builtins.set[InfrastructureComponent]
    ) -> builtins.list[ServiceDependency]:
        """Resolve all dependencies for the given components."""
        resolved = set()
        dependencies = []

        def add_component_dependencies(component: InfrastructureComponent):
            if component in resolved:
                return

            # Add dependencies first
            if component in self.COMPONENT_DEPENDENCIES:
                for dep in self.COMPONENT_DEPENDENCIES[component]:
                    add_component_dependencies(dep)

            # Add the component itself
            if component in self.DEPENDENCY_MAP:
                dependencies.append(self.DEPENDENCY_MAP[component])
                resolved.add(component)

        for component in components:
            add_component_dependencies(component)

        return dependencies


class AdvancedServiceGenerator:
    """Advanced service generator with intelligent configuration."""

    def __init__(self, framework_root: Path):
        """Initialize the generator."""
        self.framework_root = framework_root
        self.templates_dir = framework_root / "service"
        self.output_dir = framework_root / "generated_services"
        self.console = Console()
        self.dependency_resolver = InfrastructureDependencyResolver()

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

        # Create output directory
        self.output_dir.mkdir(exist_ok=True)

    def run_interactive_wizard(self) -> ServiceConfiguration:
        """Run interactive configuration wizard."""
        self.console.print(
            Panel.fit(
                "[bold cyan]🚀 Marty Microservices Framework - Advanced Service Generator[/bold cyan]\n"
                "[dim]Phase 4: Service Generation and Templates[/dim]",
                border_style="cyan",
            )
        )

        # Basic service information
        service_name = questionary.text(
            "🏷️  Service name (kebab-case):",
            validate=lambda x: len(x) > 0 and x.replace("-", "").replace("_", "").isalnum(),
        ).ask()

        service_type = questionary.select(
            "🔧 Service type:",
            choices=[
                questionary.Choice("gRPC Service", ServiceType.GRPC),
                questionary.Choice("FastAPI REST Service", ServiceType.FASTAPI),
                questionary.Choice("Hybrid (gRPC + REST)", ServiceType.HYBRID),
                questionary.Choice("Authentication Service", ServiceType.AUTH),
                questionary.Choice("Caching Service", ServiceType.CACHING),
                questionary.Choice("Database Service", ServiceType.DATABASE),
                questionary.Choice("Message Queue Service", ServiceType.MESSAGE_QUEUE),
            ],
        ).ask()

        description = questionary.text(
            "📝 Service description:", default=f"Enterprise {service_name} microservice"
        ).ask()

        author = questionary.text("👤 Author name:", default="Developer").ask()
        email = questionary.text("📧 Author email:", default="dev@company.com").ask()

        # Infrastructure components selection
        self.console.print("\n[bold]🏗️  Infrastructure Components Selection[/bold]")

        components = set()

        # Always include core components
        components.update(
            [
                InfrastructureComponent.CONFIG_MANAGEMENT,
                InfrastructureComponent.OBSERVABILITY,
                InfrastructureComponent.HEALTH_MONITORING,
            ]
        )

        # Service type specific components
        if service_type in [ServiceType.GRPC, ServiceType.HYBRID]:
            components.add(InfrastructureComponent.GRPC_FACTORY)

        # Optional Phase 2 components
        phase2_choices = questionary.checkbox(
            "Select Phase 2 Enterprise Components:",
            choices=[
                questionary.Choice(
                    "🔧 Advanced Configuration & Secrets",
                    InfrastructureComponent.ADVANCED_CONFIG,
                ),
                questionary.Choice(
                    "⚡ Cache Layer (Redis/Memcached)",
                    InfrastructureComponent.CACHE_LAYER,
                ),
                questionary.Choice(
                    "📨 Message Queue (RabbitMQ)", InfrastructureComponent.MESSAGE_QUEUE
                ),
                questionary.Choice(
                    "🌊 Event Streaming (Kafka)", InfrastructureComponent.EVENT_STREAMING
                ),
                questionary.Choice(
                    "🚪 API Gateway Integration", InfrastructureComponent.API_GATEWAY
                ),
            ],
        ).ask()
        components.update(phase2_choices)

        # Optional Phase 3 components
        phase3_choices = questionary.checkbox(
            "Select Phase 3 Deployment Components:",
            choices=[
                questionary.Choice("☸️  Kubernetes Manifests", InfrastructureComponent.KUBERNETES),
                questionary.Choice("⛵ Helm Charts", InfrastructureComponent.HELM_CHARTS),
                questionary.Choice("🕸️  Service Mesh (Istio)", InfrastructureComponent.SERVICE_MESH),
            ],
            default=[
                InfrastructureComponent.KUBERNETES,
                InfrastructureComponent.HELM_CHARTS,
            ],
        ).ask()
        components.update(phase3_choices)

        # Service-specific configuration
        config = ServiceConfiguration(
            name=service_name,
            type=service_type,
            description=description,
            author=author,
            email=email,
            infrastructure_components=components,
        )

        # Configure service-specific settings
        if InfrastructureComponent.CACHE_LAYER in components:
            config.use_cache = True
            config.cache_backend = questionary.select(
                "Cache backend:", choices=["redis", "memcached", "inmemory"]
            ).ask()

        if InfrastructureComponent.MESSAGE_QUEUE in components:
            config.use_messaging = True
            config.messaging_backend = questionary.select(
                "Message queue backend:",
                choices=["rabbitmq", "aws_sqs", "azure_servicebus"],
            ).ask()

        if InfrastructureComponent.EVENT_STREAMING in components:
            config.use_events = True
            config.event_backend = questionary.select(
                "Event streaming backend:",
                choices=["kafka", "aws_kinesis", "azure_eventhubs"],
            ).ask()

        # Database configuration
        if service_type in [ServiceType.DATABASE, ServiceType.AUTH]:
            config.use_database = True
            config.database_type = questionary.select(
                "Database type:", choices=["postgresql", "mysql", "mongodb", "sqlite"]
            ).ask()
        else:
            config.use_database = questionary.confirm(
                "Include database integration?", default=False
            ).ask()
            if config.use_database:
                config.database_type = questionary.select(
                    "Database type:", choices=["postgresql", "mysql", "mongodb"]
                ).ask()

        # Port configuration
        if service_type in [ServiceType.GRPC, ServiceType.HYBRID]:
            config.grpc_port = questionary.text(
                "gRPC port:",
                default="50051",
                validate=lambda x: x.isdigit() and 1024 <= int(x) <= 65535,
            ).ask()
            config.grpc_port = int(config.grpc_port)

        if service_type in [ServiceType.FASTAPI, ServiceType.HYBRID]:
            config.http_port = questionary.text(
                "HTTP port:",
                default="8000",
                validate=lambda x: x.isdigit() and 1024 <= int(x) <= 65535,
            ).ask()
            config.http_port = int(config.http_port)

        return config

    def analyze_dependencies(self, config: ServiceConfiguration) -> None:
        """Analyze and resolve dependencies."""
        self.console.print("\n[bold]🔍 Analyzing Dependencies...[/bold]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Resolving infrastructure dependencies...", total=None)

            # Resolve dependencies
            config.dependencies = self.dependency_resolver.resolve_dependencies(
                config.infrastructure_components
            )

            progress.update(task, description="Dependencies resolved!")

        # Display dependency tree
        tree = Tree("📦 Service Dependencies")

        phase1_tree = tree.add("Phase 1 - Core Infrastructure")
        phase2_tree = tree.add("Phase 2 - Enterprise Components")
        phase3_tree = tree.add("Phase 3 - Deployment & Operations")

        for dep in config.dependencies:
            if dep.component.value.startswith(
                ("config_management", "grpc_factory", "observability", "health")
            ):
                phase1_tree.add(f"✅ {dep.name} v{dep.version} - {dep.description}")
            elif dep.component.value.startswith(
                ("advanced_config", "cache", "message", "event", "api")
            ):
                phase2_tree.add(f"✅ {dep.name} v{dep.version} - {dep.description}")
            else:
                phase3_tree.add(f"✅ {dep.name} v{dep.version} - {dep.description}")

        self.console.print(tree)

    def generate_service(self, config: ServiceConfiguration) -> Path:
        """Generate the service with all configurations."""
        self.console.print(f"\n[bold]🏗️  Generating {config.name} service...[/bold]")

        # Prepare template variables
        template_vars = self._prepare_template_vars(config)

        # Create service directory
        service_dir = self.output_dir / config.name.replace("-", "_")
        service_dir.mkdir(parents=True, exist_ok=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            # Generate core service files
            task1 = progress.add_task("Generating core service files...", total=None)
            self._generate_core_files(config, template_vars, service_dir)
            progress.update(task1, description="✅ Core files generated")

            # Generate infrastructure integration
            task2 = progress.add_task("Generating infrastructure integration...", total=None)
            self._generate_infrastructure_integration(config, template_vars, service_dir)
            progress.update(task2, description="✅ Infrastructure integration generated")

            # Generate deployment manifests
            if InfrastructureComponent.KUBERNETES in config.infrastructure_components:
                task3 = progress.add_task("Generating Kubernetes manifests...", total=None)
                self._generate_k8s_manifests(config, template_vars, service_dir)
                progress.update(task3, description="✅ Kubernetes manifests generated")

            # Generate Helm charts
            if InfrastructureComponent.HELM_CHARTS in config.infrastructure_components:
                task4 = progress.add_task("Generating Helm charts...", total=None)
                self._generate_helm_charts(config, template_vars, service_dir)
                progress.update(task4, description="✅ Helm charts generated")

            # Generate CI/CD pipeline
            task5 = progress.add_task("Generating CI/CD pipeline...", total=None)
            self._generate_cicd_pipeline(config, template_vars, service_dir)
            progress.update(task5, description="✅ CI/CD pipeline generated")

        return service_dir

    def _prepare_template_vars(self, config: ServiceConfiguration) -> builtins.dict[str, Any]:
        """Prepare template variables from configuration."""
        # Convert service name to various formats
        service_package = config.name.replace("-", "_")
        service_class = "".join(word.capitalize() for word in config.name.split("-"))

        vars_dict = {
            # Basic service info
            "service_name": config.name,
            "service_package": service_package,
            "service_class": service_class,
            "service_description": config.description,
            "service_version": config.version,
            "author_name": config.author,
            "author_email": config.email,
            # Ports
            "grpc_port": config.grpc_port,
            "http_port": config.http_port,
            "metrics_port": config.metrics_port,
            # Infrastructure flags
            "use_database": config.use_database,
            "database_type": config.database_type,
            "use_cache": config.use_cache,
            "cache_backend": config.cache_backend,
            "use_messaging": config.use_messaging,
            "messaging_backend": config.messaging_backend,
            "use_events": config.use_events,
            "event_backend": config.event_backend,
            "use_api_gateway": config.use_api_gateway,
            "use_kubernetes": config.use_kubernetes,
            "use_helm": config.use_helm,
            "use_service_mesh": config.use_service_mesh,
            # Component flags
            "has_grpc": config.type in [ServiceType.GRPC, ServiceType.HYBRID],
            "has_rest": config.type in [ServiceType.FASTAPI, ServiceType.HYBRID],
            "has_auth": config.type == ServiceType.AUTH,
            # Infrastructure component flags
            "use_advanced_config": InfrastructureComponent.ADVANCED_CONFIG
            in config.infrastructure_components,
            "use_observability": InfrastructureComponent.OBSERVABILITY
            in config.infrastructure_components,
            "use_grpc_factory": InfrastructureComponent.GRPC_FACTORY
            in config.infrastructure_components,
            # Dependencies
            "dependencies": [
                {
                    "name": dep.name,
                    "version": dep.version,
                    "component": dep.component.value,
                    "config_key": dep.config_key,
                    "description": dep.description,
                }
                for dep in config.dependencies
            ],
            # Custom variables
            **config.custom_vars,
        }

        return vars_dict

    def _generate_core_files(
        self,
        config: ServiceConfiguration,
        template_vars: builtins.dict[str, Any],
        service_dir: Path,
    ) -> None:
        """Generate core service files."""
        template_dir = self.templates_dir / config.type.value

        if not template_dir.exists():
            raise ValueError(f"Template directory not found: {template_dir}")

        # Create directory structure
        (service_dir / "app").mkdir(exist_ok=True)
        (service_dir / "app" / "api").mkdir(exist_ok=True)
        (service_dir / "app" / "core").mkdir(exist_ok=True)
        (service_dir / "app" / "services").mkdir(exist_ok=True)
        (service_dir / "tests").mkdir(exist_ok=True)

        # Generate files from templates
        for template_file in template_dir.glob("*.j2"):
            template = self.env.get_template(f"{config.type.value}/{template_file.name}")
            rendered_content = template.render(**template_vars)

            # Determine output file
            output_file = service_dir / template_file.name.replace(".j2", "")
            if template_file.name == "service.py.j2":
                output_file = (
                    service_dir
                    / "app"
                    / "services"
                    / f"{template_vars['service_package']}_service.py"
                )
            elif template_file.name == "config.py.j2":
                output_file = service_dir / "app" / "core" / "config.py"

            output_file.write_text(rendered_content, encoding="utf-8")

    def _generate_infrastructure_integration(
        self,
        config: ServiceConfiguration,
        template_vars: builtins.dict[str, Any],
        service_dir: Path,
    ) -> None:
        """Generate infrastructure integration files."""
        # Create infrastructure directory
        infra_dir = service_dir / "infrastructure"
        infra_dir.mkdir(exist_ok=True)

        # Generate dependency injection configuration
        di_config = {
            "dependencies": template_vars["dependencies"],
            "components": [comp.value for comp in config.infrastructure_components],
        }

        (infra_dir / "dependencies.json").write_text(
            json.dumps(di_config, indent=2), encoding="utf-8"
        )

    def _generate_k8s_manifests(
        self,
        config: ServiceConfiguration,
        template_vars: builtins.dict[str, Any],
        service_dir: Path,
    ) -> None:
        """Generate Kubernetes manifests."""
        k8s_dir = service_dir / "k8s"
        k8s_dir.mkdir(exist_ok=True)

        # Use Phase 3 Kubernetes templates
        self.framework_root / "k8s" / "templates"

        # Generate namespace
        namespace_template = """apiVersion: v1
kind: Namespace
metadata:
  name: {{ service_package }}-dev
  labels:
    app.kubernetes.io/name: {{ service_package }}
    marty.framework/service: "{{ service_name }}"
    marty.framework/phase: "phase4"
"""

        template = self.env.from_string(namespace_template)
        rendered = template.render(**template_vars)
        (k8s_dir / "namespace.yaml").write_text(rendered, encoding="utf-8")

    def _generate_helm_charts(
        self,
        config: ServiceConfiguration,
        template_vars: builtins.dict[str, Any],
        service_dir: Path,
    ) -> None:
        """Generate Helm charts."""
        helm_dir = service_dir / "helm"
        helm_dir.mkdir(exist_ok=True)

        # Generate Chart.yaml
        chart_yaml = f"""apiVersion: v2
name: {template_vars["service_package"]}
description: {template_vars["service_description"]}
version: {template_vars["service_version"]}
appVersion: {template_vars["service_version"]}
type: application
dependencies:
  - name: marty-framework
    version: "3.0.0"
    repository: "oci://registry.marty.framework/helm"
"""
        (helm_dir / "Chart.yaml").write_text(chart_yaml, encoding="utf-8")

    def _generate_cicd_pipeline(
        self,
        config: ServiceConfiguration,
        template_vars: builtins.dict[str, Any],
        service_dir: Path,
    ) -> None:
        """Generate CI/CD pipeline configuration."""
        github_dir = service_dir / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)

        # Generate GitHub Actions workflow
        workflow_yaml = f"""name: {template_vars["service_name"]} CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install uv
        uv sync
    - name: Run tests
      run: uv run pytest
    - name: Run linting
      run: |
        uv run ruff check .
        uv run mypy .
"""
        (github_dir / f"{template_vars['service_package']}-ci.yml").write_text(
            workflow_yaml, encoding="utf-8"
        )

    def display_generation_summary(self, config: ServiceConfiguration, service_dir: Path) -> None:
        """Display generation summary."""
        self.console.print(
            f"\n[bold green]🎉 Service '{config.name}' generated successfully![/bold green]"
        )

        # Summary table
        table = Table(title="📊 Generation Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Location", style="blue")

        table.add_row("Core Service", "✅ Generated", str(service_dir / "app"))
        table.add_row("Configuration", "✅ Generated", str(service_dir / "app" / "core"))
        table.add_row("Tests", "✅ Generated", str(service_dir / "tests"))

        if InfrastructureComponent.KUBERNETES in config.infrastructure_components:
            table.add_row("Kubernetes", "✅ Generated", str(service_dir / "k8s"))

        if InfrastructureComponent.HELM_CHARTS in config.infrastructure_components:
            table.add_row("Helm Charts", "✅ Generated", str(service_dir / "helm"))

        table.add_row("CI/CD Pipeline", "✅ Generated", str(service_dir / ".github"))
        table.add_row("Dependencies", "✅ Configured", str(service_dir / "infrastructure"))

        self.console.print(table)

        # Next steps
        self.console.print(
            Panel(
                f"[bold]🚀 Next Steps:[/bold]\n\n"
                f"1. Navigate to service directory:\n"
                f"   [cyan]cd {service_dir}[/cyan]\n\n"
                f"2. Install dependencies:\n"
                f"   [cyan]uv sync[/cyan]\n\n"
                f"3. Run the service:\n"
                f"   [cyan]uv run python main.py[/cyan]\n\n"
                f"4. Deploy to Kubernetes:\n"
                f"   [cyan]kubectl apply -f k8s/[/cyan]\n\n"
                f"📚 Documentation: {service_dir}/README.md",
                title="🎯 Quick Start Guide",
                border_style="green",
            )
        )


@click.command()
@click.option("--interactive", "-i", is_flag=True, help="Run interactive wizard")
@click.option("--config", "-c", type=click.Path(exists=True), help="Configuration file")
@click.option(
    "--service-type",
    "-t",
    type=click.Choice([e.value for e in ServiceType]),
    help="Service type",
)
@click.option("--service-name", "-n", help="Service name")
@click.option("--output-dir", "-o", type=click.Path(), help="Output directory")
def main(
    interactive: bool,
    config: str | None,
    service_type: str | None,
    service_name: str | None,
    output_dir: str | None,
) -> None:
    """Advanced Service Generator for Marty Microservices Framework."""

    # Determine framework root
    script_dir = Path(__file__).parent
    framework_root = script_dir.parent.parent

    generator = AdvancedServiceGenerator(framework_root)

    if interactive or not all([service_type, service_name]):
        # Run interactive wizard
        service_config = generator.run_interactive_wizard()
    else:
        # Use command line arguments
        service_config = ServiceConfiguration(
            name=service_name,
            type=ServiceType(service_type),
            description=f"Generated {service_name} service",
        )
        # Add default components based on service type
        service_config.infrastructure_components.update(
            [
                InfrastructureComponent.CONFIG_MANAGEMENT,
                InfrastructureComponent.OBSERVABILITY,
                InfrastructureComponent.KUBERNETES,
            ]
        )

    # Analyze dependencies
    generator.analyze_dependencies(service_config)

    # Generate service
    service_dir = generator.generate_service(service_config)

    # Display summary
    generator.display_generation_summary(service_config, service_dir)


if __name__ == "__main__":
    main()
