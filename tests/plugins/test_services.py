"""
Service Plugin Tests

Tests for plugin service management including:
- Service definition and registration
- Service lifecycle and routing
- Service discovery mechanisms
- Plugin service integration
"""

import asyncio

# Fix import path
import sys
from pathlib import Path
from typing import Any

import pytest

from marty_msf.framework.plugins.core import PluginContext
from marty_msf.framework.plugins.services import (
    PluginService,
    ServiceDefinition,
    ServiceRegistry,
)

framework_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(framework_path))



class TestService(PluginService):
    """Shared test service class for all tests."""

    def __init__(self, context: PluginContext = None):
        super().__init__(context)
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy" if self.started else "stopped", "service": "test-service"}

    async def handle_request(self, path: str, method: str, **kwargs) -> dict[str, Any]:
        if path == "/test" and method == "GET":
            return {"message": "Test endpoint", "status": "ok"}
        return {"error": "Not found", "status": 404}


class TestServiceDefinition:
    """Test service definition functionality."""

    def test_create_service_definition(self):
        """Test creation of service definition."""
        service_def = ServiceDefinition(
            name="test-service",
            version="1.0.0",
            description="Test service for unit testing",
            routes={
                "/health": {"methods": ["GET"], "handler": "health_check"},
                "/api/v1/data": {"methods": ["GET", "POST"], "handler": "data_handler"},
            },
            dependencies=["database", "cache"],
            health_check_path="/health",
        )

        assert service_def.name == "test-service"
        assert service_def.version == "1.0.0"
        assert service_def.description == "Test service for unit testing"
        assert "/health" in service_def.routes
        assert "/api/v1/data" in service_def.routes
        assert "database" in service_def.dependencies
        assert service_def.health_check_path == "/health"

    def test_service_definition_defaults(self):
        """Test service definition with default values."""
        service_def = ServiceDefinition(name="minimal-service", version="1.0.0")

        assert service_def.name == "minimal-service"
        assert service_def.version == "1.0.0"
        assert service_def.description == ""
        assert service_def.routes == {}
        assert service_def.dependencies == []
        assert service_def.health_check_path == "/health"


class TestPluginService:
    """Test plugin service base class functionality."""

    class TestService(PluginService):
        def __init__(self):
            super().__init__()
            self.started = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.started = False

        async def health_check(self) -> dict[str, Any]:
            return {"status": "healthy" if self.started else "stopped", "service": "test-service"}

        async def handle_request(self, path: str, method: str, **kwargs) -> dict[str, Any]:
            if path == "/test" and method == "GET":
                return {"message": "Test endpoint", "status": "ok"}
            return {"error": "Not found", "status": 404}

    @pytest.mark.asyncio
    async def test_service_lifecycle(self, mock_context):
        """Test service lifecycle management."""
        service = self.TestService()
        assert not service.started

        await service.initialize(mock_context)
        assert service.context == mock_context

        await service.start()
        assert service.started

        health = await service.health_check()
        assert health["status"] == "healthy"
        assert health["service"] == "test-service"

        await service.stop()
        assert not service.started

        health = await service.health_check()
        assert health["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_service_request_handling(self, mock_context):
        """Test service request handling."""
        service = self.TestService()
        await service.initialize(mock_context)
        await service.start()

        # Test valid endpoint
        response = await service.handle_request("/test", "GET")
        assert response["message"] == "Test endpoint"
        assert response["status"] == "ok"

        # Test invalid endpoint
        response = await service.handle_request("/invalid", "GET")
        assert response["error"] == "Not found"
        assert response["status"] == 404


class TestServiceRegistry:
    """Test service registry functionality."""

    @pytest.fixture
    def service_registry(self, mock_plugin_manager):
        """Create service registry with mock plugin manager."""
        return ServiceRegistry(mock_plugin_manager)

    @pytest.mark.asyncio
    async def test_register_service(self, service_registry, mock_context):
        """Test service registration."""
        service_def = ServiceDefinition(
            name="test-service",
            version="1.0.0",
            routes={"/test": {"methods": ["GET"], "handler": "test_handler"}},
        )

        service = TestService()

        await service_registry.register_service("test-plugin", service_def, service)

        assert "test-service" in service_registry.services
        assert service_registry.services["test-service"] == service_def
        assert "test-service" in service_registry.service_instances
        assert service_registry.service_instances["test-service"] == service
        assert "test-service" in service_registry.service_definitions

    @pytest.mark.asyncio
    async def test_start_all_services(self, service_registry, mock_context):
        """Test starting all registered services."""
        service1 = TestService()
        service2 = TestService()

        service_def1 = ServiceDefinition("service1", "1.0.0")
        service_def2 = ServiceDefinition("service2", "1.0.0")

        await service_registry.register_service("plugin1", service_def1, service1)
        await service_registry.register_service("plugin2", service_def2, service2)

        await service_registry.start_all_services()

        assert service1.started
        assert service2.started

    @pytest.mark.asyncio
    async def test_stop_all_services(self, service_registry, mock_context):
        """Test stopping all registered services."""
        service1 = TestService()
        service2 = TestService()

        service_def1 = ServiceDefinition("service1", "1.0.0")
        service_def2 = ServiceDefinition("service2", "1.0.0")

        await service_registry.register_service("plugin1", service_def1, service1)
        await service_registry.register_service("plugin2", service_def2, service2)

        await service_registry.start_all_services()
        assert service1.started and service2.started

        await service_registry.stop_all_services()
        assert not service1.started and not service2.started

    def test_get_service_info(self, service_registry):
        """Test retrieving service information."""
        # Test empty registry
        info = service_registry.get_service_info()
        assert len(info) == 0

        # Add service and test info
        service = TestService()
        service_def = ServiceDefinition(
            name="test-service", version="1.0.0", description="Test service"
        )

        asyncio.run(service_registry.register_service("test-plugin", service_def, service))

        info = service_registry.get_service_info()
        assert len(info) == 1
        assert info[0]["name"] == "test-service"
        assert info[0]["version"] == "1.0.0"
        assert info[0]["plugin"] == "test-plugin"

    @pytest.mark.asyncio
    async def test_service_health_check(self, service_registry, mock_context):
        """Test health check for all services."""
        service1 = TestService()
        service2 = TestService()

        service_def1 = ServiceDefinition("service1", "1.0.0")
        service_def2 = ServiceDefinition("service2", "1.0.0")

        await service_registry.register_service("plugin1", service_def1, service1)
        await service_registry.register_service("plugin2", service_def2, service2)

        await service_registry.start_all_services()

        health = await service_registry.get_health_status()

        assert "service1" in health
        assert "service2" in health
        assert health["service1"]["status"] == "healthy"
        assert health["service2"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_route_mounting(self, service_registry, mock_context):
        """Test route mounting for plugin services."""
        service_def = ServiceDefinition(
            name="test-service",
            version="1.0.0",
            routes={
                "/api/test": {"methods": ["GET"], "handler": "test_handler"},
                "/api/status": {"methods": ["GET"], "handler": "status_handler"},
            },
        )

        service = TestService()
        await service_registry.register_service("test-plugin", service_def, service)

        mount_info = service_registry.get_mount_info()

        assert len(mount_info) == 1
        assert mount_info[0].plugin_name == "test-plugin"
        assert mount_info[0].service_name == "test-service"
        assert "/api/test" in mount_info[0].routes
        assert "/api/status" in mount_info[0].routes

    @pytest.mark.asyncio
    async def test_duplicate_service_registration_error(self, service_registry):
        """Test error handling for duplicate service registration."""
        service1 = TestService()
        service2 = TestService()
        service_def = ServiceDefinition("test-service", "1.0.0")

        await service_registry.register_service("plugin1", service_def, service1)

        with pytest.raises(ValueError, match="Service 'test-service' is already registered"):
            await service_registry.register_service("plugin2", service_def, service2)


class TestServiceIntegration:
    """Test service integration with MMF infrastructure."""

    class IntegratedService(PluginService):
        """Test service that uses MMF infrastructure."""

        def __init__(self):
            super().__init__()
            self.database_ready = False
            self.cache_ready = False

        async def start(self) -> None:
            # Simulate database initialization
            await self.context.database.execute_ddl(
                "CREATE TABLE IF NOT EXISTS test_data (id INT, value TEXT)"
            )
            self.database_ready = True

            # Test cache connectivity
            await self.context.cache.set("test_key", "test_value", ttl=300)
            cached_value = await self.context.cache.get("test_key")
            self.cache_ready = cached_value is not None

        async def stop(self) -> None:
            await self.context.cache.delete_pattern("test_*")
            self.database_ready = False
            self.cache_ready = False

        async def health_check(self) -> dict[str, Any]:
            return {
                "status": "healthy" if (self.database_ready and self.cache_ready) else "degraded",
                "database": self.database_ready,
                "cache": self.cache_ready,
            }

        async def handle_data_request(self, data_id: int) -> dict[str, Any]:
            # Try cache first
            cached = await self.context.cache.get(f"data_{data_id}")
            if cached:
                return {"data": cached, "source": "cache"}

            # Fallback to database
            result = await self.context.database.query_one(
                "SELECT value FROM test_data WHERE id = ?", (data_id,)
            )

            if result:
                # Cache the result
                await self.context.cache.set(f"data_{data_id}", result, ttl=300)
                return {"data": result, "source": "database"}

            return {"error": "Not found", "status": 404}

    @pytest.mark.asyncio
    async def test_service_mmf_integration(self, mock_context):
        """Test service integration with MMF infrastructure."""
        service = self.IntegratedService()
        await service.initialize(mock_context)
        await service.start()

        # Verify database initialization was called
        mock_context.database.execute_ddl.assert_called_once()

        # Verify cache operations
        mock_context.cache.set.assert_called()
        mock_context.cache.get.assert_called()

        health = await service.health_check()
        # Note: In test, cache.get returns None, so cache_ready will be False
        assert health["database"] is True
        assert health["cache"] is False  # Because mock returns None

    @pytest.mark.asyncio
    async def test_service_data_operations(self, mock_context):
        """Test service data operations through MMF infrastructure."""
        service = self.IntegratedService()
        await service.initialize(mock_context)
        await service.start()

        # Test cache miss, database miss
        mock_context.cache.get.return_value = None
        mock_context.database.query_one.return_value = None

        result = await service.handle_data_request(123)
        assert result["error"] == "Not found"
        assert result["status"] == 404

        # Test cache hit
        mock_context.cache.get.return_value = "cached_data"

        result = await service.handle_data_request(123)
        assert result["data"] == "cached_data"
        assert result["source"] == "cache"

        # Test database hit
        mock_context.cache.get.side_effect = [None, None]  # Cache miss, then for set operation
        mock_context.database.query_one.return_value = "db_data"

        result = await service.handle_data_request(456)
        assert result["data"] == "db_data"
        assert result["source"] == "database"

        # Verify cache was updated
        mock_context.cache.set.assert_called_with("data_456", "db_data", ttl=300)


# Alias removed - no longer needed
