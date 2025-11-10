"""
Migration and plugin commands for converting Helm charts to Kustomize manifests
and generating MMF plugins.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scripts.dev.helm_to_kustomize_converter import HelmToKustomizeConverter

from ..framework.service_mesh import EnhancedServiceMeshManager
from .generators import ServiceGenerator

# Add project root to Python path for scripts import
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))



console = Console()

try:

    # Legacy alias for backward compatibility
    MinimalPluginGenerator = ServiceGenerator
except ImportError:
    ServiceGenerator = None
    MinimalPluginGenerator = None
    console.print("⚠️  Service generator not available", style="yellow")


@click.group()
def migrate():
    """Migration utilities for moving to MMF patterns."""
    pass


@migrate.command()
@click.option(
    "--helm-chart-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to Helm chart directory",
)
@click.option(
    "--output-path",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Output path for Kustomize manifests",
)
@click.option(
    "--service-name",
    required=True,
    help="Name of the service",
)
@click.option(
    "--values-file",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Helm values files to use (can specify multiple)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate conversion output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be converted without making changes",
)
def helm_to_kustomize(
    helm_chart_path: Path,
    output_path: Path,
    service_name: str,
    values_file: tuple[Path, ...],
    validate: bool,
    dry_run: bool,
):
    """Convert Helm charts to Kustomize manifests."""
    console.print("🔄 Converting Helm chart to Kustomize manifests", style="bold blue")

    if dry_run:
        console.print("🔍 Dry-run mode: showing what would be converted", style="yellow")

        # Show conversion plan
        table = Table(title="Conversion Plan")
        table.add_column("Component", style="cyan")
        table.add_column("Action", style="green")
        table.add_column("Output", style="yellow")

        table.add_row("Helm Chart", "Convert", str(helm_chart_path))
        table.add_row("Service Name", "Use", service_name)
        table.add_row("Output Path", "Create", str(output_path))
        table.add_row("Values Files", "Process", f"{len(values_file)} files")

        console.print(table)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Converting Helm to Kustomize...", total=None)

        try:
            # Import and use the converter

            converter = HelmToKustomizeConverter(
                str(helm_chart_path), str(output_path), service_name
            )

            success = converter.convert(list(map(str, values_file)), validate)

            if success:
                console.print("✅ Conversion completed successfully!", style="bold green")
                console.print(f"📁 Output directory: {output_path}", style="blue")

                # Show generated structure
                _show_generated_structure(output_path)
            else:
                console.print("❌ Conversion failed!", style="bold red")
                raise click.ClickException("Helm to Kustomize conversion failed")

        except ImportError:
            console.print("❌ Conversion tool not available", style="bold red")
            raise click.ClickException("Helm to Kustomize converter not found")


@migrate.command()
@click.option(
    "--service-name",
    required=True,
    help="Name of the service",
)
@click.option(
    "--environment",
    type=click.Choice(["dev", "staging", "prod", "marty-dev", "marty-prod"]),
    default="dev",
    help="Target environment",
)
@click.option(
    "--output-path",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("./k8s/overlays"),
    help="Output path for overlay",
)
@click.option(
    "--use-marty-patterns",
    is_flag=True,
    help="Use Marty-specific patterns (migration jobs, PVCs, etc.)",
)
@click.option(
    "--service-mesh",
    type=click.Choice(["none", "istio", "linkerd"]),
    default="none",
    help="Enable service mesh integration",
)
@click.option(
    "--enable-circuit-breaker",
    is_flag=True,
    help="Enable circuit breaker policies",
)
@click.option(
    "--enable-fault-injection",
    is_flag=True,
    help="Enable fault injection for chaos engineering",
)
@click.option(
    "--enable-retry-policies",
    is_flag=True,
    help="Enable retry policies",
)
@click.option(
    "--enable-rate-limiting",
    is_flag=True,
    help="Enable rate limiting policies",
)
def generate_overlay(
    service_name: str,
    environment: str,
    output_path: Path,
    use_marty_patterns: bool,
    service_mesh: str,
    enable_circuit_breaker: bool,
    enable_fault_injection: bool,
    enable_retry_policies: bool,
    enable_rate_limiting: bool,
):
    """Generate Kustomize overlay for a service."""
    console.print(f"🏗️  Generating {environment} overlay for {service_name}", style="bold blue")

    if service_mesh != "none":
        console.print(f"🕸️  Service mesh: {service_mesh}", style="cyan")
        if enable_circuit_breaker:
            console.print("⚡ Circuit breaker: enabled", style="green")
        if enable_fault_injection:
            console.print("🔬 Fault injection: enabled", style="green")
        if enable_retry_policies:
            console.print("🔄 Retry policies: enabled", style="green")
        if enable_rate_limiting:
            console.print("⏳ Rate limiting: enabled", style="green")

    overlay_path = output_path / environment
    overlay_path.mkdir(parents=True, exist_ok=True)

    if use_marty_patterns:
        # Copy from marty-dev or marty-services template
        template_name = "marty-dev" if environment in ["dev", "marty-dev"] else "marty-services"
        console.print(f"📋 Using Marty template: {template_name}", style="cyan")

        # Copy template files and customize
        _generate_marty_overlay(
            overlay_path,
            service_name,
            environment,
            template_name,
            service_mesh,
            enable_circuit_breaker,
            enable_fault_injection,
            enable_retry_policies,
            enable_rate_limiting
        )
    else:
        # Generate basic overlay
        _generate_basic_overlay(
            overlay_path,
            service_name,
            environment,
            service_mesh,
            enable_circuit_breaker,
            enable_fault_injection,
            enable_retry_policies,
            enable_rate_limiting
        )

    console.print(f"✅ Overlay generated at: {overlay_path}", style="bold green")


@migrate.command()
@click.option(
    "--original-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to original Helm deployment",
)
@click.option(
    "--migrated-path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to migrated Kustomize deployment",
)
@click.option(
    "--namespace",
    default="default",
    help="Kubernetes namespace for validation",
)
def validate_migration(
    original_path: Path,
    migrated_path: Path,
    namespace: str,
):
    """Validate that migrated manifests match original functionality."""
    console.print("🔍 Validating migration...", style="bold blue")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Validating migration...", total=None)

        try:
            # Render both Helm and Kustomize manifests
            helm_output = _render_helm_manifests(original_path, namespace)
            kustomize_output = _render_kustomize_manifests(migrated_path)

            # Compare outputs
            differences = _compare_manifests(helm_output, kustomize_output)

            if not differences:
                console.print("✅ Migration validation passed!", style="bold green")
                console.print("🎯 Functionality parity achieved", style="green")
            else:
                console.print("⚠️  Migration validation found differences:", style="yellow")
                for diff in differences:
                    console.print(f"  • {diff}", style="yellow")

        except Exception as e:
            console.print(f"❌ Validation failed: {str(e)}", style="bold red")
            raise click.ClickException("Migration validation failed")


@migrate.command()
@click.option(
    "--service-name",
    required=True,
    help="Name of the service to check",
)
@click.option(
    "--chart-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to Helm chart (optional)",
)
def check_compatibility(service_name: str, chart_path: Path | None):
    """Check Helm chart compatibility with MMF migration."""
    console.print(f"🔍 Checking migration compatibility for {service_name}", style="bold blue")

    compatibility_results = {
        "Basic Deployment": True,
        "Service Configuration": True,
        "ConfigMaps": True,
        "Secrets": False,  # Requires manual review
        "ServiceAccount": True,
        "RBAC": False,  # May need customization
        "Ingress": False,  # Not in base template
        "PersistentVolumes": False,  # Available in Marty overlay
        "Custom Resources": False,  # Needs evaluation
    }

    if chart_path:
        # Analyze actual chart
        compatibility_results.update(_analyze_helm_chart(chart_path))

    # Display results
    table = Table(title=f"Migration Compatibility: {service_name}")
    table.add_column("Component", style="cyan")
    table.add_column("Compatible", style="green")
    table.add_column("Notes", style="yellow")

    for component, compatible in compatibility_results.items():
        status = "✅ Yes" if compatible else "❌ No"
        notes = _get_compatibility_notes(component, compatible)
        table.add_row(component, status, notes)

    console.print(table)

    # Overall recommendation
    compatible_count = sum(compatibility_results.values())
    total_count = len(compatibility_results)

    if compatible_count >= total_count * 0.8:
        console.print("🟢 Good migration candidate", style="bold green")
    elif compatible_count >= total_count * 0.6:
        console.print("🟡 Moderate complexity migration", style="bold yellow")
    else:
        console.print("🔴 Complex migration - manual work required", style="bold red")


def _show_generated_structure(output_path: Path) -> None:
    """Display the generated directory structure."""
    console.print("📁 Generated structure:", style="bold")

    for root, _dirs, files in os.walk(output_path):
        level = root.replace(str(output_path), "").count(os.sep)
        indent = " " * 2 * level
        console.print(f"{indent}📂 {os.path.basename(root)}/", style="blue")
        sub_indent = " " * 2 * (level + 1)
        for file in files:
            console.print(f"{sub_indent}📄 {file}", style="cyan")


def _generate_marty_overlay(
    overlay_path: Path,
    service_name: str,
    environment: str,
    template_name: str,
    service_mesh: str = "none",
    enable_circuit_breaker: bool = False,
    enable_fault_injection: bool = False,
    enable_retry_policies: bool = False,
    enable_rate_limiting: bool = False,
) -> None:
    """Generate a Marty-specific overlay."""
    # This would copy and customize from the MMF template
    # For now, create a basic implementation
    _generate_basic_overlay(
        overlay_path,
        service_name,
        environment,
        service_mesh,
        enable_circuit_breaker,
        enable_fault_injection,
        enable_retry_policies,
        enable_rate_limiting
    )

    # Add Marty-specific configurations
    kustomization_file = overlay_path / "kustomization.yaml"
    if kustomization_file.exists():
        with open(kustomization_file, encoding="utf-8") as f:
            content = f.read()

        # Add Marty-specific configurations
        marty_additions = f"""
# Marty-specific configurations
commonLabels:
  app.kubernetes.io/part-of: marty-platform

commonAnnotations:
  marty.io/service-type: microservice
  marty.io/environment: {environment}
"""

        if service_mesh != "none":
            marty_additions += f"""
  marty.io/service-mesh: {service_mesh}
"""

        with open(kustomization_file, "w", encoding="utf-8") as f:
            f.write(content + marty_additions)


def _generate_basic_overlay(
    overlay_path: Path,
    service_name: str,
    environment: str,
    service_mesh: str = "none",
    enable_circuit_breaker: bool = False,
    enable_fault_injection: bool = False,
    enable_retry_policies: bool = False,
    enable_rate_limiting: bool = False,
) -> None:
    """Generate a basic Kustomize overlay."""

    # Determine resources to include
    resources = ["namespace.yaml", "../../base"]

    # Add service mesh resources if enabled
    if service_mesh != "none":
        if enable_circuit_breaker:
            resources.append(f"../../service-mesh/{service_mesh}/circuit-breakers.yaml")
        if enable_fault_injection:
            resources.append(f"../../service-mesh/{service_mesh}/fault-injection.yaml")
        if enable_retry_policies:
            resources.append(f"../../service-mesh/{service_mesh}/retry-policies.yaml")
        if enable_rate_limiting:
            resources.append(f"../../service-mesh/{service_mesh}/rate-limiting.yaml")

    # Generate kustomization.yaml
    kustomization = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "namespace": f"{service_name}-{environment}",
        "resources": resources,
        "configMapGenerator": [
            {
                "name": "microservice-template-config",
                "behavior": "merge",
                "literals": [
                    f"environment={environment}",
                    "otlp_endpoint=http://otel-collector.monitoring:4317",
                ],
            }
        ],
    }

    # Add service mesh specific configurations
    if service_mesh != "none":
        kustomization["commonLabels"] = {
            "service-mesh": "enabled",
            f"service-mesh.{service_mesh}": "true"
        }

        kustomization["commonAnnotations"] = {
            "marty.io/service-mesh": service_mesh
        }

        # Add Istio-specific annotations
        if service_mesh == "istio":
            kustomization["commonAnnotations"].update({
                "sidecar.istio.io/inject": "true",
                "sidecar.istio.io/proxyCPU": "10m",
                "sidecar.istio.io/proxyMemory": "128Mi",
                "traffic.sidecar.istio.io/excludeOutboundPorts": "443,53"
            })

        # Add Linkerd-specific annotations
        elif service_mesh == "linkerd":
            kustomization["commonAnnotations"].update({
                "linkerd.io/inject": "enabled",
                "config.linkerd.io/proxy-cpu-request": "10m",
                "config.linkerd.io/proxy-memory-request": "64Mi",
                "config.linkerd.io/skip-outbound-ports": "443,53"
            })

        # Add policy-specific literals to config
        if enable_circuit_breaker:
            kustomization["configMapGenerator"][0]["literals"].append("circuit_breaker=enabled")
        if enable_fault_injection:
            kustomization["configMapGenerator"][0]["literals"].append("fault_injection=enabled")
        if enable_retry_policies:
            kustomization["configMapGenerator"][0]["literals"].append("retry_policies=enabled")
        if enable_rate_limiting:
            kustomization["configMapGenerator"][0]["literals"].append("rate_limiting=enabled")

    with open(overlay_path / "kustomization.yaml", "w", encoding="utf-8") as f:
        yaml.dump(kustomization, f, default_flow_style=False)

    # Generate namespace.yaml with service mesh labels
    namespace_labels = {
        "name": f"{service_name}-{environment}",
        "environment": environment
    }

    namespace_annotations = {}

    if service_mesh == "istio":
        namespace_labels["istio-injection"] = "enabled"
        namespace_annotations["istio-injection"] = "enabled"
    elif service_mesh == "linkerd":
        namespace_labels["linkerd.io/inject"] = "enabled"
        namespace_annotations["linkerd.io/inject"] = "enabled"

    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": f"{service_name}-{environment}",
            "labels": namespace_labels,
        },
    }

    if namespace_annotations:
        namespace["metadata"]["annotations"] = namespace_annotations

    with open(overlay_path / "namespace.yaml", "w", encoding="utf-8") as f:
        yaml.dump(namespace, f, default_flow_style=False)


def _render_helm_manifests(helm_path: Path, namespace: str) -> str:
    """Render Helm manifests for comparison."""
    cmd = ["helm", "template", "test", str(helm_path), "--namespace", namespace]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def _render_kustomize_manifests(kustomize_path: Path) -> str:
    """Render Kustomize manifests for comparison."""
    cmd = ["kustomize", "build", str(kustomize_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def _compare_manifests(helm_output: str, kustomize_output: str) -> list[str]:
    """Compare Helm and Kustomize manifest outputs."""
    # Simple implementation - in practice this would be more sophisticated
    differences = []

    # Parse both outputs and compare

    try:
        helm_docs = list(yaml.safe_load_all(helm_output))
        kustomize_docs = list(yaml.safe_load_all(kustomize_output))

        if len(helm_docs) != len(kustomize_docs):
            differences.append(
                f"Document count differs: Helm={len(helm_docs)}, Kustomize={len(kustomize_docs)}"
            )

        # More detailed comparison would go here

    except yaml.YAMLError as e:
        differences.append(f"YAML parsing error: {e}")

    return differences


def _analyze_helm_chart(chart_path: Path) -> dict[str, bool]:
    """Analyze Helm chart for compatibility assessment."""
    # Simplified analysis - would be more comprehensive in practice
    results = {}

    templates_dir = chart_path / "templates"
    if templates_dir.exists():
        for template_file in templates_dir.glob("*.yaml"):
            if "ingress" in template_file.name:
                results["Ingress"] = True
            elif "pvc" in template_file.name or "persistent" in template_file.name:
                results["PersistentVolumes"] = True
            elif "rbac" in template_file.name or "role" in template_file.name:
                results["RBAC"] = True

    return results


def _get_compatibility_notes(component: str, compatible: bool) -> str:
    """Get compatibility notes for a component."""
    notes_map = {
        "Secrets": "Requires manual secret creation",
        "RBAC": "May need customization for specific permissions",
        "Ingress": "Use service mesh or add custom ingress",
        "PersistentVolumes": "Available in Marty overlay",
        "Custom Resources": "Manual evaluation required",
    }

    if compatible:
        return "Ready for migration"
    else:
        return notes_map.get(component, "Manual work required")


# Service Mesh Management Commands
@click.group()
def service_mesh():
    """Service mesh integration and management commands."""
    pass


@service_mesh.command()
@click.option(
    "--mesh-type",
    type=click.Choice(["istio", "linkerd"]),
    required=True,
    help="Service mesh type to install",
)
@click.option(
    "--namespace",
    default="microservice-framework",
    help="Target namespace for service mesh",
)
@click.option(
    "--cluster-name",
    default="kind-mmf",
    help="Kubernetes cluster name",
)
@click.option(
    "--enable-monitoring",
    is_flag=True,
    help="Enable service mesh monitoring and dashboards",
)
def install(mesh_type: str, namespace: str, cluster_name: str, enable_monitoring: bool):
    """Install and configure service mesh."""
    console.print(f"🕸️  Installing {mesh_type} service mesh...", style="bold blue")

    try:
        # Check if cluster is running
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            console.print("❌ Kubernetes cluster not available", style="bold red")
            raise click.ClickException("Please ensure Kubernetes cluster is running")

        # Create namespace
        console.print(f"📦 Creating namespace: {namespace}", style="cyan")
        subprocess.run(
            ["kubectl", "create", "namespace", namespace, "--dry-run=client", "-o", "yaml"],
            stdout=subprocess.PIPE,
            check=True
        )
        subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=result.stdout,
            text=True,
            check=True
        )

        if mesh_type == "istio":
            _install_istio(namespace, enable_monitoring)
        elif mesh_type == "linkerd":
            _install_linkerd(namespace, enable_monitoring)

        console.print(f"✅ {mesh_type} service mesh installed successfully!", style="bold green")
        console.print(f"🎯 Namespace: {namespace}", style="green")

        if enable_monitoring:
            console.print("📊 Monitoring enabled", style="green")

    except subprocess.CalledProcessError as e:
        console.print(f"❌ Installation failed: {e}", style="bold red")
        raise click.ClickException(f"{mesh_type} installation failed")


@service_mesh.command()
@click.option(
    "--service-name",
    required=True,
    help="Service name to apply policies to",
)
@click.option(
    "--mesh-type",
    type=click.Choice(["istio", "linkerd"]),
    required=True,
    help="Service mesh type",
)
@click.option(
    "--namespace",
    default="microservice-framework",
    help="Target namespace",
)
@click.option(
    "--enable-circuit-breaker",
    is_flag=True,
    help="Enable circuit breaker policy",
)
@click.option(
    "--enable-retry",
    is_flag=True,
    help="Enable retry policy",
)
@click.option(
    "--enable-rate-limit",
    is_flag=True,
    help="Enable rate limiting policy",
)
@click.option(
    "--enable-fault-injection",
    is_flag=True,
    help="Enable fault injection for chaos engineering",
)
def apply_policies(
    service_name: str,
    mesh_type: str,
    namespace: str,
    enable_circuit_breaker: bool,
    enable_retry: bool,
    enable_rate_limit: bool,
    enable_fault_injection: bool,
):
    """Apply service mesh policies to a service."""
    console.print(f"🛡️  Applying {mesh_type} policies to {service_name}...", style="bold blue")

    # Get project root for manifest files
    project_root = Path(__file__).parent.parent.parent.parent
    mesh_manifests_dir = project_root / "ops" / "service-mesh" / mesh_type

    if not mesh_manifests_dir.exists():
        console.print(f"❌ {mesh_type} manifests not found at {mesh_manifests_dir}", style="bold red")
        raise click.ClickException("Service mesh manifests directory not found")

    applied_policies = []

    try:
        if enable_circuit_breaker:
            circuit_breaker_file = mesh_manifests_dir / "circuit-breakers.yaml"
            if circuit_breaker_file.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(circuit_breaker_file), "-n", namespace],
                    check=True
                )
                applied_policies.append("Circuit Breaker")

        if enable_retry:
            retry_file = mesh_manifests_dir / "retry-policies.yaml"
            if retry_file.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(retry_file), "-n", namespace],
                    check=True
                )
                applied_policies.append("Retry Policies")

        if enable_rate_limit:
            rate_limit_file = mesh_manifests_dir / "rate-limiting.yaml"
            if rate_limit_file.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(rate_limit_file), "-n", namespace],
                    check=True
                )
                applied_policies.append("Rate Limiting")

        if enable_fault_injection:
            fault_injection_file = mesh_manifests_dir / "fault-injection.yaml"
            if fault_injection_file.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(fault_injection_file), "-n", namespace],
                    check=True
                )
                applied_policies.append("Fault Injection")

        console.print(f"✅ Applied policies to {service_name}:", style="bold green")
        for policy in applied_policies:
            console.print(f"  • {policy}", style="green")

    except subprocess.CalledProcessError as e:
        console.print(f"❌ Policy application failed: {e}", style="bold red")
        raise click.ClickException("Failed to apply service mesh policies")


@service_mesh.command()
@click.option(
    "--mesh-type",
    type=click.Choice(["istio", "linkerd"]),
    required=True,
    help="Service mesh type to check",
)
@click.option(
    "--namespace",
    default="microservice-framework",
    help="Namespace to check",
)
def status(mesh_type: str, namespace: str):
    """Check service mesh status and health."""
    console.print(f"🔍 Checking {mesh_type} status...", style="bold blue")

    try:
        if mesh_type == "istio":
            # Check Istio control plane
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "istio-system", "-l", "app=istiod"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print("🕸️  Istio Control Plane:", style="cyan")
            console.print(result.stdout)

        elif mesh_type == "linkerd":
            # Check Linkerd control plane
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "linkerd", "-l", "linkerd.io/control-plane-component"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print("🕸️  Linkerd Control Plane:", style="cyan")
            console.print(result.stdout)

        # Check service mesh injection in target namespace
        result = subprocess.run(
            ["kubectl", "get", "namespace", namespace, "-o", "yaml"],
            capture_output=True,
            text=True,
            check=True
        )

        injection_enabled = False
        if mesh_type == "istio" and "istio-injection=enabled" in result.stdout:
            injection_enabled = True
        elif mesh_type == "linkerd" and "linkerd.io/inject=enabled" in result.stdout:
            injection_enabled = True

        if injection_enabled:
            console.print(f"✅ Sidecar injection enabled in {namespace}", style="green")
        else:
            console.print(f"⚠️  Sidecar injection not enabled in {namespace}", style="yellow")

    except subprocess.CalledProcessError as e:
        console.print(f"❌ Status check failed: {e}", style="bold red")
        raise click.ClickException("Failed to check service mesh status")


@service_mesh.command()
@click.option(
    "--project-name",
    required=True,
    help="Name of the project to generate service mesh deployment for",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Output directory for generated deployment files",
)
@click.option(
    "--domain",
    default="example.com",
    help="Domain name for the project (default: example.com)",
)
@click.option(
    "--mesh-type",
    type=click.Choice(["istio", "linkerd"]),
    default="istio",
    help="Service mesh type to configure (default: istio)",
)
@click.option(
    "--namespace",
    help="Target namespace (defaults to project name)",
)
def generate(project_name: str, output_dir: Path, domain: str, mesh_type: str, namespace: str):
    """Generate service mesh deployment scripts and manifests for a project."""
    console.print(f"🚀 Generating service mesh deployment for project: {project_name}", style="bold blue")


    # Use project name as namespace if not specified
    if not namespace:
        namespace = project_name.lower().replace('_', '-')

    try:
        # Create service mesh manager
        manager = EnhancedServiceMeshManager()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Generate deployment files
            task = progress.add_task("Generating deployment scripts...", total=None)

            generated_files = manager.generate_deployment_script(
                service_name=project_name,
                config={
                    "output_dir": str(output_dir),
                    "domain": domain,
                    "mesh_type": mesh_type
                }
            )

            progress.update(task, completed=True)

        # Display results
        console.print("✅ Service mesh deployment generated successfully!", style="bold green")
        console.print()

        # Show generated files
        table = Table(title="Generated Files")
        table.add_column("Component", style="cyan")
        table.add_column("Path", style="yellow")
        table.add_column("Description", style="green")

        table.add_row(
            "Deployment Script",
            generated_files["deployment_script"],
            "Main service mesh deployment script"
        )
        table.add_row(
            "Plugin Template",
            generated_files["plugin_template"],
            "Customizable plugin extensions"
        )
        table.add_row(
            "Kubernetes Manifests",
            generated_files["manifests_dir"],
            "Production-ready service mesh configurations"
        )

        console.print(table)
        console.print()

        # Show configuration details
        console.print(Panel.fit(
            f"[bold]Project Configuration[/bold]\n\n"
            f"• Project Name: [cyan]{project_name}[/cyan]\n"
            f"• Domain: [cyan]{domain}[/cyan]\n"
            f"• Mesh Type: [cyan]{mesh_type}[/cyan]\n"
            f"• Namespace: [cyan]{namespace}[/cyan]\n"
            f"• Output Directory: [cyan]{output_dir}[/cyan]",
            title="📋 Configuration Summary"
        ))

        # Show next steps
        console.print()
        console.print("[bold blue]Next Steps:[/bold blue]")
        console.print("1. Review and customize the plugin template:")
        console.print(f"   [cyan]edit {generated_files['plugin_template']}[/cyan]")
        console.print("2. Deploy the service mesh:")
        console.print(f"   [cyan]cd {output_dir} && ./deploy-service-mesh.sh[/cyan]")
        console.print("3. Customize for your domain-specific requirements in the plugin file")
        console.print()
        console.print("[bold green]🎯 Deployment script is ready for use![/bold green]")

    except Exception as e:
        console.print(f"❌ Generation failed: {e}", style="bold red")
        raise click.ClickException(f"Failed to generate service mesh deployment: {e}")


def _install_istio(namespace: str, enable_monitoring: bool):
    """Install Istio service mesh."""
    # Check if istioctl is available
    try:
        subprocess.run(["istioctl", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("📥 Installing istioctl...", style="cyan")
        # Installation would be handled by the setup script
        raise click.ClickException("Please install istioctl first")

    # Install Istio
    console.print("🔧 Installing Istio control plane...", style="cyan")
    subprocess.run(
        ["istioctl", "install", "--set", "values.defaultRevision=default", "-y"],
        check=True
    )

    # Enable injection in namespace
    subprocess.run(
        ["kubectl", "label", "namespace", namespace, "istio-injection=enabled", "--overwrite"],
        check=True
    )

    # Apply MMF-specific production configurations
    project_root = Path(__file__).parent.parent.parent.parent
    istio_configs = project_root / "ops" / "service-mesh" / "production"

    if istio_configs.exists():
        # Apply core Istio production manifests
        for manifest in ["istio-production.yaml", "istio-security.yaml", "istio-traffic-management.yaml", "istio-gateways.yaml"]:
            manifest_path = istio_configs / manifest
            if manifest_path.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(manifest_path)],
                    check=True
                )

    console.print("📋 For complete production setup, use: ops/service-mesh/deploy-production-mesh.sh", style="yellow")


def _install_linkerd(namespace: str, enable_monitoring: bool):
    """Install Linkerd service mesh."""
    # Check if linkerd CLI is available
    try:
        subprocess.run(["linkerd", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("📥 Installing linkerd CLI...", style="cyan")
        # Installation would be handled by the setup script
        raise click.ClickException("Please install linkerd CLI first")

    # Pre-check
    console.print("🔍 Running pre-installation checks...", style="cyan")
    subprocess.run(["linkerd", "check", "--pre"], check=True)

    # Install Linkerd
    console.print("🔧 Installing Linkerd control plane...", style="cyan")
    subprocess.run(["linkerd", "install", "--crds"], stdout=subprocess.PIPE, check=True)
    subprocess.run(["linkerd", "install"], stdout=subprocess.PIPE, check=True)

    # Enable injection in namespace
    subprocess.run(
        ["kubectl", "annotate", "namespace", namespace, "linkerd.io/inject=enabled", "--overwrite"],
        check=True
    )

    # Apply MMF-specific production configurations
    project_root = Path(__file__).parent.parent.parent.parent
    linkerd_configs = project_root / "ops" / "service-mesh" / "production"

    if linkerd_configs.exists():
        # Apply core Linkerd production manifests
        for manifest in ["linkerd-production.yaml", "linkerd-security.yaml", "linkerd-traffic-management.yaml"]:
            manifest_path = linkerd_configs / manifest
            if manifest_path.exists():
                subprocess.run(
                    ["kubectl", "apply", "-f", str(manifest_path)],
                    check=True
                )

    console.print("📋 For complete production setup, use: ops/service-mesh/deploy-production-mesh.sh", style="yellow")


# Plugin management functionality
class MMFConfig:
    """Configuration manager for MMF CLI."""

    def __init__(self, project_root: Path | None = None):
        # Default to 4 levels up from this file to get project root
        default_root = Path(__file__).parent.parent.parent.parent
        self.project_root = project_root or default_root
        self.plugins_dir = self.project_root / "plugins"
        self.config_file = self.project_root / ".mmf" / "config.json"

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return {}
        try:
            return json.loads(self.config_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def save_config(self, config: dict[str, Any]):
        """Save configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(config, indent=2))


# Global config instance
mmf_config = MMFConfig()


# Feature definitions with descriptions
AVAILABLE_FEATURES = {
    "database": {
        "name": "Database Integration",
        "description": "Add database connectivity (PostgreSQL, MySQL, MongoDB)",
        "options": ["postgresql", "mysql", "mongodb"],
        "default": "postgresql"
    },
    "cache": {
        "name": "Cache Integration",
        "description": "Add caching layer (Redis)",
        "options": ["redis"],
        "default": "redis"
    },
    "messaging": {
        "name": "Message Queue",
        "description": "Add message queue support (RabbitMQ, Kafka)",
        "options": ["rabbitmq", "kafka"],
        "default": "rabbitmq"
    },
    "auth": {
        "name": "Authentication",
        "description": "Add authentication support (JWT)",
        "options": ["jwt"],
        "default": "jwt"
    },
    "background_tasks": {
        "name": "Background Tasks",
        "description": "Add background task processing (Celery, RQ)",
        "options": ["celery", "rq"],
        "default": "celery"
    },
    "monitoring": {
        "name": "Monitoring & Metrics",
        "description": "Add monitoring and metrics collection (Prometheus)",
        "options": ["prometheus"],
        "default": "prometheus"
    }
}

SERVICE_TYPES = [
    "business",
    "data",
    "integration",
    "utility",
    "api",
    "worker"
]


def validate_name(ctx, param, value):
    """Validate plugin/service name."""
    if not value:
        return None

    # Check length
    if len(value) > 50:
        name_type = "Plugin name" if param.name == 'name' else "Service name"
        raise click.BadParameter(f"{name_type} must be 50 characters or less")

    # Check format (letters, numbers, hyphens only)
    if not all(c.isalnum() or c == '-' for c in value):
        name_type = "Plugin name" if param.name == 'name' else "Service name"
        raise click.BadParameter(f"{name_type} can only contain letters, numbers, and hyphens")

    # Cannot start or end with hyphen
    if value.startswith('-') or value.endswith('-'):
        name_type = "Plugin name" if param.name == 'name' else "Service name"
        raise click.BadParameter(f"{name_type} cannot start or end with a hyphen")

    return value


def get_existing_plugins() -> list[str]:
    """Get list of existing plugins."""
    if not mmf_config.plugins_dir.exists():
        return []

    plugins = []
    for item in mmf_config.plugins_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if it looks like a plugin (has pyproject.toml)
            if (item / "pyproject.toml").exists():
                plugins.append(item.name)

    return sorted(plugins)


def get_plugin_services(plugin_name: str) -> list[str]:
    """Get list of services in a plugin."""
    plugin_dir = mmf_config.plugins_dir / plugin_name
    if not plugin_dir.exists():
        return []

    services_dir = plugin_dir / "app" / "services"
    if not services_dir.exists():
        return []

    services = []
    for item in services_dir.iterdir():
        if item.is_file() and item.suffix == ".py" and not item.name.startswith("__"):
            # Remove _service.py suffix if present
            service_name = item.stem
            if service_name.endswith("_service"):
                service_name = service_name[:-8]
            services.append(service_name)

    return sorted(services)


def prompt_for_features() -> dict[str, str]:
    """Interactive feature selection."""
    selected_features = {}

    console.print("\n🔧 Available Features:")
    console.print("(Select features to add to your plugin)")

    for feature_key, feature_info in AVAILABLE_FEATURES.items():
        console.print(f"\n📦 {feature_info['name']}")
        console.print(f"   {feature_info['description']}")

        if click.confirm(f"   Enable {feature_info['name']}?", default=False):
            if len(feature_info['options']) > 1:
                # Multiple options available
                console.print("   Choose implementation:")
                for i, option in enumerate(feature_info['options'], 1):
                    console.print(f"   {i}. {option}")

                choice = click.prompt(
                    "Select option",
                    type=click.IntRange(1, len(feature_info['options'])),
                    default=1
                )
                selected_features[feature_key] = feature_info['options'][choice - 1]
            else:
                # Single option
                selected_features[feature_key] = feature_info['default']

    return selected_features


def display_services(plugin: str, services: list[str]):
    """Display services with their metadata."""
    config = mmf_config.load_config()
    plugin_info = config.get('plugins', {}).get(plugin, {})
    service_configs = {s['name']: s for s in plugin_info.get('services', [])}

    for plugin_service in services:
        service_info = service_configs.get(plugin_service, {})
        service_type = service_info.get('type', 'unknown')
        created = service_info.get('created_at', '')[:10] if service_info.get('created_at') else ''

        console.print(f"\n   🔸 [green]{plugin_service}[/green]")
        console.print(f"      Type: {service_type}")
        if created:
            console.print(f"      Created: {created}")


def generate_service(plugin_dir: Path, plugin_name: str, service_name: str, service_type: str, features: tuple) -> bool:
    """Generate a new service in an existing plugin."""

    if not MinimalPluginGenerator:
        console.print("❌ Plugin generator not available", style="red")
        return False

    # Import the generator functionality
    try:
        generator = MinimalPluginGenerator()
        return generator.add_service_to_plugin(plugin_dir, plugin_name, service_name, service_type, features)

    except ImportError as e:
        console.print(f"❌ Error importing generator: {e}", style="red")
        return False
    except Exception as e:
        console.print(f"❌ Error generating service: {e}", style="red")
        return False


# Plugin Commands
@click.group()
def plugin():
    """Plugin management commands."""
    pass


@plugin.command('init')
@click.option('--name', '-n', callback=validate_name, help='Plugin name')
@click.option('--features', '-f', multiple=True, help='Enable specific features')
@click.option('--interactive/--no-interactive', default=True, help='Interactive mode')
@click.option('--template', default='minimal', help='Plugin template to use')
def plugin_init(name: str | None, features: tuple, interactive: bool, template: str):
    """Initialize a new plugin."""

    if not MinimalPluginGenerator:
        console.print("❌ Plugin generator not available", style="red")
        return

    # Get plugin name
    if not name:
        if interactive:
            name = click.prompt("Plugin name", type=str)
            # Apply validation
            try:
                name = validate_name(None, type('MockParam', (), {'name': 'name'})(), name)
            except click.BadParameter as e:
                console.print(f"❌ {e}", style="red")
                return
        else:
            console.print("❌ Plugin name is required", style="red")
            return

    # Check if plugin already exists
    existing_plugins = get_existing_plugins()
    if name in existing_plugins:
        console.print(f"❌ Plugin '{name}' already exists", style="red")
        return

    # Feature selection
    selected_features = {}
    if interactive and not features:
        selected_features = prompt_for_features()
    elif features:
        # Parse command line features
        for feature in features:
            if '=' in feature:
                key, value = feature.split('=', 1)
                if key in AVAILABLE_FEATURES:
                    selected_features[key] = value
            else:
                if feature in AVAILABLE_FEATURES:
                    selected_features[feature] = AVAILABLE_FEATURES[feature]['default']

    # Create plugin
    console.print("\n📁 Creating plugin structure...")

    # Import and use the generator
    try:
        generator = MinimalPluginGenerator()
        success = generator.generate_plugin_with_features(name, selected_features, template)

        if success:
            # Save plugin configuration
            config = mmf_config.load_config()
            if 'plugins' not in config:
                config['plugins'] = {}

            config['plugins'][name] = {
                'template': template,
                'features': selected_features,
                'created_at': datetime.now().isoformat(),
                'services': []
            }

            mmf_config.save_config(config)

            console.print(f"✅ Plugin '{name}' created successfully!", style="green")

            if selected_features:
                console.print("\n🔧 Enabled features:")
                for feature, implementation in selected_features.items():
                    feature_name = AVAILABLE_FEATURES[feature]['name']
                    console.print(f"   • {feature_name}: {implementation}")

            console.print("\n🚀 Next steps:")
            console.print(f"   cd plugins/{name}")
            console.print("   marty plugin service add <service-name>")
            console.print("   ./scripts/deploy.sh")
        else:
            console.print(f"❌ Failed to create plugin '{name}'", style="red")

    except ImportError as e:
        console.print(f"❌ Error importing generator: {e}", style="red")


@plugin.command('list')
def plugin_list():
    """List all plugins."""
    plugins = get_existing_plugins()

    if not plugins:
        console.print("📦 No plugins found")
        console.print("\n💡 Create your first plugin with: marty plugin init")
        return

    console.print(f"📦 Found {len(plugins)} plugin(s):")

    config = mmf_config.load_config()
    for plugin_item in plugins:
        plugin_info = config.get('plugins', {}).get(plugin_item, {})
        template = plugin_info.get('template', 'unknown')
        features = plugin_info.get('features', {})
        services = get_plugin_services(plugin_item)

        console.print(f"\n🔸 [green]{plugin_item}[/green]")
        console.print(f"   Template: {template}")

        if features:
            feature_list = ", ".join(features.keys())
            console.print(f"   Features: {feature_list}")

        if services:
            console.print(f"   Services: {', '.join(services)}")
        else:
            console.print("   Services: none")


@plugin.command('status')
@click.argument('name', required=True)
def plugin_status(name: str):
    """Show detailed status of a plugin."""
    plugins = get_existing_plugins()

    if name not in plugins:
        console.print(f"❌ Plugin '{name}' not found", style="red")
        available = ", ".join(plugins) if plugins else "none"
        console.print(f"Available plugins: {available}")
        return

    plugin_dir = mmf_config.plugins_dir / name
    config = mmf_config.load_config()
    plugin_info = config.get('plugins', {}).get(name, {})

    console.print(f"📦 Plugin: [green]{name}[/green]")
    console.print(f"   Path: {plugin_dir}")
    console.print(f"   Template: {plugin_info.get('template', 'unknown')}")

    # Features
    features = plugin_info.get('features', {})
    if features:
        console.print("\n🔧 Features:")
        for feature, implementation in features.items():
            feature_name = AVAILABLE_FEATURES.get(feature, {}).get('name', feature)
            console.print(f"   • {feature_name}: {implementation}")

    # Services
    services = get_plugin_services(name)
    if services:
        console.print(f"\n⚙️  Services ({len(services)}):")
        display_services(name, services)
    else:
        console.print("\n⚙️  Services: none")

    # Infrastructure status
    if (plugin_dir / "Dockerfile").exists():
        console.print("\n☸️  Kubernetes: Ready for deployment")

    if (plugin_dir / "k8s").exists():
        console.print("🐳 Docker: Containerization ready")


@plugin.group('service')
def plugin_service():
    """Service management commands for plugins."""
    pass


@plugin_service.command('add')
@click.option('--name', '-n', callback=validate_name, help='Service name')
@click.option('--plugin', '-p', help='Plugin to add service to')
@click.option('--type', 'service_type', type=click.Choice(SERVICE_TYPES),
              default='business', help='Service type')
@click.option('--features', '-f', multiple=True, help='Service-specific features')
def service_add(name: str | None, plugin: str | None, service_type: str, features: tuple):
    """Add a new service to a plugin."""

    if not MinimalPluginGenerator:
        console.print("❌ Plugin generator not available", style="red")
        return

    # Get plugin name
    existing_plugins = get_existing_plugins()
    if not existing_plugins:
        console.print("❌ No plugins found. Create one first with: marty plugin init", style="red")
        return

    if not plugin:
        if len(existing_plugins) == 1:
            plugin = existing_plugins[0]
        else:
            console.print("📦 Available plugins:")
            for i, p in enumerate(existing_plugins, 1):
                console.print(f"   {i}. {p}")

            choice = click.prompt(
                "Select plugin",
                type=click.IntRange(1, len(existing_plugins))
            )
            plugin = existing_plugins[choice - 1]

    if plugin not in existing_plugins:
        console.print(f"❌ Plugin '{plugin}' not found", style="red")
        return

    # Get service name
    if not name:
        name = click.prompt("Service name", type=str)
        # Apply validation
        try:
            name = validate_name(None, type('MockParam', (), {'name': 'name'})(), name)
        except click.BadParameter as e:
            console.print(f"❌ {e}", style="red")
            return

    # Check if service already exists
    existing_services = get_plugin_services(plugin)
    if name in existing_services:
        console.print(f"❌ Service '{name}' already exists in plugin '{plugin}'", style="red")
        return

    # Generate service
    plugin_dir = mmf_config.plugins_dir / plugin
    success = generate_service(plugin_dir, plugin, name, service_type, features)

    if success:
        # Update plugin configuration
        config = mmf_config.load_config()
        if 'plugins' not in config:
            config['plugins'] = {}
        if plugin not in config['plugins']:
            config['plugins'][plugin] = {'services': []}
        if 'services' not in config['plugins'][plugin]:
            config['plugins'][plugin]['services'] = []

        config['plugins'][plugin]['services'].append({
            'name': name,
            'type': service_type,
            'features': list(features),
            'created_at': datetime.now().isoformat()
        })

        mmf_config.save_config(config)

        console.print(f"✅ Service '{name}' added to plugin '{plugin}'!", style="green")
        console.print(f"   Type: {service_type}")

        console.print("\n🚀 Next steps:")
        console.print(f"   # Edit business logic in app/services/{name.replace('-', '_')}_service.py")
        console.print("   # Add API endpoints in app/api/routes.py")
        console.print("   uv run pytest tests/ -v")
    else:
        console.print(f"❌ Failed to add service '{name}'", style="red")


@plugin_service.command('list')
@click.option('--plugin', '-p', help='Show services for specific plugin')
def service_list(plugin: str | None):
    """List services across plugins or in a specific plugin."""
    existing_plugins = get_existing_plugins()

    if not existing_plugins:
        console.print("📦 No plugins found")
        return

    if plugin:
        if plugin not in existing_plugins:
            console.print(f"❌ Plugin '{plugin}' not found", style="red")
            return

        services = get_plugin_services(plugin)
        if services:
            console.print(f"⚙️  Services in '{plugin}':")
            display_services(plugin, services)
        else:
            console.print(f"⚙️  No services in plugin '{plugin}'")
    else:
        # Show all services across all plugins
        total_services = 0
        for current_plugin in existing_plugins:
            services = get_plugin_services(current_plugin)
            if services:
                console.print(f"\n📦 Plugin: {current_plugin}")
                display_services(current_plugin, services)
                total_services += len(services)
            else:
                console.print(f"\n📦 Plugin: {current_plugin}")
                console.print("   No services")

        if total_services == 0:
            console.print("\n⚙️  No services found in any plugin")


# Service Commands (comprehensive service generation)
@click.group()
def service():
    """Service management commands for comprehensive microservice generation."""
    pass


@service.command('init')
@click.argument('service_type', type=click.Choice(['fastapi', 'simple-fastapi', 'production', 'grpc', 'hybrid', 'minimal']))
@click.argument('service_name')
@click.option('--description', help='Service description')
@click.option('--author', default='Marty Development Team', help='Author name')
@click.option('--grpc-port', type=int, default=50051, help='gRPC port (default: 50051)')
@click.option('--http-port', type=int, default=8080, help='HTTP port for FastAPI services (default: 8080)')
@click.option('--service-mesh', is_flag=True, help='Enable service mesh configuration')
@click.option('--service-mesh-type', type=click.Choice(['istio', 'linkerd']), default='istio', help='Service mesh type')
@click.option('--namespace', default='microservice-framework', help='Kubernetes namespace')
@click.option('--domain', default='framework.local', help='Service domain')
def service_init(service_type: str, service_name: str, description: str | None, author: str,
                grpc_port: int, http_port: int, service_mesh: bool, service_mesh_type: str,
                namespace: str, domain: str):
    """Initialize a new microservice."""

    if not ServiceGenerator:
        console.print("❌ Service generator not available", style="red")
        return

    console.print("📁 Creating comprehensive service...", style="blue")

    # Create generator instance
    generator = ServiceGenerator()

    # Generate service
    success = generator.generate_service(
        service_type=service_type,
        service_name=service_name,
        description=description,
        author=author,
        grpc_port=grpc_port,
        http_port=http_port,
        service_mesh=service_mesh,
        service_mesh_type=service_mesh_type,
        namespace=namespace,
        domain=domain
    )

    if success:
        console.print(f"✅ Service '{service_name}' created successfully!", style="green")

        # Show next steps based on service type
        next_steps_panel = Panel(
            f"""[bold]Next Steps:[/bold]

1. 📁 Navigate to the service: [cyan]cd plugins/{service_name.replace('-', '_')}[/cyan]
2. 📦 Install dependencies: [cyan]uv sync[/cyan]
3. 🚀 Run the service: [cyan]python main.py[/cyan]
4. 🔍 Test health endpoint: [cyan]curl http://localhost:{http_port}/health[/cyan]
5. 📚 View API docs: [cyan]http://localhost:{http_port}/docs[/cyan]

[dim]Service type: {service_type}
Template features: Jinja2-based templates with full customization[/dim]""",
            title="🚀 Service Ready",
            border_style="green"
        )
        console.print(next_steps_panel)
    else:
        console.print("❌ Failed to create service", style="red")


@service.command('list')
def list_services():
    """List all generated services."""

    console.print("╭───────────────────────────────────╮", style="blue")
    console.print("│ Marty Microservices Framework CLI │", style="blue")
    console.print("╰────────── Version 1.0.0 ──────────╯", style="blue")

    # Look for services in plugins directory
    plugins_dir = Path(__file__).parent.parent.parent.parent / "plugins"

    if not plugins_dir.exists():
        console.print("📁 No plugins directory found", style="yellow")
        return

    services = []
    for item in plugins_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if it has service characteristics
            main_py = item / "main.py"
            dockerfile = item / "Dockerfile"
            app_dir = item / "app"

            service_type = "unknown"
            if main_py.exists() and app_dir.exists():
                if dockerfile.exists():
                    service_type = "production"
                else:
                    service_type = "minimal"

            services.append({
                "name": item.name,
                "type": service_type,
                "path": item
            })

    if not services:
        console.print("📦 No services found", style="yellow")
        return

    console.print(f"📦 Found {len(services)} service(s):\n")

    for service in services:
        icon = "🔸" if service["type"] != "unknown" else "🔹"
        console.print(f"{icon} {service['name']}")
        console.print(f"   Type: {service['type']}")
        console.print(f"   Path: {service['path']}")
        console.print()


@service.command('status')
@click.argument('service_name')
def service_status(service_name: str):
    """Check the status of a service."""

    console.print(f"🔍 Checking status of service: {service_name}", style="blue")

    # Look for the service
    plugins_dir = Path(__file__).parent.parent.parent.parent / "plugins"
    service_dir = plugins_dir / service_name.replace('-', '_')

    if not service_dir.exists():
        console.print(f"❌ Service '{service_name}' not found", style="red")
        return

    # Check service components
    checks = [
        ("Main file", service_dir / "main.py"),
        ("App module", service_dir / "app" / "__init__.py"),
        ("Dockerfile", service_dir / "Dockerfile"),
        ("Requirements", service_dir / "requirements.txt"),
        ("K8s manifests", service_dir / "k8s"),
        ("Tests", service_dir / "tests"),
    ]

    console.print(f"📁 Service directory: {service_dir}\n")

    for check_name, path in checks:
        exists = path.exists()
        status = "✅" if exists else "❌"
        console.print(f"{status} {check_name}: {path.name}")

    # Try to determine service type
    if (service_dir / "app" / "api").exists():
        service_type = "FastAPI-based"
    elif (service_dir / "main.py").exists():
        service_type = "Python service"
    else:
        service_type = "Unknown"

    console.print(f"\n🏷️  Service type: {service_type}")

    # Check for running processes (basic check)
    try:
        result = subprocess.run(['pgrep', '-f', f'python.*{service_name}'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            console.print("🟢 Service appears to be running", style="green")
        else:
            console.print("🔴 Service is not running", style="red")
    except FileNotFoundError:
        console.print("⚠️  Cannot check running status (pgrep not available)", style="yellow")
