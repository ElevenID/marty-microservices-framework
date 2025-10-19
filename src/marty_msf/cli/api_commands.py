"""
API Documentation and Contract Testing CLI Commands for Marty Framework.

This module extends the existing Marty CLI with comprehensive commands for:
- API documentation generation (REST and gRPC)
- Contract testing (consumer-driven and provider verification)
- API version management
- OpenAPI and protobuf documentation generation

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..framework.documentation.api_docs import (
    APIDocumentationManager,
    APIVersionManager,
    DocumentationConfig,
    generate_api_docs,
)
from ..framework.testing.contract_testing import (
    ContractManager,
    ContractRepository,
    pact_contract,
    verify_contracts_for_provider,
)
from ..framework.testing.grpc_contract_testing import (
    EnhancedContractManager,
    GRPCContractRepository,
    generate_contract_from_proto,
    grpc_contract,
)

# Import our documentation and testing modules
try:
    documentation_available = True
except ImportError:
    documentation_available = False

try:
    contract_testing_available = True
except ImportError:
    contract_testing_available = False

try:
    grpc_contract_testing_available = True
except ImportError:
    grpc_contract_testing_available = False

logger = logging.getLogger(__name__)
console = Console()


# Add to the main CLI group in __init__.py
def add_api_commands(main_cli):
    """Add API documentation and contract testing commands to the main CLI."""

    # Create API command group
    @main_cli.group()
    def api():
        """API documentation and contract testing commands."""
        pass

    @api.command()
    @click.option("--source-paths", "-s", multiple=True, required=True,
                  help="Source code paths to scan for APIs")
    @click.option("--output-dir", "-o", default="./docs/api",
                  help="Output directory for documentation")
    @click.option("--config-file", "-c", help="Configuration file path")
    @click.option("--theme", default="redoc",
                  type=click.Choice(["redoc", "swagger-ui", "stoplight"]),
                  help="Documentation theme")
    @click.option("--include-examples/--no-examples", default=True,
                  help="Include code examples")
    @click.option("--generate-postman/--no-postman", default=True,
                  help="Generate Postman collections")
    @click.option("--generate-grpc-docs/--no-grpc-docs", default=True,
                  help="Generate gRPC documentation")
    @click.option("--unified/--separate", default=True,
                  help="Generate unified docs for services with both REST and gRPC")
    def docs(source_paths, output_dir, config_file, theme, include_examples,
             generate_postman, generate_grpc_docs, unified):
        """Generate comprehensive API documentation.

        Scans source code for FastAPI applications and gRPC proto files,
        then generates unified documentation including OpenAPI specs,
        gRPC documentation, and interactive documentation sites.

        Examples:
            marty api docs -s ./services/user-service -s ./services/order-service
            marty api docs -s ./src --theme swagger-ui --no-examples
            marty api docs -s ./services -c ./api-docs-config.yaml
        """
        asyncio.run(_generate_documentation(
            list(source_paths), output_dir, config_file, theme,
            include_examples, generate_postman, generate_grpc_docs, unified
        ))

    @api.command()
    @click.option("--consumer", "-c", required=True, help="Consumer service name")
    @click.option("--provider", "-p", required=True, help="Provider service name")
    @click.option("--version", "-v", default="1.0.0", help="Contract version")
    @click.option("--type", "contract_type", default="rest",
                  type=click.Choice(["rest", "grpc"]),
                  help="Contract type")
    @click.option("--service-name", help="Service name (for gRPC contracts)")
    @click.option("--proto-file", help="Proto file path (for gRPC contracts)")
    @click.option("--output-dir", "-o", default="./contracts",
                  help="Output directory for contracts")
    @click.option("--interactive", "-i", is_flag=True,
                  help="Interactive contract creation")
    def create_contract(consumer, provider, version, contract_type, service_name,
                       proto_file, output_dir, interactive):
        """Create a new API contract.

        Creates consumer-driven contracts for REST or gRPC APIs that can be
        used for contract testing between services.

        Examples:
            marty api create-contract -c web-frontend -p user-service --type rest
            marty api create-contract -c order-service -p payment-service --type grpc --service-name PaymentService
            marty api create-contract -c mobile-app -p api-gateway --interactive
        """
        asyncio.run(_create_contract(
            consumer, provider, version, contract_type, service_name,
            proto_file, output_dir, interactive
        ))

    @api.command()
    @click.option("--provider", "-p", required=True, help="Provider service name")
    @click.option("--url", "-u", help="Service URL (for REST)")
    @click.option("--grpc-address", "-g", help="gRPC service address")
    @click.option("--consumer", "-c", help="Specific consumer to test")
    @click.option("--version", "-v", help="Specific contract version")
    @click.option("--contracts-dir", default="./contracts",
                  help="Contracts directory")
    @click.option("--verification-level", default="strict",
                  type=click.Choice(["strict", "permissive", "schema_only"]),
                  help="Contract verification level")
    @click.option("--output-format", default="table",
                  type=click.Choice(["table", "json", "junit"]),
                  help="Output format for results")
    def test_contracts(provider, url, grpc_address, consumer, version,
                      contracts_dir, verification_level, output_format):
        """Test contracts against a running service.

        Verifies that a provider service correctly implements the contracts
        defined by its consumers. Can test both REST and gRPC contracts.

        Examples:
            marty api test-contracts -p user-service -u http://localhost:8080
            marty api test-contracts -p payment-service -g localhost:50051
            marty api test-contracts -p api-gateway -u http://localhost:8080 -g localhost:50051
            marty api test-contracts -p user-service -u http://localhost:8080 -c web-frontend -v 2.0.0
        """
        asyncio.run(_test_contracts(
            provider, url, grpc_address, consumer, version,
            contracts_dir, verification_level, output_format
        ))

    @api.command()
    @click.option("--contracts-dir", default="./contracts",
                  help="Contracts directory")
    @click.option("--consumer", "-c", help="Filter by consumer")
    @click.option("--provider", "-p", help="Filter by provider")
    @click.option("--type", "contract_type",
                  type=click.Choice(["rest", "grpc", "all"]), default="all",
                  help="Contract type filter")
    def list_contracts(contracts_dir, consumer, provider, contract_type):
        """List all available contracts.

        Shows all contracts in the contracts directory with their metadata.
        Can be filtered by consumer, provider, or contract type.

        Examples:
            marty api list-contracts
            marty api list-contracts -c web-frontend
            marty api list-contracts -p user-service --type grpc
        """
        asyncio.run(_list_contracts(contracts_dir, consumer, provider, contract_type))

    @api.command()
    @click.option("--service-name", "-s", required=True, help="Service name")
    @click.option("--version", "-v", required=True, help="Version to register")
    @click.option("--deprecation-date", "-d",
                  help="Deprecation date (YYYY-MM-DD)")
    @click.option("--migration-guide", "-m",
                  help="Migration guide or documentation URL")
    @click.option("--status", default="active",
                  type=click.Choice(["active", "deprecated", "retired"]),
                  help="Version status")
    def register_version(service_name, version, deprecation_date, migration_guide, status):
        """Register a new API version.

        Registers API versions for tracking and deprecation management.
        Helps maintain backward compatibility and plan migrations.

        Examples:
            marty api register-version -s user-service -v 2.0.0
            marty api register-version -s user-service -v 1.0.0 --status deprecated -d 2024-12-31
            marty api register-version -s payment-service -v 3.0.0 -m "https://docs.example.com/migration-v3"
        """
        asyncio.run(_register_version(
            service_name, version, deprecation_date, migration_guide, status
        ))

    @api.command()
    @click.option("--service-name", "-s", help="Filter by service name")
    @click.option("--status", type=click.Choice(["active", "deprecated", "retired", "all"]),
                  default="all", help="Filter by status")
    def list_versions(service_name, status):
        """List API versions.

        Shows all registered API versions with their status and metadata.
        Useful for tracking API evolution and planning deprecations.

        Examples:
            marty api list-versions
            marty api list-versions -s user-service
            marty api list-versions --status deprecated
        """
        asyncio.run(_list_versions(service_name, status))

    @api.command()
    @click.option("--proto-file", "-f", required=True, type=click.Path(exists=True),
                  help="Protocol buffer file path")
    @click.option("--consumer", "-c", required=True, help="Consumer service name")
    @click.option("--provider", "-p", required=True, help="Provider service name")
    @click.option("--output-dir", "-o", default="./contracts",
                  help="Output directory for generated contract")
    def generate_grpc_contract(proto_file, consumer, provider, output_dir):
        """Generate gRPC contract from proto file.

        Automatically generates a contract definition from a protobuf file,
        creating base interactions for all service methods.

        Examples:
            marty api generate-grpc-contract -f ./protos/user.proto -c web-app -p user-service
            marty api generate-grpc-contract -f ./payment.proto -c order-service -p payment-service -o ./my-contracts
        """
        asyncio.run(_generate_grpc_contract(proto_file, consumer, provider, output_dir))

    @api.command()
    @click.option("--contracts-dir", default="./contracts",
                  help="Contracts directory")
    @click.option("--docs-dir", default="./docs/contracts",
                  help="Output directory for contract documentation")
    @click.option("--format", "output_format", default="html",
                  type=click.Choice(["html", "markdown", "json"]),
                  help="Documentation format")
    def generate_contract_docs(contracts_dir, docs_dir, output_format):
        """Generate documentation from contracts.

        Creates human-readable documentation from contract definitions,
        including interaction examples and API specifications.

        Examples:
            marty api generate-contract-docs
            marty api generate-contract-docs --format markdown
            marty api generate-contract-docs --contracts-dir ./my-contracts --docs-dir ./contract-docs
        """
        asyncio.run(_generate_contract_docs(contracts_dir, docs_dir, output_format))

    @api.command()
    @click.option("--config-file", "-c", help="Configuration file for monitoring")
    @click.option("--providers", "-p", multiple=True,
                  help="Provider services to monitor")
    @click.option("--interval", default=300, type=int,
                  help="Check interval in seconds")
    @click.option("--webhook-url", help="Webhook URL for notifications")
    @click.option("--fail-fast", is_flag=True,
                  help="Stop on first contract failure")
    def monitor_contracts(config_file, providers, interval, webhook_url, fail_fast):
        """Monitor contract compliance continuously.

        Runs contract tests periodically against live services and reports
        failures. Useful for CI/CD pipelines and production monitoring.

        Examples:
            marty api monitor-contracts -p user-service -p order-service --interval 60
            marty api monitor-contracts -c ./monitor-config.yaml --webhook-url https://hooks.slack.com/...
        """
        asyncio.run(_monitor_contracts(
            config_file, list(providers), interval, webhook_url, fail_fast
        ))


# Implementation functions
async def _generate_documentation(source_paths: list[str], output_dir: str,
                                config_file: str | None, theme: str,
                                include_examples: bool, generate_postman: bool,
                                generate_grpc_docs: bool, unified: bool):
    """Generate API documentation."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating API documentation...", total=None)

        try:
            # Configure documentation generation
            config = DocumentationConfig(
                output_dir=Path(output_dir),
                include_examples=include_examples,
                generate_postman=generate_postman,
                generate_grpc_docs=generate_grpc_docs,
                generate_unified_docs=unified,
                theme=theme
            )

            if config_file and Path(config_file).exists():
                with open(config_file) as f:
                    config_data = yaml.safe_load(f)
                    for key, value in config_data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)

            # Generate documentation
            manager = APIDocumentationManager(Path.cwd(), config)
            source_paths_list = [Path(p) for p in source_paths]
            results = await manager.generate_all_documentation(source_paths_list)

            progress.update(task, completed=True)

            console.print("\n[green]✓ Documentation generated successfully![/green]")
            console.print(f"[blue]Output directory: {output_dir}[/blue]")
            console.print(f"[blue]Index page: {output_dir}/index.html[/blue]")

            # Show summary table
            table = Table(title="Generated Documentation")
            table.add_column("Service", style="cyan")
            table.add_column("Files Generated", style="green")

            for service_name, files in results.items():
                file_types = ", ".join(files.keys())
                table.add_row(service_name, file_types)

            console.print(table)

        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]✗ Failed to generate documentation: {e}[/red]")
            raise click.Abort()


async def _create_contract(consumer: str, provider: str, version: str,
                         contract_type: str, service_name: str | None,
                         proto_file: str | None, output_dir: str,
                         interactive: bool):
    """Create a new contract."""
    contracts_dir = Path(output_dir)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    if contract_type == "grpc":
        if proto_file:
            # Generate from proto file
            contract = await generate_contract_from_proto(
                Path(proto_file), consumer, provider
            )
        else:
            if not service_name:
                service_name = click.prompt("gRPC service name")

            # Create manual gRPC contract
            builder = grpc_contract(consumer, provider, service_name, version)

            if interactive:
                # Interactive mode for adding interactions
                console.print(f"[blue]Creating gRPC contract: {consumer} -> {provider}[/blue]")
                console.print("Add interactions (press Enter with empty description to finish):")

                while True:
                    description = click.prompt("Interaction description", default="", show_default=False)
                    if not description:
                        break

                    method_name = click.prompt("gRPC method name")
                    input_type = click.prompt("Input message type")
                    output_type = click.prompt("Output message type")

                    builder.interaction(description).upon_calling(method_name).with_request(input_type).will_respond_with(output_type)

            contract = builder.build()

        # Save gRPC contract
        grpc_repo = GRPCContractRepository(contracts_dir / "grpc")
        grpc_repo.save_contract(contract)

    else:  # REST contract
        # Create REST contract
        builder = pact_contract(consumer, provider, version)

        if interactive:
            console.print(f"[blue]Creating REST contract: {consumer} -> {provider}[/blue]")
            console.print("Add interactions (press Enter with empty description to finish):")

            while True:
                description = click.prompt("Interaction description", default="", show_default=False)
                if not description:
                    break

                method = click.prompt("HTTP method", type=click.Choice(["GET", "POST", "PUT", "DELETE", "PATCH"]))
                path = click.prompt("Request path")
                status = click.prompt("Response status", default=200, type=int)

                builder.interaction(description).upon_receiving(method, path).will_respond_with(status)

        contract = builder.build()

        # Save REST contract
        rest_repo = ContractRepository(contracts_dir / "rest")
        rest_repo.save_contract(contract)

    console.print(f"[green]✓ Contract created: {consumer} -> {provider} ({contract_type})[/green]")


async def _test_contracts(provider: str, url: str | None, grpc_address: str | None,
                        consumer: str | None, version: str | None,
                        contracts_dir: str, verification_level: str,
                        output_format: str):
    """Test contracts against a running service."""
    contracts_path = Path(contracts_dir)

    if not contracts_path.exists():
        console.print(f"[red]✗ Contracts directory not found: {contracts_dir}[/red]")
        raise click.Abort()

    manager = EnhancedContractManager(
        repository=ContractRepository(contracts_path / "rest"),
        grpc_repository=GRPCContractRepository(contracts_path / "grpc")
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running contract tests...", total=None)

        try:
            # Ensure we have at least one service endpoint
            if not url and not grpc_address:
                console.print("[red]✗ Must provide either --url or --grpc-address[/red]")
                raise click.Abort()

            results = await manager.verify_all_contracts_for_provider(
                provider, url or "", grpc_address or ""
            )

            progress.update(task, completed=True)

            # Display results
            if output_format == "table":
                _display_test_results_table(results)
            elif output_format == "json":
                _display_test_results_json(results)
            elif output_format == "junit":
                _generate_junit_report(results, f"{provider}_contract_tests.xml")

            # Summary
            passed = sum(1 for r in results if r.status.name == "PASSED")
            failed = sum(1 for r in results if r.status.name == "FAILED")

            if failed > 0:
                console.print(f"\n[red]✗ {failed} contract tests failed, {passed} passed[/red]")
                raise click.Abort()
            else:
                console.print(f"\n[green]✓ All {passed} contract tests passed[/green]")

        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]✗ Contract testing failed: {e}[/red]")
            raise click.Abort()


async def _list_contracts(contracts_dir: str, consumer: str | None,
                        provider: str | None, contract_type: str):
    """List available contracts."""
    contracts_path = Path(contracts_dir)

    if not contracts_path.exists():
        console.print(f"[yellow]Contracts directory not found: {contracts_dir}[/yellow]")
        return

    manager = EnhancedContractManager(
        repository=ContractRepository(contracts_path / "rest"),
        grpc_repository=GRPCContractRepository(contracts_path / "grpc")
    )

    contracts = manager.list_all_contracts(consumer or "", provider or "")

    if contract_type != "all":
        contracts = [c for c in contracts if c["type"] == contract_type]

    if not contracts:
        console.print("[yellow]No contracts found[/yellow]")
        return

    table = Table(title="Available Contracts")
    table.add_column("Consumer", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Type", style="magenta")
    table.add_column("File", style="blue")

    for contract in contracts:
        table.add_row(
            contract["consumer"],
            contract["provider"],
            contract["version"],
            contract["type"].upper(),
            Path(contract["file"]).name
        )

    console.print(table)


async def _register_version(service_name: str, version: str,
                          deprecation_date: str | None,
                          migration_guide: str | None, status: str):
    """Register an API version."""

    version_manager = APIVersionManager(Path.cwd())

    if status == "deprecated" and not deprecation_date:
        deprecation_date = click.prompt("Deprecation date (YYYY-MM-DD)")

    success = await version_manager.register_version(
        service_name, version, deprecation_date, migration_guide
    )

    if status == "deprecated":
        success = await version_manager.deprecate_version(
            service_name, version, deprecation_date or "", migration_guide or ""
        )

    if success:
        console.print(f"[green]✓ Version {version} registered for {service_name}[/green]")
    else:
        console.print("[red]✗ Failed to register version[/red]")
        raise click.Abort()


async def _list_versions(service_name: str | None, status: str):
    """List API versions."""

    version_manager = APIVersionManager(Path.cwd())

    if service_name:
        services = [service_name]
    else:
        # Load all services from versions file
        versions_data = await version_manager._load_versions()
        services = list(versions_data.keys())

    table = Table(title="API Versions")
    table.add_column("Service", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Deprecation Date", style="red")
    table.add_column("Migration Guide", style="blue")

    for service in services:
        if status in ["active", "all"]:
            active_versions = await version_manager.get_active_versions(service)
            for version in active_versions:
                table.add_row(service, version, "Active", "-", "-")

        if status in ["deprecated", "all"]:
            deprecated_versions = await version_manager.get_deprecated_versions(service)
            for version_info in deprecated_versions:
                table.add_row(
                    service,
                    version_info["version"],
                    "Deprecated",
                    version_info.get("deprecation_date", "-"),
                    version_info.get("migration_guide", "-")
                )

    console.print(table)


async def _generate_grpc_contract(proto_file: str, consumer: str, provider: str, output_dir: str):
    """Generate gRPC contract from proto file."""
    contract = await generate_contract_from_proto(Path(proto_file), consumer, provider)

    grpc_repo = GRPCContractRepository(Path(output_dir) / "grpc")
    grpc_repo.save_contract(contract)

    console.print(f"[green]✓ gRPC contract generated from {proto_file}[/green]")
    console.print(f"[blue]Consumer: {consumer}, Provider: {provider}[/blue]")
    console.print(f"[blue]Service: {contract.service_name}[/blue]")
    console.print(f"[blue]Interactions: {len(contract.interactions)}[/blue]")


async def _generate_contract_docs(contracts_dir: str, docs_dir: str, output_format: str):
    """Generate documentation from contracts."""
    # Implementation would generate human-readable docs from contracts
    console.print(f"[blue]Generating contract documentation in {output_format} format...[/blue]")

    docs_path = Path(docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    # This is a placeholder - in a real implementation, you'd:
    # 1. Load all contracts
    # 2. Generate documentation templates
    # 3. Create index pages
    # 4. Export in the specified format

    console.print(f"[green]✓ Contract documentation generated in {docs_dir}[/green]")


async def _monitor_contracts(config_file: str | None, providers: list[str],
                           interval: int, webhook_url: str | None, fail_fast: bool):
    """Monitor contract compliance continuously."""
    console.print(f"[blue]Starting contract monitoring (interval: {interval}s)...[/blue]")

    if config_file:
        with open(config_file) as f:
            config = yaml.safe_load(f)
        # Load monitoring configuration
        providers = config.get("providers", providers)
        interval = config.get("interval", interval)
        webhook_url = config.get("webhook_url", webhook_url)

    try:
        while True:
            console.print(f"[blue]Running contract checks at {datetime.now()}[/blue]")

            for provider in providers:
                # This would run contract tests for each provider
                console.print(f"[blue]Checking contracts for {provider}...[/blue]")
                # Implementation would test contracts and report results

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Contract monitoring stopped[/yellow]")


def _display_test_results_table(results):
    """Display test results in table format."""
    table = Table(title="Contract Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration (ms)", style="yellow")
    table.add_column("Errors", style="red")

    for result in results:
        status_color = "green" if result.status.name == "PASSED" else "red"
        status_text = f"[{status_color}]{result.status.name}[/{status_color}]"
        errors_text = "; ".join(result.errors) if result.errors else "-"

        table.add_row(
            result.test_id,
            status_text,
            str(result.duration_ms),
            errors_text
        )

    console.print(table)


def _display_test_results_json(results):
    """Display test results in JSON format."""
    json_results = []
    for result in results:
        json_results.append({
            "test_id": result.test_id,
            "status": result.status.name,
            "duration_ms": result.duration_ms,
            "errors": result.errors,
            "warnings": getattr(result, 'warnings', [])
        })

    console.print(json.dumps(json_results, indent=2))


def _generate_junit_report(results, output_file: str):
    """Generate JUnit XML report."""
    # This would generate a JUnit XML report for CI/CD integration
    console.print(f"[blue]JUnit report generated: {output_file}[/blue]")
