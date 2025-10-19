"""
CLI module for the Marty Dashboard.
"""

import asyncio
import sys

import click
import uvicorn

from .database import create_tables
from .services.discovery import ServiceDiscoveryService, ServiceInfo


@click.group()
@click.version_option(version="1.0.0", prog_name="marty-dashboard")
def main():
    """Marty Dashboard - Management interface for Marty Microservices Framework."""


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--workers", default=1, help="Number of worker processes")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--log-level", default="info", help="Log level")
def serve(host: str, port: int, workers: int, reload: bool, log_level: str):
    """Start the dashboard server."""
    uvicorn.run(
        "marty_dashboard.main:app",
        host=host,
        port=port,
        workers=workers if not reload else 1,
        reload=reload,
        log_level=log_level,
    )


@main.command()
def init():
    """Initialize the dashboard database."""
    click.echo("Initializing database...")

    async def init_db():

        await create_tables()
        click.echo("Database initialized successfully!")

    asyncio.run(init_db())


@main.command()
@click.argument("service_name")
@click.argument("address")
@click.argument("port", type=int)
@click.option("--health-url", help="Health check URL")
@click.option("--tags", help="Comma-separated tags")
def register(
    service_name: str,
    address: str,
    port: int,
    health_url: str | None,
    tags: str | None,
):
    """Register a service with the dashboard."""

    async def register_service():

        service_discovery = ServiceDiscoveryService()
        await service_discovery.start()

        service_tags = tags.split(",") if tags else []
        service_info = ServiceInfo(
            name=service_name,
            address=address,
            port=port,
            health_check_url=health_url,
            tags=service_tags,
        )

        success = await service_discovery.register_service(service_info)
        if success:
            click.echo(f"Service {service_name} registered successfully!")
        else:
            click.echo(f"Failed to register service {service_name}")
            sys.exit(1)

        await service_discovery.stop()

    asyncio.run(register_service())


@main.command()
@click.argument("service_name")
def deregister(service_name: str):
    """Deregister a service from the dashboard."""

    async def deregister_service():

        service_discovery = ServiceDiscoveryService()
        await service_discovery.start()

        success = await service_discovery.deregister_service(service_name)
        if success:
            click.echo(f"Service {service_name} deregistered successfully!")
        else:
            click.echo(f"Failed to deregister service {service_name}")
            sys.exit(1)

        await service_discovery.stop()

    asyncio.run(deregister_service())


@main.command()
def list_services():
    """List all registered services."""

    async def list_all_services():

        service_discovery = ServiceDiscoveryService()
        await service_discovery.start()

        services = await service_discovery.get_services()

        if not services:
            click.echo("No services registered.")
        else:
            click.echo("Registered services:")
            for service in services:
                click.echo(
                    f"  - {service.name} ({service.address}:{service.port}) - {service.status}"
                )

        await service_discovery.stop()

    asyncio.run(list_all_services())


if __name__ == "__main__":
    main()
