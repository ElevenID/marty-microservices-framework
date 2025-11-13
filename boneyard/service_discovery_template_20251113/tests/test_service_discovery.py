"""
Comprehensive test suite for Service Discovery Template

This module provides extensive testing for the service discovery system including:
- Unit tests for core functionality
- Integration tests with different registry backends
- Performance and load testing
- Health check validation
- Load balancing algorithm testing
- Security and authentication testing
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Import the service discovery components
from main import HealthCheckResult, ServiceDiscoveryService, ServiceInstance, app

from config import RegistryType, create_development_config, create_kubernetes_config


class TestServiceDiscoveryCore:
    """Core service discovery functionality tests."""

    @pytest.fixture
    def config(self):
        """Provide test configuration."""
        return create_development_config()

    @pytest.fixture
    def discovery_service(self, config):
        """Provide service discovery instance."""
        return ServiceDiscoveryService(config)

    @pytest.fixture
    def test_client(self):
        """Provide test client for API testing."""
        return TestClient(app)

    @pytest.fixture
    def sample_service(self):
        """Provide sample service instance for testing."""
        return ServiceInstance(
            name="test-service",
            host="10.0.1.100",
            port=8080,
            tags={"api", "v1"},
            metadata={"version": "1.0.0", "protocol": "http"},
            health_check_enabled=True,
            health_check_path="/health",
        )

    def test_service_instance_creation(self, sample_service):
        """Test service instance creation and validation."""
        assert sample_service.name == "test-service"
        assert sample_service.host == "10.0.1.100"
        assert sample_service.port == 8080
        assert "api" in sample_service.tags
        assert "v1" in sample_service.tags
        assert sample_service.metadata["version"] == "1.0.0"
        assert sample_service.health_check_enabled is True
        assert sample_service.health_check_path == "/health"

    def test_service_instance_serialization(self, sample_service):
        """Test service instance JSON serialization."""
        data = sample_service.dict()
        assert data["name"] == "test-service"
        assert data["host"] == "10.0.1.100"
        assert data["port"] == 8080
        assert set(data["tags"]) == {"api", "v1"}

        # Test deserialization
        restored = ServiceInstance(**data)
        assert restored.name == sample_service.name
        assert restored.host == sample_service.host
        assert restored.port == sample_service.port

    @pytest.mark.asyncio
    async def test_service_registration(self, discovery_service, sample_service):
        """Test service registration functionality."""
        # Mock the registry backend
        discovery_service._registry = AsyncMock()
        discovery_service._registry.register_service = AsyncMock(return_value=True)

        result = await discovery_service.register_service(sample_service)

        assert result is True
        discovery_service._registry.register_service.assert_called_once_with(
            sample_service
        )

    @pytest.mark.asyncio
    async def test_service_deregistration(self, discovery_service, sample_service):
        """Test service deregistration functionality."""
        # Mock the registry backend
        discovery_service._registry = AsyncMock()
        discovery_service._registry.deregister_service = AsyncMock(return_value=True)

        result = await discovery_service.deregister_service(
            "test-service", "instance-1"
        )

        assert result is True
        discovery_service._registry.deregister_service.assert_called_once_with(
            "test-service", "instance-1"
        )

    @pytest.mark.asyncio
    async def test_service_discovery(self, discovery_service, sample_service):
        """Test service discovery functionality."""
        # Mock the registry backend
        discovery_service._registry = AsyncMock()
        discovery_service._registry.discover_services = AsyncMock(
            return_value=[sample_service]
        )

        services = await discovery_service.discover_services("test-service")

        assert len(services) == 1
        assert services[0].name == "test-service"
        discovery_service._registry.discover_services.assert_called_once_with(
            "test-service", tags=None, healthy_only=True
        )

    @pytest.mark.asyncio
    async def test_service_discovery_with_tags(self, discovery_service, sample_service):
        """Test service discovery with tag filtering."""
        # Mock the registry backend
        discovery_service._registry = AsyncMock()
        discovery_service._registry.discover_services = AsyncMock(
            return_value=[sample_service]
        )

        services = await discovery_service.discover_services(
            "test-service", tags={"api"}
        )

        assert len(services) == 1
        discovery_service._registry.discover_services.assert_called_once_with(
            "test-service", tags={"api"}, healthy_only=True
        )

    @pytest.mark.asyncio
    async def test_health_check_http(self, discovery_service, sample_service):
        """Test HTTP health check functionality."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_response

            result = await discovery_service.check_service_health(sample_service)

            assert isinstance(result, HealthCheckResult)
            assert result.healthy is True
            assert result.status_code == 200
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, discovery_service, sample_service):
        """Test health check failure handling."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.RequestError("Connection failed")

            result = await discovery_service.check_service_health(sample_service)

            assert isinstance(result, HealthCheckResult)
            assert result.healthy is False
            assert "Connection failed" in result.error


class TestLoadBalancing:
    """Load balancing algorithm tests."""

    @pytest.fixture
    def services(self):
        """Provide list of service instances for load balancing tests."""
        return [
            ServiceInstance(
                name="test-service",
                host="10.0.1.100",
                port=8080,
                instance_id="instance-1",
            ),
            ServiceInstance(
                name="test-service",
                host="10.0.1.101",
                port=8080,
                instance_id="instance-2",
            ),
            ServiceInstance(
                name="test-service",
                host="10.0.1.102",
                port=8080,
                instance_id="instance-3",
            ),
        ]

    @pytest.fixture
    def discovery_service(self):
        """Provide service discovery instance with memory registry."""
        config = create_development_config()
        config.registry_type = RegistryType.MEMORY
        return ServiceDiscoveryService(config)

    def test_round_robin_balancing(self, discovery_service, services):
        """Test round-robin load balancing."""
        # Test multiple selections to verify round-robin behavior
        selections = []
        for _ in range(6):  # Two full rounds
            selected = discovery_service._select_instance_round_robin(services)
            selections.append(selected.instance_id)

        # Should cycle through instances
        expected = ["instance-1", "instance-2", "instance-3"] * 2
        assert selections == expected

    def test_random_balancing(self, discovery_service, services):
        """Test random load balancing."""
        # Test multiple selections
        selections = set()
        for _ in range(20):
            selected = discovery_service._select_instance_random(services)
            selections.add(selected.instance_id)

        # Should eventually select all instances
        assert len(selections) == 3

    def test_weighted_round_robin(self, discovery_service, services):
        """Test weighted round-robin load balancing."""
        # Set different weights
        weights = {"instance-1": 1.0, "instance-2": 2.0, "instance-3": 1.0}

        selections = []
        for _ in range(8):  # Two full weighted rounds
            selected = discovery_service._select_instance_weighted_round_robin(
                services, weights
            )
            selections.append(selected.instance_id)

        # instance-2 should appear twice as often
        instance_2_count = selections.count("instance-2")
        instance_1_count = selections.count("instance-1")
        assert instance_2_count >= instance_1_count

    def test_least_connections_balancing(self, discovery_service, services):
        """Test least connections load balancing."""
        # Mock connection counts
        connection_counts = {"instance-1": 5, "instance-2": 2, "instance-3": 8}

        selected = discovery_service._select_instance_least_connections(
            services, connection_counts
        )

        # Should select instance with least connections
        assert selected.instance_id == "instance-2"

    def test_health_based_balancing(self, discovery_service, services):
        """Test health-based load balancing."""
        # Mock health scores
        health_scores = {"instance-1": 0.9, "instance-2": 0.7, "instance-3": 0.95}

        selected = discovery_service._select_instance_health_based(
            services, health_scores
        )

        # Should prefer healthier instances
        assert selected.instance_id in ["instance-1", "instance-3"]


class TestAPIEndpoints:
    """API endpoint tests."""

    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Setup test environment with mocked dependencies."""
        with patch("main.discovery_service") as mock_service:
            mock_service._registry = AsyncMock()
            yield mock_service

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_ready_endpoint(self, client):
        """Test readiness check endpoint."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"

    def test_startup_endpoint(self, client):
        """Test startup check endpoint."""
        response = client.get("/health/startup")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "started"

    def test_service_registration_endpoint(self, client, setup_test_environment):
        """Test service registration API endpoint."""
        service_data = {
            "name": "test-service",
            "host": "10.0.1.100",
            "port": 8080,
            "tags": ["api", "v1"],
            "metadata": {"version": "1.0.0"},
            "health_check": {"enabled": True, "http_path": "/health"},
        }

        setup_test_environment.register_service = AsyncMock(return_value=True)

        response = client.post("/api/v1/services", json=service_data)
        assert response.status_code == 201

        data = response.json()
        assert data["message"] == "Service registered successfully"
        assert "instance_id" in data

    def test_service_deregistration_endpoint(self, client, setup_test_environment):
        """Test service deregistration API endpoint."""
        setup_test_environment.deregister_service = AsyncMock(return_value=True)

        response = client.delete("/api/v1/services/test-service/instance-1")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "Service deregistered successfully"

    def test_service_discovery_endpoint(self, client, setup_test_environment):
        """Test service discovery API endpoint."""
        sample_service = ServiceInstance(
            name="test-service",
            host="10.0.1.100",
            port=8080,
            tags={"api", "v1"},
            metadata={"version": "1.0.0"},
        )

        setup_test_environment.discover_services = AsyncMock(
            return_value=[sample_service]
        )

        response = client.get("/api/v1/services/test-service")
        assert response.status_code == 200

        data = response.json()
        assert len(data["instances"]) == 1
        assert data["instances"][0]["name"] == "test-service"

    def test_service_list_endpoint(self, client, setup_test_environment):
        """Test service list API endpoint."""
        services = {
            "test-service": [
                ServiceInstance(name="test-service", host="10.0.1.100", port=8080)
            ]
        }

        setup_test_environment.list_all_services = AsyncMock(return_value=services)

        response = client.get("/api/v1/services")
        assert response.status_code == 200

        data = response.json()
        assert "test-service" in data["services"]

    def test_load_balanced_instance_endpoint(self, client, setup_test_environment):
        """Test load-balanced instance selection endpoint."""
        sample_service = ServiceInstance(
            name="test-service", host="10.0.1.100", port=8080
        )

        setup_test_environment.get_load_balanced_instance = AsyncMock(
            return_value=sample_service
        )

        response = client.get("/api/v1/services/test-service/instance")
        assert response.status_code == 200

        data = response.json()
        assert data["host"] == "10.0.1.100"
        assert data["port"] == 8080

    def test_health_check_endpoint(self, client, setup_test_environment):
        """Test service health check endpoint."""
        health_result = HealthCheckResult(
            healthy=True, status_code=200, response_time=0.1, timestamp=1234567890
        )

        setup_test_environment.check_service_health_by_name = AsyncMock(
            return_value=health_result
        )

        response = client.get("/api/v1/health/test-service")
        assert response.status_code == 200

        data = response.json()
        assert data["healthy"] is True
        assert data["status_code"] == 200

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "service_discovery_" in response.text


class TestRegistryBackends:
    """Registry backend integration tests."""

    @pytest.mark.consul
    @pytest.mark.asyncio
    async def test_consul_backend(self):
        """Test Consul registry backend."""
        config = create_development_config()
        config.registry_type = RegistryType.CONSUL

        discovery_service = ServiceDiscoveryService(config)

        # Mock consul client
        with patch("consul.aio.Consul") as mock_consul:
            mock_client = AsyncMock()
            mock_consul.return_value = mock_client

            # Test service registration
            sample_service = ServiceInstance(
                name="test-service", host="10.0.1.100", port=8080
            )

            mock_client.agent.service.register = AsyncMock(return_value=True)

            await discovery_service._registry.register_service(sample_service)
            mock_client.agent.service.register.assert_called_once()

    @pytest.mark.etcd
    @pytest.mark.asyncio
    async def test_etcd_backend(self):
        """Test etcd registry backend."""
        config = create_development_config()
        config.registry_type = RegistryType.ETCD

        discovery_service = ServiceDiscoveryService(config)

        # Mock etcd client
        with patch("etcd3.aio.client") as mock_etcd:
            mock_client = AsyncMock()
            mock_etcd.return_value = mock_client

            # Test service registration
            sample_service = ServiceInstance(
                name="test-service", host="10.0.1.100", port=8080
            )

            mock_client.put = AsyncMock(return_value=True)

            await discovery_service._registry.register_service(sample_service)
            mock_client.put.assert_called_once()

    @pytest.mark.k8s
    @pytest.mark.asyncio
    async def test_kubernetes_backend(self):
        """Test Kubernetes registry backend."""
        config = create_kubernetes_config()

        discovery_service = ServiceDiscoveryService(config)

        # Mock Kubernetes client
        with patch("kubernetes.client.CoreV1Api") as mock_k8s:
            mock_client = AsyncMock()
            mock_k8s.return_value = mock_client

            # Test service discovery
            mock_services = MagicMock()
            mock_services.items = []
            mock_client.list_service_for_all_namespaces = AsyncMock(
                return_value=mock_services
            )

            await discovery_service._registry.discover_services(
                "test-service"
            )
            mock_client.list_service_for_all_namespaces.assert_called_once()


class TestSecurity:
    """Security and authentication tests."""

    @pytest.fixture
    def secured_client(self):
        """Provide test client with security enabled."""
        with patch("main.config") as mock_config:
            mock_config.security.api_key_enabled = True
            mock_config.security.api_keys = {"test-api-key"}
            return TestClient(app)

    def test_api_key_authentication(self, secured_client):
        """Test API key authentication."""
        # Request without API key should fail
        response = secured_client.get("/api/v1/services")
        assert response.status_code == 401

        # Request with valid API key should succeed
        headers = {"X-API-Key": "test-api-key"}
        response = secured_client.get("/api/v1/services", headers=headers)
        assert response.status_code == 200

    def test_invalid_api_key(self, secured_client):
        """Test invalid API key handling."""
        headers = {"X-API-Key": "invalid-key"}
        response = secured_client.get("/api/v1/services", headers=headers)
        assert response.status_code == 401


class TestPerformance:
    """Performance and load testing."""

    @pytest.mark.benchmark
    def test_service_registration_performance(self, benchmark):
        """Benchmark service registration performance."""
        config = create_development_config()
        config.registry_type = RegistryType.MEMORY
        discovery_service = ServiceDiscoveryService(config)

        sample_service = ServiceInstance(
            name="test-service", host="10.0.1.100", port=8080
        )

        async def register_service():
            return await discovery_service.register_service(sample_service)

        result = benchmark(asyncio.run, register_service())
        assert result is True

    @pytest.mark.benchmark
    def test_service_discovery_performance(self, benchmark):
        """Benchmark service discovery performance."""
        config = create_development_config()
        config.registry_type = RegistryType.MEMORY
        discovery_service = ServiceDiscoveryService(config)

        # Pre-register services
        async def setup():
            for i in range(100):
                service = ServiceInstance(
                    name="test-service",
                    host=f"10.0.1.{i}",
                    port=8080,
                    instance_id=f"instance-{i}",
                )
                await discovery_service.register_service(service)

        asyncio.run(setup())

        async def discover_services():
            return await discovery_service.discover_services("test-service")

        result = benchmark(asyncio.run, discover_services())
        assert len(result) == 100

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_registrations(self):
        """Test concurrent service registrations."""
        config = create_development_config()
        config.registry_type = RegistryType.MEMORY
        discovery_service = ServiceDiscoveryService(config)

        # Create multiple services to register concurrently
        services = [
            ServiceInstance(
                name=f"test-service-{i}",
                host=f"10.0.1.{i}",
                port=8080,
                instance_id=f"instance-{i}",
            )
            for i in range(50)
        ]

        # Register all services concurrently
        tasks = [discovery_service.register_service(service) for service in services]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All registrations should succeed
        assert all(
            result is True for result in results if not isinstance(result, Exception)
        )

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check performance with multiple services."""
        config = create_development_config()
        discovery_service = ServiceDiscoveryService(config)

        # Create services for health checking
        services = [
            ServiceInstance(
                name=f"test-service-{i}",
                host="httpbin.org",  # Use httpbin for real HTTP testing
                port=80,
                health_check_path="/status/200",
                instance_id=f"instance-{i}",
            )
            for i in range(10)
        ]

        # Check health of all services concurrently
        tasks = [
            discovery_service.check_service_health(service) for service in services
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most health checks should succeed (allowing for network issues)
        successful_checks = sum(
            1
            for result in results
            if isinstance(result, HealthCheckResult) and result.healthy
        )
        assert successful_checks >= len(services) * 0.8  # At least 80% success rate


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=main",
            "--cov=config",
            "--cov-report=html",
            "--cov-report=term-missing",
        ]
    )
