"""
Modern Marty Microservice Template

Copy this template to create new services that use the unified configuration system.

Usage:
1. Copy this file to src/services/{your_service_name}/modern_{your_service_name}.py
2. Replace {{SERVICE_NAME}} with your service name
3. Copy and modify the config template for your service
4. Implement your service-specific business logic

This template demonstrates all configuration patterns and best practices.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from marty_msf.framework.config import (
    ConfigurationStrategy,
    Environment,
    UnifiedConfigurationManager,
    create_unified_config_manager,
)


# Define service configuration model
class SERVICE_NAME_PASCAL_ServiceConfig(BaseModel):
    """Configuration model for SERVICE_NAME service."""
    service_name: str = Field(default="SERVICE_NAME-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)

    # Database configuration
    database_url: str = Field(default="${SECRET:database_url}")
    database_pool_size: int = Field(default=10)

    # Security configuration
    jwt_secret: str = Field(default="${SECRET:jwt_secret}")
    api_key: str = Field(default="${SECRET:api_key}")

    # Service-specific settings
    max_concurrent_operations: int = Field(default=100)
    operation_timeout: int = Field(default=30)
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)


class ModernSERVICE_NAME_PASCAL:
    """
    Modern {{SERVICE_NAME}} service using unified configuration management.

    This template demonstrates:
    - Unified configuration loading with cloud-agnostic secret management
    - Automatic environment detection
    - Type-safe configuration with Pydantic models
    - Secret references with ${SECRET:key} syntax
    - Configuration hot-reloading
    - Proper logging and monitoring setup
    """

    def __init__(self, config_dir: str = "config", environment: str = "development"):
        """
        Initialize the {{SERVICE_NAME}} service with unified configuration.

        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (development, testing, staging, production)
        """
        self.logger = logging.getLogger("marty.SERVICE_NAME")

        # Create unified configuration manager
        self.config_manager = create_unified_config_manager(
            service_name="SERVICE_NAME-service",
            environment=Environment(environment),
            config_class=SERVICE_NAME_PASCAL_ServiceConfig,
            config_dir=config_dir,
            strategy=ConfigurationStrategy.AUTO_DETECT
        )

        # Configuration will be loaded in start() method
        self.config: SERVICE_NAME_PASCAL_ServiceConfig | None = None

        # Initialize components
        self.db_pool = None
        self.grpc_server = None
        self.metrics_server = None
        self._running = False

        self.logger.info("SERVICE_NAME service initialized with unified configuration")

    async def start(self) -> None:
        """Start the SERVICE_NAME service."""
        if self._running:
            self.logger.warning("Service is already running")
            return

        try:
            self.logger.info("Starting SERVICE_NAME service...")

            # Initialize database connection
            await self._init_database()

            # Initialize security components
            await self._init_security()

            # Initialize cryptographic components (if configured)
            if self.crypto_config:
                await self._init_cryptographic()

            # Initialize trust store (if configured)
            if self.trust_store_config:
                await self._init_trust_store()

            # Start gRPC server
            await self._start_grpc_server()

            # Start metrics server
            await self._start_metrics_server()

            # Start background tasks
            await self._start_background_tasks()

            self._running = True
            self.logger.info("SERVICE_NAME service started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start SERVICE_NAME service: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the SERVICE_NAME service."""
        if not self._running:
            return

        self.logger.info("Stopping SERVICE_NAME service...")

        try:
            # Stop background tasks
            await self._stop_background_tasks()

            # Stop servers
            if self.grpc_server:
                await self.grpc_server.stop(grace=30)

            if self.metrics_server:
                await self.metrics_server.stop()

            # Close database connections
            if self.db_pool:
                await self.db_pool.close()

            self._running = False
            self.logger.info("SERVICE_NAME service stopped")

        except Exception as e:
            self.logger.error(f"Error stopping SERVICE_NAME service: {e}")

    async def _init_database(self) -> None:
        """Initialize database connection pool."""
        if not self.db_config:
            self.logger.warning("No database configuration found")
            return

        self.logger.info("Initializing database connection...")

        # Example database initialization (adapt to your database library)
        # self.db_pool = await create_pool(
        #     host=self.db_config.host,
        #     port=self.db_config.port,
        #     database=self.db_config.database,
        #     user=self.db_config.username,
        #     password=self.db_config.password,
        #     minsize=1,
        #     maxsize=self.db_config.pool_size,
        #     ssl=self.db_config.ssl_mode != "disable"
        # )

        self.logger.info(f"Database connection initialized for {self.db_config.database}")

    async def _init_security(self) -> None:
        """Initialize security components."""
        if not self.security_config:
            self.logger.warning("No security configuration found")
            return

        self.logger.info("Initializing security components...")

        # Initialize TLS certificates if gRPC TLS is enabled
        if self.security_config.grpc_tls and self.security_config.grpc_tls.enabled:
            self.logger.info("gRPC TLS enabled")
            # Load TLS certificates
            # self.server_credentials = grpc.ssl_server_credentials(...)

        # Initialize authentication if enabled
        if self.security_config.auth and self.security_config.auth.required:
            self.logger.info("Authentication enabled")
            # Initialize JWT validation, API key checking, etc.

        # Initialize authorization if enabled
        if self.security_config.authz and self.security_config.authz.enabled:
            self.logger.info("Authorization enabled")
            # Load authorization policies

        self.logger.info("Security components initialized")

    async def _init_cryptographic(self) -> None:
        """Initialize cryptographic components."""
        if not self.crypto_config:
            return

        self.logger.info("Initializing cryptographic components...")

        # Initialize signing configuration
        if self.crypto_config.signing:
            self.logger.info(f"Signing algorithm: {self.crypto_config.signing.algorithm}")
            # Load signing keys

        # Initialize vault connection
        if self.crypto_config.vault:
            self.logger.info(f"Vault URL: {self.crypto_config.vault.url}")
            # Initialize vault client

        self.logger.info("Cryptographic components initialized")

    async def _init_trust_store(self) -> None:
        """Initialize trust store components."""
        if not self.trust_store_config:
            return

        self.logger.info("Initializing trust store...")

        # Initialize trust anchor
        if self.trust_store_config.trust_anchor:
            cert_store_path = self.trust_store_config.trust_anchor.certificate_store_path
            self.logger.info(f"Trust anchor certificate store: {cert_store_path}")
            # Load trust anchor certificates

        # Initialize PKD connection
        if self.trust_store_config.pkd and self.trust_store_config.pkd.enabled:
            pkd_url = self.trust_store_config.pkd.service_url
            self.logger.info(f"PKD service URL: {pkd_url}")
            # Initialize PKD client

        self.logger.info("Trust store initialized")

    async def _start_grpc_server(self) -> None:
        """Start the gRPC server."""
        self.logger.info("Starting gRPC server...")

        # Example gRPC server setup (adapt to your service)
        # self.grpc_server = grpc.aio.server()
        # add_{{SERVICE_NAME}}_servicer_to_server({{SERVICE_NAME}}Servicer(self), self.grpc_server)
        #
        # listen_addr = f"[::]:{self.service_discovery.ports.get('{{SERVICE_NAME}}', 8080)}"
        # self.grpc_server.add_insecure_port(listen_addr)
        #
        # await self.grpc_server.start()
        # self.logger.info(f"gRPC server listening on {listen_addr}")

    async def _start_metrics_server(self) -> None:
        """Start the metrics server for monitoring."""
        if not self.config.monitoring or not self.config.monitoring.enabled:
            return

        self.logger.info("Starting metrics server...")

        # Example metrics server setup
        # from prometheus_client import start_http_server
        # start_http_server(self.config.monitoring.metrics_port)
        # self.logger.info(f"Metrics server listening on port {self.config.monitoring.metrics_port}")

    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        self.logger.info("Starting background tasks...")

        # Example background tasks
        if self.trust_store_config and self.trust_store_config.trust_anchor:
            # Start trust store update task
            asyncio.create_task(self._trust_store_update_task())

        if self.service_settings.get("enable_event_publishing", False):
            # Start event publishing task
            asyncio.create_task(self._event_publishing_task())

    async def _stop_background_tasks(self) -> None:
        """Stop background tasks."""
        self.logger.info("Stopping background tasks...")
        # Cancel and cleanup background tasks

    async def _trust_store_update_task(self) -> None:
        """Background task to update trust store."""
        while self._running:
            try:
                self.logger.debug("Updating trust store...")
                # Update trust store logic
                await asyncio.sleep(self.trust_store_config.trust_anchor.update_interval_hours * 3600)
            except Exception as e:
                self.logger.error(f"Trust store update error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _event_publishing_task(self) -> None:
        """Background task for event publishing."""
        while self._running:
            try:
                # Event publishing logic
                await asyncio.sleep(60)  # Publish events every minute
            except Exception as e:
                self.logger.error(f"Event publishing error: {e}")
                await asyncio.sleep(60)

    # Service-specific business logic methods
    async def process_SERVICE_NAME_operation(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Process a {{SERVICE_NAME}} operation.

        This is where you implement your service-specific business logic.
        """
        try:
            self.logger.info(f"Processing {{SERVICE_NAME}} operation: {request.get('operation_id', 'unknown')}")

            # Implement your business logic here
            result = {
                "status": "success",
                "operation_id": request.get("operation_id"),
                "result": "{{SERVICE_NAME}} operation completed"
            }

            # Publish event if enabled
            if self.service_settings.get("enable_event_publishing", False):
                await self._publish_event("{{SERVICE_NAME}}.operation.completed", result)

            return result

        except Exception as e:
            self.logger.error(f"{{SERVICE_NAME}} operation failed: {e}")

            # Publish error event if enabled
            if self.service_settings.get("enable_event_publishing", False):
                await self._publish_event("{{SERVICE_NAME}}.error.occurred", {
                    "operation_id": request.get("operation_id"),
                    "error": str(e)
                })

            raise

    async def _publish_event(self, topic: str, event_data: dict[str, Any]) -> None:
        """Publish an event to the configured event system."""
        self.logger.debug(f"Publishing event to {topic}: {event_data}")
        # Implement event publishing logic

    @asynccontextmanager
    async def get_database_connection(self):
        """Get a database connection from the pool."""
        if not self.db_pool:
            raise RuntimeError("Database not initialized")

        # Example connection management (adapt to your database library)
        # async with self.db_pool.acquire() as conn:
        #     yield conn
        yield None  # Placeholder

    def get_service_host(self, service_name: str) -> str:
        """Get the host for a service from service discovery."""
        return self.service_discovery.hosts.get(service_name, f"{service_name}-service")

    def get_service_port(self, service_name: str) -> int:
        """Get the port for a service from service discovery."""
        return self.service_discovery.ports.get(service_name, 8080)

    def get_service_endpoint(self, service_name: str) -> str:
        """Get the full endpoint for a service."""
        host = self.get_service_host(service_name)
        port = self.get_service_port(service_name)
        return f"{host}:{port}"


# Example usage and main function
async def main():
    """Main function to run the {{SERVICE_NAME}} service."""

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create service instance
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/services/{{SERVICE_NAME}}.yaml"
    service = ModernSERVICE_NAME_PASCAL(config_path)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        asyncio.create_task(service.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start the service
        await service.start()

        # Keep the service running
        while service._running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
