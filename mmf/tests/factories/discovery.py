"""
Factories for service discovery domain models.

Provides factory_boy factories for creating test fixtures for
ServiceEndpoint, ServiceMetadata, HealthCheck, ServiceInstance,
ServiceRegistryConfig, and ServiceQuery.
"""

import factory
from factory import Faker, LazyAttribute, SubFactory

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


class ServiceEndpointFactory(factory.Factory):
    """Factory for ServiceEndpoint dataclass."""

    class Meta:
        model = ServiceEndpoint

    host = Faker("ipv4_private")
    port = Faker("random_int", min=8000, max=9000)
    protocol = ServiceInstanceType.HTTP
    path = ""
    ssl_enabled = False
    ssl_verify = True
    ssl_cert_path = None
    ssl_key_path = None
    connection_timeout = 5.0
    read_timeout = 30.0

    class Params:
        """Traits for common endpoint configurations."""

        https = factory.Trait(
            protocol=ServiceInstanceType.HTTPS,
            ssl_enabled=True,
            port=443,
        )
        grpc = factory.Trait(
            protocol=ServiceInstanceType.GRPC,
            port=50051,
        )
        tcp = factory.Trait(
            protocol=ServiceInstanceType.TCP,
            port=5432,
        )
        with_path = factory.Trait(
            path="/api/v1",
        )


class ServiceMetadataFactory(factory.Factory):
    """Factory for ServiceMetadata dataclass."""

    class Meta:
        model = ServiceMetadata

    version = Faker("numerify", text="#.#.#")
    environment = Faker("random_element", elements=["development", "staging", "production"])
    weight = 100
    region = "us-east-1"
    availability_zone = LazyAttribute(lambda o: f"{o.region}a")
    deployment_id = None
    build_id = None
    git_commit = None
    cpu_cores = None
    memory_mb = None
    disk_gb = None
    public_ip = None
    private_ip = Faker("ipv4_private")
    subnet = None
    max_connections = None
    request_timeout = None
    tags = factory.LazyFunction(set)
    labels = factory.LazyFunction(dict)
    annotations = factory.LazyFunction(dict)

    class Params:
        """Traits for common metadata configurations."""

        with_resources = factory.Trait(
            cpu_cores=4,
            memory_mb=8192,
            disk_gb=100,
        )
        high_weight = factory.Trait(
            weight=200,
        )
        low_weight = factory.Trait(
            weight=50,
        )
        production = factory.Trait(
            environment="production",
        )
        staging = factory.Trait(
            environment="staging",
        )


class HealthCheckFactory(factory.Factory):
    """Factory for HealthCheck dataclass."""

    class Meta:
        model = HealthCheck

    url = "/health"
    method = "GET"
    headers = factory.LazyFunction(dict)
    expected_status = 200
    timeout = 5.0
    tcp_port = None
    custom_check = None
    interval = 30.0
    initial_delay = 0.0
    failure_threshold = 3
    success_threshold = 2
    follow_redirects = True
    verify_ssl = True

    class Params:
        """Traits for health check configurations."""

        tcp = factory.Trait(
            url=None,
            tcp_port=5432,
        )
        custom = factory.Trait(
            url=None,
            custom_check="check_database_connection",
        )
        aggressive = factory.Trait(
            interval=10.0,
            failure_threshold=2,
            success_threshold=1,
            timeout=2.0,
        )


class ServiceInstanceFactory(factory.Factory):
    """Factory for ServiceInstance class."""

    class Meta:
        model = ServiceInstance
        exclude = ("_host", "_port")

    # Store host/port for the endpoint
    _host = Faker("ipv4_private")
    _port = Faker("random_int", min=8000, max=9000)

    service_name = Faker("slug")
    instance_id = Faker("uuid4")
    endpoint = factory.LazyAttribute(lambda o: ServiceEndpoint(host=o._host, port=o._port))
    metadata = SubFactory(ServiceMetadataFactory)
    health_check = SubFactory(HealthCheckFactory)

    class Params:
        """Traits for common instance configurations."""

        healthy = factory.Trait(
            # Note: We set status/health_status post-creation
        )
        https = factory.Trait(
            endpoint=factory.LazyAttribute(
                lambda o: ServiceEndpoint(
                    host=o._host,
                    port=443,
                    protocol=ServiceInstanceType.HTTPS,
                    ssl_enabled=True,
                )
            )
        )
        grpc = factory.Trait(
            endpoint=factory.LazyAttribute(
                lambda o: ServiceEndpoint(
                    host=o._host,
                    port=50051,
                    protocol=ServiceInstanceType.GRPC,
                )
            )
        )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle ServiceInstance which is a class, not dataclass."""
        return model_class(*args, **kwargs)

    @classmethod
    def create_healthy(cls, **kwargs):
        """Create a healthy service instance."""
        instance = cls.create(**kwargs)
        instance.status = ServiceStatus.HEALTHY
        instance.health_status = HealthStatus.HEALTHY
        return instance

    @classmethod
    def create_unhealthy(cls, **kwargs):
        """Create an unhealthy service instance."""
        instance = cls.create(**kwargs)
        instance.status = ServiceStatus.UNHEALTHY
        instance.health_status = HealthStatus.UNHEALTHY
        return instance

    @classmethod
    def create_batch_healthy(cls, size, **kwargs):
        """Create a batch of healthy service instances."""
        instances = []
        for _ in range(size):
            instances.append(cls.create_healthy(**kwargs))
        return instances


class ServiceRegistryConfigFactory(factory.Factory):
    """Factory for ServiceRegistryConfig dataclass."""

    class Meta:
        model = ServiceRegistryConfig

    enable_health_checks = True
    health_check_interval = 30.0
    instance_ttl = 300.0
    cleanup_interval = 60.0
    enable_clustering = False
    cluster_nodes = factory.LazyFunction(list)
    replication_factor = 3
    persistence_enabled = False
    persistence_path = None
    backup_interval = 3600.0
    enable_authentication = False
    auth_token = None
    enable_encryption = False
    max_instances_per_service = 1000
    max_services = 10000
    cache_size = 10000
    enable_metrics = True
    metrics_interval = 60.0
    enable_notifications = True
    notification_channels = factory.LazyFunction(list)

    class Params:
        """Traits for registry configurations."""

        clustered = factory.Trait(
            enable_clustering=True,
            cluster_nodes=["node1:8500", "node2:8500", "node3:8500"],
            replication_factor=3,
        )
        persistent = factory.Trait(
            persistence_enabled=True,
            persistence_path="/var/lib/registry",
            backup_interval=1800.0,
        )
        secure = factory.Trait(
            enable_authentication=True,
            auth_token="secret-token-12345",
            enable_encryption=True,
        )


class ServiceQueryFactory(factory.Factory):
    """Factory for ServiceQuery dataclass."""

    class Meta:
        model = ServiceQuery

    service_name = Faker("slug")
    version = None
    environment = None
    zone = None
    region = None
    tags = factory.LazyFunction(dict)
    labels = factory.LazyFunction(dict)
    protocols = factory.LazyFunction(list)

    class Params:
        """Traits for service queries."""

        production = factory.Trait(
            environment="production",
        )
        specific_version = factory.Trait(
            version="2.0.0",
        )
        http_only = factory.Trait(
            protocols=["http", "https"],
        )
