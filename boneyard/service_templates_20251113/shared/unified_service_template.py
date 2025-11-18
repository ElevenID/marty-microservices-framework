"""
Modern Marty Microservice Template with Unified Configuration

This template demonstrates how to create new services using the unified configuration system.

Usage:
1. Copy this file to your service directory
2. Replace ExampleService with your actual service name
3. Update the configuration model for your service needs
4. Implement your service-specific business logic

This template demonstrates:
- Unified configuration loading with cloud-agnostic secret management
- Automatic environment detection
- Type-safe configuration with Pydantic models
- Secret references with ${SECRET:key} syntax
- Configuration hot-reloading
- Proper logging and monitoring setup
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from marty_msf.framework.config import (
    ConfigurationStrategy,
    Environment,
    UnifiedConfigurationManager,
    create_unified_config_manager,
)
from marty_msf.framework.database import DatabaseManager, create_database_manager
from marty_msf.framework.database.config import ConnectionPoolConfig, DatabaseConfig
from marty_msf.framework.grpc.unified_grpc_server import UnifiedGrpcServer
from marty_msf.observability.monitoring import MonitoringManager, initialize_monitoring


# Define service configuration model
class ExampleServiceConfig(BaseModel):
    """Configuration model for Example service."""
    service_name: str = Field(default="example-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)

    # Database configuration with secret reference
    database_url: str = Field(default="${SECRET:database_url}")
    database_pool_size: int = Field(default=10)
    database_enabled: bool = Field(default=False)

    # Security configuration with secret references
    jwt_secret: str = Field(default="${SECRET:jwt_secret}")
    api_key: str = Field(default="${SECRET:api_key}")

    # Service-specific settings
    max_concurrent_operations: int = Field(default=100)
    operation_timeout: int = Field(default=30)
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)

    # Monitoring configuration
    prometheus_enabled: bool = Field(default=True)
    jaeger_endpoint: str | None = Field(default=None)


class ModernExampleService:
    """
    Modern Example service using unified configuration management.

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
        Initialize the Example service with unified configuration.

        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (development, testing, staging, production)
        """
        self.logger = logging.getLogger("marty.example")

        # Create unified configuration manager
        self.config_manager = create_unified_config_manager(
            service_name="example-service",
            environment=Environment(environment),
            config_class=ExampleServiceConfig,
            config_dir=config_dir,
            strategy=ConfigurationStrategy.AUTO_DETECT
        )

        # Configuration will be loaded in start() method
        self.config: ExampleServiceConfig | None = None

        # Initialize components
        self.db_manager: DatabaseManager | None = None
        self.grpc_server: UnifiedGrpcServer | None = None
        self.metrics_server: MonitoringManager | None = None
        self._running = False

        self.logger.info("Example service initialized with unified configuration")

    async def start(self) -> None:
        """Start the Example service."""
        if self._running:
            self.logger.warning("Service is already running")
            return

        try:
            self.logger.info("Starting Example service...")

            # Initialize configuration manager and load configuration
            await self.config_manager.initialize()
            self.config = await self.config_manager.get_configuration()

            self.logger.info(f"Configuration loaded for {self.config.service_name}")

            # Initialize database connection
            await self._init_database()

            # Initialize security components
            await self._init_security()

            # Start gRPC server (if applicable)
            await self._start_grpc_server()

            # Start metrics server
            await self._start_metrics_server()

            self._running = True
            self.logger.info("Example service started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Example service: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the Example service."""
        if not self._running:
            return

        try:
            self.logger.info("Stopping Example service...")

            # Stop gRPC server
            if self.grpc_server:
                await self.grpc_server.stop()
                self.logger.info("gRPC server stopped")

            # Stop metrics server
            if self.metrics_server:
                # MonitoringManager cleanup is handled automatically
                self.logger.info("Metrics server stopped")

            # Close database connections
            if self.db_manager:
                await self.db_manager.close()
                self.logger.info("Database connections closed")

            self._running = False
            self.logger.info("Example service stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping Example service: {e}")

    async def _init_database(self) -> None:
        """Initialize database connection."""
        if not self.config:
            raise RuntimeError("Configuration not loaded")

        if not self.config.database_enabled:
            self.logger.info("Database disabled in configuration")
            return

        try:
            # Parse database URL to extract connection details
            # For simplicity, assume PostgreSQL URL format: postgresql://user:pass@host:port/db


            parsed = urlparse(self.config.database_url)

            # Create pool configuration
            pool_config = ConnectionPoolConfig(
                max_size=self.config.database_pool_size,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False,
                echo_pool=False
            )

            # Create database configuration
            db_config = DatabaseConfig(
                service_name=self.config.service_name,
                host=parsed.hostname or 'localhost',
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/') if parsed.path else 'postgres',
                username=parsed.username or 'postgres',
                password=parsed.password or '',
                pool_config=pool_config
            )

            self.db_manager = create_database_manager(db_config)
            await self.db_manager.initialize()

            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    async def _init_security(self) -> None:
        """Initialize security components."""
        if not self.config:
            raise RuntimeError("Configuration not loaded")

        try:
            # Security initialization logic here
            # Use self.config.jwt_secret and self.config.api_key
            self.logger.info("Security components initialized")
        except Exception as e:
            self.logger.error(f"Security initialization failed: {e}")
            raise

    async def _start_grpc_server(self) -> None:
        """Start gRPC server."""
        if not self.config:
            raise RuntimeError("Configuration not loaded")

        try:
            # Create unified gRPC server with configuration
            self.grpc_server = UnifiedGrpcServer(
                service_name=self.config.service_name
            )

            # Add service implementations here
            # Example: self.grpc_server.add_servicer(
            #     ExampleServicer(self),
            #     add_ExampleServicer_to_server
            # )

            await self.grpc_server.start()
            self.logger.info("gRPC server started successfully")
        except Exception as e:
            self.logger.error(f"gRPC server startup failed: {e}")
            raise

    async def _start_metrics_server(self) -> None:
        """Start metrics server."""
        if not self.config or not self.config.enable_metrics:
            return

        try:
            self.metrics_server = initialize_monitoring(
                service_name=self.config.service_name,
                use_prometheus=self.config.prometheus_enabled,
                jaeger_endpoint=self.config.jaeger_endpoint
            )

            self.logger.info("Metrics server initialized successfully")
        except Exception as e:
            self.logger.error(f"Metrics server startup failed: {e}")
            raise

    async def health_check(self) -> dict:
        """Perform health check on all components."""
        health = {
            'service': self.config.service_name if self.config else 'unknown',
            'status': 'healthy',
            'timestamp': time.time(),
            'components': {}
        }

        # Check database health
        if self.db_manager:
            try:
                db_health = await self.db_manager.health_check()
                health['components']['database'] = 'healthy' if db_health.get('status') == 'healthy' else 'unhealthy'
            except Exception as e:
                health['components']['database'] = f'unhealthy: {e}'

        # Check gRPC server health
        if self.grpc_server:
            health['components']['grpc'] = 'healthy'

        # Check metrics health
        if self.metrics_server:
            try:
                metrics_health = await self.metrics_server.get_service_health()
                health['components']['metrics'] = metrics_health.get('status', 'healthy')
            except Exception as e:
                health['components']['metrics'] = f'unhealthy: {e}'

        return health

    async def reload_configuration(self) -> None:
        """Reload configuration from the unified configuration manager."""
        try:
            old_config = self.config
            self.config = await self.config_manager.get_configuration(reload=True)
            self.logger.info("Configuration reloaded successfully")

            # Optionally handle configuration changes here
            if old_config and old_config != self.config:
                self.logger.info("Configuration changes detected, applying updates...")
                # Handle specific configuration changes

        except Exception as e:
            self.logger.error(f"Configuration reload failed: {e}")
            raise

    # Business logic methods
    async def process_example_operation(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Process an example operation.

        This demonstrates how to implement business logic with proper
        configuration access, error handling, and monitoring.
        """
        if not self._running:
            raise RuntimeError("Service is not running")

        try:
            # Process the operation
            result = {
                "status": "success",
                "data": request,
                "service": self.config.service_name if self.config else "unknown",
                "processed_at": asyncio.get_event_loop().time()
            }

            # Publish success event if event publishing is configured
            await self._publish_event("example.operation.completed", result)

            return result

        except Exception as e:
            self.logger.error(f"Operation processing failed: {e}")

            # Publish error event
            await self._publish_event("example.error.occurred", {
                "error": str(e),
                "request": request,
                "service": self.config.service_name if self.config else "unknown"
            })

            raise

    async def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event (placeholder implementation)."""
        # Event publishing logic would go here
        self.logger.debug(f"Event published: {event_type}")


@asynccontextmanager
async def create_example_service(config_dir: str = "config", environment: str = "development"):
    """
    Context manager for creating and managing the Example service lifecycle.

    This is the recommended way to use the service in applications.
    """
    service = ModernExampleService(config_dir, environment)

    try:
        await service.start()
        yield service
    finally:
        await service.stop()


# Example usage
async def main():
    """Example of how to use the modern service."""
    async with create_example_service() as service:
        # Perform health check
        health = await service.health_check()
        print(f"Service health: {health}")

        # Process an example operation
        result = await service.process_example_operation({"test": "data"})
        print(f"Operation result: {result}")

        # Reload configuration
        await service.reload_configuration()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
