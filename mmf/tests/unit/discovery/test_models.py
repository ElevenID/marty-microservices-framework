"""
Comprehensive tests for discovery domain models.

Tests ServiceEndpoint, ServiceMetadata, HealthCheck, ServiceInstance,
ServiceRegistryConfig, and ServiceQuery classes with proper coverage.
"""

import time
from dataclasses import dataclass

import pytest

from mmf.discovery.domain.models import (
    HealthCheck,
    HealthStatus,
    ServiceEndpoint,
    ServiceInstance,
    ServiceInstanceType,
    ServiceMetadata,
    ServiceQuery,
    ServiceRegistryConfig,
    ServiceStatus,
)


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_all_status_values(self):
        """Test all status enum values exist."""
        assert ServiceStatus.UNKNOWN.value == "unknown"
        assert ServiceStatus.STARTING.value == "starting"
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.CRITICAL.value == "critical"
        assert ServiceStatus.MAINTENANCE.value == "maintenance"
        assert ServiceStatus.TERMINATING.value == "terminating"
        assert ServiceStatus.TERMINATED.value == "terminated"

    def test_status_count(self):
        """Test total number of statuses."""
        assert len(ServiceStatus) == 8


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_all_health_status_values(self):
        """Test all health status enum values exist."""
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.TIMEOUT.value == "timeout"
        assert HealthStatus.ERROR.value == "error"

    def test_health_status_count(self):
        """Test total number of health statuses."""
        assert len(HealthStatus) == 5


class TestServiceInstanceType:
    """Tests for ServiceInstanceType enum."""

    def test_all_instance_types(self):
        """Test all service instance types exist."""
        assert ServiceInstanceType.HTTP.value == "http"
        assert ServiceInstanceType.HTTPS.value == "https"
        assert ServiceInstanceType.TCP.value == "tcp"
        assert ServiceInstanceType.UDP.value == "udp"
        assert ServiceInstanceType.GRPC.value == "grpc"
        assert ServiceInstanceType.WEBSOCKET.value == "websocket"

    def test_instance_type_count(self):
        """Test total number of instance types."""
        assert len(ServiceInstanceType) == 6


class TestServiceEndpoint:
    """Tests for ServiceEndpoint dataclass."""

    def test_basic_endpoint(self):
        """Test creating a basic endpoint."""
        endpoint = ServiceEndpoint(host="localhost", port=8080)

        assert endpoint.host == "localhost"
        assert endpoint.port == 8080
        assert endpoint.protocol == ServiceInstanceType.HTTP
        assert endpoint.path == ""
        assert endpoint.ssl_enabled is False
        assert endpoint.ssl_verify is True
        assert endpoint.connection_timeout == 5.0
        assert endpoint.read_timeout == 30.0

    def test_https_endpoint(self):
        """Test creating an HTTPS endpoint."""
        endpoint = ServiceEndpoint(
            host="api.example.com",
            port=443,
            protocol=ServiceInstanceType.HTTPS,
            ssl_enabled=True,
        )

        assert endpoint.protocol == ServiceInstanceType.HTTPS
        assert endpoint.ssl_enabled is True

    def test_endpoint_with_path(self):
        """Test endpoint with path."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=8080,
            path="/api/v1",
        )

        assert endpoint.path == "/api/v1"

    def test_endpoint_with_ssl_config(self):
        """Test endpoint with full SSL configuration."""
        endpoint = ServiceEndpoint(
            host="secure.example.com",
            port=443,
            ssl_enabled=True,
            ssl_verify=True,
            ssl_cert_path="/path/to/cert.pem",
            ssl_key_path="/path/to/key.pem",
        )

        assert endpoint.ssl_cert_path == "/path/to/cert.pem"
        assert endpoint.ssl_key_path == "/path/to/key.pem"

    def test_get_url_http(self):
        """Test get_url for HTTP endpoint."""
        endpoint = ServiceEndpoint(host="localhost", port=8080)
        assert endpoint.get_url() == "http://localhost:8080"

    def test_get_url_https_protocol(self):
        """Test get_url for HTTPS protocol."""
        endpoint = ServiceEndpoint(
            host="api.example.com",
            port=443,
            protocol=ServiceInstanceType.HTTPS,
        )
        assert endpoint.get_url() == "https://api.example.com:443"

    def test_get_url_ssl_enabled(self):
        """Test get_url with SSL enabled."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=8443,
            ssl_enabled=True,
        )
        assert endpoint.get_url() == "https://localhost:8443"

    def test_get_url_with_path(self):
        """Test get_url with path."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=8080,
            path="/api/v1",
        )
        assert endpoint.get_url() == "http://localhost:8080/api/v1"

    def test_get_url_with_path_no_slash(self):
        """Test get_url adds slash to path if missing."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=8080,
            path="api/v1",
        )
        assert endpoint.get_url() == "http://localhost:8080/api/v1"

    def test_get_url_tcp_protocol(self):
        """Test get_url for TCP protocol."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=5432,
            protocol=ServiceInstanceType.TCP,
        )
        assert endpoint.get_url() == "tcp://localhost:5432"

    def test_get_url_udp_protocol(self):
        """Test get_url for UDP protocol."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=53,
            protocol=ServiceInstanceType.UDP,
        )
        assert endpoint.get_url() == "udp://localhost:53"

    def test_get_url_grpc_protocol(self):
        """Test get_url for gRPC protocol."""
        endpoint = ServiceEndpoint(
            host="localhost",
            port=50051,
            protocol=ServiceInstanceType.GRPC,
        )
        assert endpoint.get_url() == "grpc://localhost:50051"

    def test_str_representation(self):
        """Test string representation returns URL."""
        endpoint = ServiceEndpoint(host="localhost", port=8080)
        assert str(endpoint) == "http://localhost:8080"

    def test_custom_timeouts(self):
        """Test endpoint with custom timeouts."""
        endpoint = ServiceEndpoint(
            host="slow.example.com",
            port=8080,
            connection_timeout=10.0,
            read_timeout=60.0,
        )

        assert endpoint.connection_timeout == 10.0
        assert endpoint.read_timeout == 60.0


class TestServiceMetadata:
    """Tests for ServiceMetadata dataclass."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = ServiceMetadata()

        assert metadata.version == "1.0.0"
        assert metadata.environment == "production"
        assert metadata.weight == 100
        assert metadata.region == "default"
        assert metadata.availability_zone == "default"
        assert metadata.tags == set()
        assert metadata.labels == {}
        assert metadata.annotations == {}

    def test_custom_metadata(self):
        """Test creating metadata with custom values."""
        metadata = ServiceMetadata(
            version="2.1.0",
            environment="staging",
            weight=50,
            region="us-east-1",
            availability_zone="us-east-1a",
            deployment_id="deploy-123",
            build_id="build-456",
            git_commit="abc123",
        )

        assert metadata.version == "2.1.0"
        assert metadata.environment == "staging"
        assert metadata.weight == 50
        assert metadata.region == "us-east-1"
        assert metadata.deployment_id == "deploy-123"

    def test_resource_info(self):
        """Test resource information fields."""
        metadata = ServiceMetadata(
            cpu_cores=4,
            memory_mb=8192,
            disk_gb=100,
        )

        assert metadata.cpu_cores == 4
        assert metadata.memory_mb == 8192
        assert metadata.disk_gb == 100

    def test_network_info(self):
        """Test network information fields."""
        metadata = ServiceMetadata(
            public_ip="203.0.113.1",
            private_ip="10.0.0.5",
            subnet="10.0.0.0/24",
        )

        assert metadata.public_ip == "203.0.113.1"
        assert metadata.private_ip == "10.0.0.5"
        assert metadata.subnet == "10.0.0.0/24"

    def test_service_config(self):
        """Test service configuration fields."""
        metadata = ServiceMetadata(
            max_connections=1000,
            request_timeout=30.0,
        )

        assert metadata.max_connections == 1000
        assert metadata.request_timeout == 30.0

    def test_add_tag(self):
        """Test adding a tag."""
        metadata = ServiceMetadata()
        metadata.add_tag("critical")
        metadata.add_tag("web")

        assert "critical" in metadata.tags
        assert "web" in metadata.tags

    def test_remove_tag(self):
        """Test removing a tag."""
        metadata = ServiceMetadata()
        metadata.add_tag("temp")
        metadata.remove_tag("temp")

        assert "temp" not in metadata.tags

    def test_remove_nonexistent_tag(self):
        """Test removing a tag that doesn't exist (should not raise)."""
        metadata = ServiceMetadata()
        metadata.remove_tag("nonexistent")  # Should not raise

    def test_has_tag(self):
        """Test checking if tag exists."""
        metadata = ServiceMetadata()
        metadata.add_tag("important")

        assert metadata.has_tag("important") is True
        assert metadata.has_tag("nonexistent") is False

    def test_set_label(self):
        """Test setting a label."""
        metadata = ServiceMetadata()
        metadata.set_label("team", "platform")
        metadata.set_label("tier", "backend")

        assert metadata.labels["team"] == "platform"
        assert metadata.labels["tier"] == "backend"

    def test_get_label(self):
        """Test getting a label."""
        metadata = ServiceMetadata()
        metadata.set_label("version", "v2")

        assert metadata.get_label("version") == "v2"
        assert metadata.get_label("missing") is None
        assert metadata.get_label("missing", "default") == "default"

    def test_set_annotation(self):
        """Test setting an annotation."""
        metadata = ServiceMetadata()
        metadata.set_annotation("description", "Main API server")

        assert metadata.annotations["description"] == "Main API server"

    def test_get_annotation(self):
        """Test getting an annotation."""
        metadata = ServiceMetadata()
        metadata.set_annotation("notes", "Legacy system")

        assert metadata.get_annotation("notes") == "Legacy system"
        assert metadata.get_annotation("missing") is None
        assert metadata.get_annotation("missing", "none") == "none"


class TestHealthCheck:
    """Tests for HealthCheck dataclass."""

    def test_default_health_check(self):
        """Test default health check values."""
        hc = HealthCheck()

        assert hc.url is None
        assert hc.method == "GET"
        assert hc.headers == {}
        assert hc.expected_status == 200
        assert hc.timeout == 5.0
        assert hc.interval == 30.0
        assert hc.initial_delay == 0.0
        assert hc.failure_threshold == 3
        assert hc.success_threshold == 2
        assert hc.follow_redirects is True
        assert hc.verify_ssl is True

    def test_http_health_check(self):
        """Test HTTP health check configuration."""
        hc = HealthCheck(
            url="/health",
            method="GET",
            expected_status=200,
            timeout=10.0,
            interval=15.0,
        )

        assert hc.url == "/health"
        assert hc.interval == 15.0

    def test_tcp_health_check(self):
        """Test TCP health check configuration."""
        hc = HealthCheck(tcp_port=5432)

        assert hc.tcp_port == 5432

    def test_custom_health_check(self):
        """Test custom health check configuration."""
        hc = HealthCheck(custom_check="check_database_connection")

        assert hc.custom_check == "check_database_connection"

    def test_health_check_with_headers(self):
        """Test health check with custom headers."""
        hc = HealthCheck(
            url="/health",
            headers={"Authorization": "Bearer token123"},
        )

        assert hc.headers["Authorization"] == "Bearer token123"

    def test_is_valid_with_url(self):
        """Test is_valid returns True for URL-based check."""
        hc = HealthCheck(url="/health")
        assert hc.is_valid() is True

    def test_is_valid_with_tcp_port(self):
        """Test is_valid returns True for TCP-based check."""
        hc = HealthCheck(tcp_port=5432)
        assert hc.is_valid() is True

    def test_is_valid_with_custom_check(self):
        """Test is_valid returns True for custom check."""
        hc = HealthCheck(custom_check="my_check")
        assert hc.is_valid() is True

    def test_is_valid_empty(self):
        """Test is_valid returns False for empty config."""
        hc = HealthCheck()
        assert hc.is_valid() is False


class TestServiceInstance:
    """Tests for ServiceInstance class."""

    def test_create_with_endpoint(self):
        """Test creating instance with endpoint object."""
        endpoint = ServiceEndpoint(host="localhost", port=8080)
        instance = ServiceInstance(
            service_name="api-service",
            endpoint=endpoint,
        )

        assert instance.service_name == "api-service"
        assert instance.endpoint == endpoint
        assert instance.instance_id is not None
        assert instance.status == ServiceStatus.UNKNOWN
        assert instance.health_status == HealthStatus.UNKNOWN

    def test_create_with_host_port(self):
        """Test creating instance with host and port."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        assert instance.endpoint.host == "localhost"
        assert instance.endpoint.port == 8080

    def test_create_with_custom_instance_id(self):
        """Test creating instance with custom ID."""
        instance = ServiceInstance(
            service_name="api-service",
            instance_id="my-custom-id",
            host="localhost",
            port=8080,
        )

        assert instance.instance_id == "my-custom-id"

    def test_create_missing_endpoint_raises(self):
        """Test that missing endpoint info raises ValueError."""
        with pytest.raises(ValueError, match="Either endpoint or host/port must be provided"):
            ServiceInstance(service_name="api-service")

    def test_create_with_custom_metadata(self):
        """Test creating instance with custom metadata."""
        metadata = ServiceMetadata(version="2.0.0", environment="staging")
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
            metadata=metadata,
        )

        assert instance.metadata.version == "2.0.0"
        assert instance.metadata.environment == "staging"

    def test_update_health_status_healthy(self):
        """Test updating health status to healthy."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.update_health_status(HealthStatus.HEALTHY)

        assert instance.health_status == HealthStatus.HEALTHY
        assert instance.status == ServiceStatus.HEALTHY
        assert instance.last_health_check is not None

    def test_update_health_status_unhealthy(self):
        """Test updating health status to unhealthy."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.update_health_status(HealthStatus.UNHEALTHY)

        assert instance.health_status == HealthStatus.UNHEALTHY
        assert instance.status == ServiceStatus.UNHEALTHY

    def test_record_request_basic(self):
        """Test recording a basic request."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_request()

        assert instance.total_requests == 1

    def test_record_request_with_response_time(self):
        """Test recording request with response time."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_request(response_time=150.0)
        instance.record_request(response_time=100.0)

        assert len(instance.response_times) == 2
        assert 150.0 in instance.response_times

    def test_record_request_failure(self):
        """Test recording a failed request."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_request(success=False)

        assert instance.total_requests == 1
        assert instance.total_failures == 1

    def test_record_request_limits_response_times(self):
        """Test that response times are limited to 100 entries."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        for i in range(150):
            instance.record_request(response_time=float(i))

        assert len(instance.response_times) == 100
        # Should keep the last 100
        assert instance.response_times[0] == 50.0

    def test_record_connection(self):
        """Test recording connections."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_connection(active=True)
        instance.record_connection(active=True)

        assert instance.active_connections == 2

        instance.record_connection(active=False)

        assert instance.active_connections == 1

    def test_record_connection_no_negative(self):
        """Test that connections don't go negative."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_connection(active=False)  # Decrease from 0

        assert instance.active_connections == 0

    def test_get_average_response_time_empty(self):
        """Test average response time with no data."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        assert instance.get_average_response_time() == 0.0

    def test_get_average_response_time(self):
        """Test average response time calculation."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_request(response_time=100.0)
        instance.record_request(response_time=200.0)
        instance.record_request(response_time=300.0)

        assert instance.get_average_response_time() == 200.0

    def test_get_success_rate_no_requests(self):
        """Test success rate with no requests."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        assert instance.get_success_rate() == 1.0

    def test_get_success_rate(self):
        """Test success rate calculation."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.record_request(success=True)
        instance.record_request(success=True)
        instance.record_request(success=True)
        instance.record_request(success=False)  # 1 failure out of 4

        assert instance.get_success_rate() == 0.75

    def test_is_healthy(self):
        """Test is_healthy check."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        # Initially not healthy (unknown status)
        assert instance.is_healthy() is False

        # Set to healthy
        instance.status = ServiceStatus.HEALTHY
        instance.health_status = HealthStatus.HEALTHY

        assert instance.is_healthy() is True

    def test_is_healthy_circuit_breaker_open(self):
        """Test is_healthy returns False when circuit breaker is open."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.status = ServiceStatus.HEALTHY
        instance.health_status = HealthStatus.HEALTHY
        instance.circuit_breaker_open = True

        assert instance.is_healthy() is False

    def test_is_available_unknown_status(self):
        """Test is_available with unknown status."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        # Unknown status is considered available
        assert instance.is_available() is True

    def test_is_available_healthy(self):
        """Test is_available with healthy status."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.status = ServiceStatus.HEALTHY
        instance.health_status = HealthStatus.HEALTHY

        assert instance.is_available() is True

    def test_is_available_unhealthy(self):
        """Test is_available with unhealthy status."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.status = ServiceStatus.UNHEALTHY

        assert instance.is_available() is False

    def test_get_weight_base(self):
        """Test get_weight with default state."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        weight = instance.get_weight()
        # With 100% success rate and no response times, weight should be 1.0
        assert weight == 1.0

    def test_get_weight_with_failures(self):
        """Test get_weight decreases with failures."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        # 50% success rate
        instance.record_request(success=True)
        instance.record_request(success=False)

        weight = instance.get_weight()
        assert weight == 0.5

    def test_get_weight_with_slow_responses(self):
        """Test get_weight decreases with slow responses."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        # Slow responses (5000ms baseline, so 2500ms = 0.5 factor)
        instance.record_request(response_time=2500.0)

        weight = instance.get_weight()
        assert weight < 1.0

    def test_get_weight_with_connections(self):
        """Test get_weight decreases with high connection ratio."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
            metadata=ServiceMetadata(max_connections=10),
        )

        # 50% of max connections
        for _ in range(5):
            instance.record_connection(active=True)

        weight = instance.get_weight()
        assert weight < 1.0

    def test_get_weight_minimum(self):
        """Test get_weight has minimum of 0.1."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        # All failures = 0 success rate, but minimum weight is 0.1
        for _ in range(10):
            instance.record_request(success=False)

        weight = instance.get_weight()
        assert weight == 0.1

    def test_to_dict(self):
        """Test to_dict serialization."""
        instance = ServiceInstance(
            service_name="api-service",
            instance_id="test-id",
            host="localhost",
            port=8080,
        )

        result = instance.to_dict()

        assert result["service_name"] == "api-service"
        assert result["instance_id"] == "test-id"
        assert result["endpoint"]["host"] == "localhost"
        assert result["endpoint"]["port"] == 8080
        assert result["endpoint"]["url"] == "http://localhost:8080"
        assert result["metadata"]["version"] == "1.0.0"
        assert result["status"] == "unknown"
        assert result["health_status"] == "unknown"
        assert "stats" in result
        assert "circuit_breaker" in result

    def test_str_representation(self):
        """Test string representation."""
        instance = ServiceInstance(
            service_name="api-service",
            instance_id="test-id",
            host="localhost",
            port=8080,
        )

        result = str(instance)
        assert "api-service" in result
        assert "test-id" in result
        assert "localhost:8080" in result

    def test_repr_representation(self):
        """Test repr representation."""
        instance = ServiceInstance(
            service_name="api-service",
            instance_id="test-id",
            host="localhost",
            port=8080,
        )

        result = repr(instance)
        assert "ServiceInstance" in result
        assert "api-service" in result
        assert "test-id" in result


class TestServiceRegistryConfig:
    """Tests for ServiceRegistryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ServiceRegistryConfig()

        assert config.enable_health_checks is True
        assert config.health_check_interval == 30.0
        assert config.instance_ttl == 300.0
        assert config.cleanup_interval == 60.0
        assert config.enable_clustering is False
        assert config.cluster_nodes == []
        assert config.replication_factor == 3
        assert config.persistence_enabled is False
        assert config.max_instances_per_service == 1000
        assert config.max_services == 10000

    def test_clustering_config(self):
        """Test clustering configuration."""
        config = ServiceRegistryConfig(
            enable_clustering=True,
            cluster_nodes=["node1:8500", "node2:8500", "node3:8500"],
            replication_factor=5,
        )

        assert config.enable_clustering is True
        assert len(config.cluster_nodes) == 3
        assert config.replication_factor == 5

    def test_persistence_config(self):
        """Test persistence configuration."""
        config = ServiceRegistryConfig(
            persistence_enabled=True,
            persistence_path="/var/lib/registry",
            backup_interval=1800.0,
        )

        assert config.persistence_enabled is True
        assert config.persistence_path == "/var/lib/registry"
        assert config.backup_interval == 1800.0

    def test_security_config(self):
        """Test security configuration."""
        config = ServiceRegistryConfig(
            enable_authentication=True,
            auth_token="secret-token",
            enable_encryption=True,
        )

        assert config.enable_authentication is True
        assert config.auth_token == "secret-token"
        assert config.enable_encryption is True

    def test_monitoring_config(self):
        """Test monitoring configuration."""
        config = ServiceRegistryConfig(
            enable_metrics=True,
            metrics_interval=30.0,
            enable_notifications=True,
            notification_channels=["slack", "email"],
        )

        assert config.enable_metrics is True
        assert config.metrics_interval == 30.0
        assert "slack" in config.notification_channels


class TestServiceQuery:
    """Tests for ServiceQuery dataclass."""

    def test_basic_query(self):
        """Test basic service query."""
        query = ServiceQuery(service_name="api-service")

        assert query.service_name == "api-service"
        assert query.version is None
        assert query.environment is None
        assert query.tags == {}
        assert query.labels == {}
        assert query.protocols == []

    def test_full_query(self):
        """Test fully specified service query."""
        query = ServiceQuery(
            service_name="api-service",
            version="2.0.0",
            environment="production",
            zone="us-east-1a",
            region="us-east-1",
            tags={"team": "platform"},
            labels={"tier": "frontend"},
            protocols=["http", "grpc"],
        )

        assert query.service_name == "api-service"
        assert query.version == "2.0.0"
        assert query.environment == "production"
        assert query.zone == "us-east-1a"
        assert query.region == "us-east-1"
        assert query.tags == {"team": "platform"}
        assert query.labels == {"tier": "frontend"}
        assert "http" in query.protocols


class TestServiceInstanceIntegration:
    """Integration tests for ServiceInstance behavior."""

    def test_full_lifecycle(self):
        """Test full instance lifecycle."""
        # Create instance
        instance = ServiceInstance(
            service_name="payment-service",
            host="10.0.0.5",
            port=8080,
            metadata=ServiceMetadata(
                version="3.0.0",
                environment="production",
                region="us-east-1",
            ),
        )

        # Initial state
        assert instance.status == ServiceStatus.UNKNOWN

        # Simulate health check success
        instance.update_health_status(HealthStatus.HEALTHY)
        assert instance.is_healthy() is True

        # Simulate requests
        instance.record_request(response_time=50.0, success=True)
        instance.record_request(response_time=75.0, success=True)
        instance.record_request(response_time=100.0, success=False)

        # Check stats
        assert instance.total_requests == 3
        assert instance.total_failures == 1
        assert instance.get_success_rate() == 2 / 3

        # Simulate health degradation
        instance.update_health_status(HealthStatus.UNHEALTHY)
        assert instance.is_healthy() is False
        assert instance.is_available() is False

    def test_circuit_breaker_behavior(self):
        """Test circuit breaker affects availability."""
        instance = ServiceInstance(
            service_name="api-service",
            host="localhost",
            port=8080,
        )

        instance.status = ServiceStatus.HEALTHY
        instance.health_status = HealthStatus.HEALTHY

        # Initially available
        assert instance.is_available() is True
        assert instance.is_healthy() is True

        # Open circuit breaker
        instance.circuit_breaker_open = True
        instance.circuit_breaker_failures = 5
        instance.circuit_breaker_last_failure = time.time()

        # Should no longer be available/healthy
        assert instance.is_available() is False
        assert instance.is_healthy() is False
