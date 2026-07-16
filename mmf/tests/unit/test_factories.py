"""
Unit tests for test factories.

Verifies that all factories produce valid objects.
"""

import pytest

from mmf.core.gateway import (
    GatewayRequest,
    GatewayResponse,
    HTTPMethod,
    RateLimitConfig,
    RouteConfig,
    RoutingRule,
    UpstreamGroup,
    UpstreamServer,
)
from mmf.core.messaging import (
    BackendConfig,
    ExchangeConfig,
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
    ProducerConfig,
    QueueConfig,
)
from mmf.core.security.domain.models.user import AuthenticatedUser
from mmf.tests.factories import (
    AuthenticatedUserFactory,
    BackendConfigFactory,
    ExchangeConfigFactory,
    GatewayRequestFactory,
    GatewayResponseFactory,
    MessageFactory,
    MessageHeadersFactory,
    ProducerConfigFactory,
    QueueConfigFactory,
    RateLimitConfigFactory,
    RouteConfigFactory,
    RoutingRuleFactory,
    UpstreamGroupFactory,
    UpstreamServerFactory,
)


class TestGatewayFactories:
    """Tests for gateway factories."""

    def test_gateway_request_factory_default(self):
        """Test GatewayRequestFactory creates valid request."""
        request = GatewayRequestFactory()

        assert isinstance(request, GatewayRequest)
        assert request.method == HTTPMethod.GET
        assert request.path.startswith("/api/v1/resource/")
        assert request.request_id is not None

    def test_gateway_request_factory_with_override(self):
        """Test GatewayRequestFactory with field overrides."""
        request = GatewayRequestFactory(
            method=HTTPMethod.POST,
            path="/custom/path",
        )

        assert request.method == HTTPMethod.POST
        assert request.path == "/custom/path"

    def test_gateway_request_factory_with_json_body(self):
        """Test GatewayRequestFactory with JSON body trait."""
        request = GatewayRequestFactory(with_json_body=True)

        assert request.method == HTTPMethod.POST
        assert request.body is not None

    def test_gateway_request_factory_with_bearer_token(self):
        """Test GatewayRequestFactory with bearer token trait."""
        request = GatewayRequestFactory(with_bearer_token=True)

        assert "Authorization" in request.headers
        assert request.headers["Authorization"].startswith("Bearer ")

    def test_gateway_request_factory_batch(self):
        """Test creating multiple requests."""
        requests = GatewayRequestFactory.build_batch(5)

        assert len(requests) == 5
        # All should have unique IDs
        ids = [r.request_id for r in requests]
        assert len(set(ids)) == 5

    def test_gateway_response_factory_default(self):
        """Test GatewayResponseFactory creates valid response."""
        response = GatewayResponseFactory()

        assert isinstance(response, GatewayResponse)
        assert response.status_code == 200

    def test_gateway_response_factory_error_trait(self):
        """Test GatewayResponseFactory error trait."""
        response = GatewayResponseFactory(error=True)

        assert response.status_code == 500

    def test_gateway_response_factory_not_found_trait(self):
        """Test GatewayResponseFactory not found trait."""
        response = GatewayResponseFactory(not_found=True)

        assert response.status_code == 404

    def test_upstream_server_factory_default(self):
        """Test UpstreamServerFactory creates valid server."""
        server = UpstreamServerFactory()

        assert isinstance(server, UpstreamServer)
        assert server.id is not None
        assert server.port >= 8080

    def test_upstream_server_factory_unhealthy(self):
        """Test UpstreamServerFactory unhealthy trait."""
        from mmf.core.gateway import HealthStatus

        server = UpstreamServerFactory(unhealthy=True)
        assert server.status == HealthStatus.UNHEALTHY

    def test_upstream_group_factory_with_servers(self):
        """Test UpstreamGroupFactory with servers trait."""
        group = UpstreamGroupFactory(with_servers=True)

        assert isinstance(group, UpstreamGroup)
        assert len(group.servers) == 3

    def test_route_config_factory_default(self):
        """Test RouteConfigFactory creates valid route."""
        route = RouteConfigFactory()

        assert isinstance(route, RouteConfig)
        assert route.path is not None
        assert route.upstream is not None

    def test_route_config_factory_public(self):
        """Test RouteConfigFactory public trait."""
        route = RouteConfigFactory(public=True)

        assert route.auth_required is False

    def test_route_config_factory_bearer_protected(self):
        """Test RouteConfigFactory bearer protected trait."""
        from mmf.core.gateway import AuthenticationType

        route = RouteConfigFactory(bearer_protected=True)
        assert route.auth_required is True
        assert route.authentication_type == AuthenticationType.BEARER_TOKEN

    def test_rate_limit_config_factory_default(self):
        """Test RateLimitConfigFactory creates valid config."""
        config = RateLimitConfigFactory()

        assert isinstance(config, RateLimitConfig)
        assert config.requests_per_window == 100

    def test_routing_rule_factory_default(self):
        """Test RoutingRuleFactory creates valid rule."""
        rule = RoutingRuleFactory()

        assert isinstance(rule, RoutingRule)


class TestMessagingFactories:
    """Tests for messaging factories."""

    def test_message_headers_factory_default(self):
        """Test MessageHeadersFactory creates valid headers."""
        headers = MessageHeadersFactory()

        assert isinstance(headers, MessageHeaders)
        assert headers.data == {}

    def test_message_headers_factory_with_tracing(self):
        """Test MessageHeadersFactory with tracing trait."""
        headers = MessageHeadersFactory(with_tracing=True)

        assert "trace_id" in headers.data
        assert "span_id" in headers.data

    def test_message_factory_default(self):
        """Test MessageFactory creates valid message."""
        message = MessageFactory()

        assert isinstance(message, Message)
        assert message.id is not None
        assert message.priority == MessagePriority.NORMAL
        assert message.status == MessageStatus.PENDING

    def test_message_factory_high_priority(self):
        """Test MessageFactory high priority trait."""
        message = MessageFactory(high_priority=True)

        assert message.priority == MessagePriority.HIGH

    def test_message_factory_critical(self):
        """Test MessageFactory critical trait."""
        message = MessageFactory(critical=True)

        assert message.priority == MessagePriority.CRITICAL
        assert message.max_retries == 5

    def test_message_factory_request_reply(self):
        """Test MessageFactory request reply trait."""
        message = MessageFactory(request_reply=True)

        assert message.correlation_id is not None
        assert message.reply_to is not None

    def test_message_factory_expired(self):
        """Test MessageFactory expired trait."""
        message = MessageFactory(expired=True)

        assert message.is_expired() is True

    def test_message_factory_failed(self):
        """Test MessageFactory failed trait."""
        message = MessageFactory(failed=True)

        assert message.status == MessageStatus.FAILED
        assert message.retry_count == 3

    def test_message_factory_dead_letter(self):
        """Test MessageFactory dead letter trait."""
        message = MessageFactory(dead_letter=True)

        assert message.status == MessageStatus.DEAD_LETTER
        assert "original_routing_key" in message.metadata

    def test_message_factory_batch(self):
        """Test creating multiple messages."""
        messages = MessageFactory.build_batch(10)

        assert len(messages) == 10
        # All should have unique IDs
        ids = [m.id for m in messages]
        assert len(set(ids)) == 10

    def test_queue_config_factory_default(self):
        """Test QueueConfigFactory creates valid queue."""
        queue = QueueConfigFactory()

        assert isinstance(queue, QueueConfig)
        assert queue.durable is True

    def test_queue_config_factory_temporary(self):
        """Test QueueConfigFactory temporary trait."""
        queue = QueueConfigFactory(temporary=True)

        assert queue.durable is False
        assert queue.exclusive is True
        assert queue.auto_delete is True

    def test_exchange_config_factory_default(self):
        """Test ExchangeConfigFactory creates valid exchange."""
        exchange = ExchangeConfigFactory()

        assert isinstance(exchange, ExchangeConfig)
        assert exchange.type == "direct"

    def test_exchange_config_factory_topic(self):
        """Test ExchangeConfigFactory topic trait."""
        exchange = ExchangeConfigFactory(topic=True)

        assert exchange.type == "topic"

    def test_backend_config_factory_default(self):
        """Test BackendConfigFactory creates valid config."""
        from mmf.core.messaging import BackendType

        config = BackendConfigFactory()

        assert isinstance(config, BackendConfig)
        assert config.type == BackendType.MEMORY

    def test_backend_config_factory_rabbitmq(self):
        """Test BackendConfigFactory RabbitMQ trait."""
        from mmf.core.messaging import BackendType

        config = BackendConfigFactory(rabbitmq=True)

        assert config.type == BackendType.RABBITMQ
        assert "amqp://" in config.connection_url

    def test_producer_config_factory_default(self):
        """Test ProducerConfigFactory creates valid config."""
        config = ProducerConfigFactory()

        assert isinstance(config, ProducerConfig)


class TestSecurityFactories:
    """Tests for security factories."""

    def test_authenticated_user_factory_default(self):
        """Test AuthenticatedUserFactory creates valid user."""
        user = AuthenticatedUserFactory()

        assert isinstance(user, AuthenticatedUser)
        assert user.user_id is not None
        assert user.username is not None
        assert user.email is not None
        assert "user" in user.roles
        assert "read" in user.permissions

    def test_authenticated_user_factory_admin(self):
        """Test AuthenticatedUserFactory admin trait."""
        user = AuthenticatedUserFactory(admin=True)

        assert "admin" in user.roles
        assert "admin" in user.permissions
        assert user.user_type == "administrator"

    def test_authenticated_user_factory_guest(self):
        """Test AuthenticatedUserFactory guest trait."""
        user = AuthenticatedUserFactory(guest=True)

        assert user.username is None
        assert "guest" in user.roles
        assert user.auth_method == "anonymous"

    def test_authenticated_user_factory_service_account(self):
        """Test AuthenticatedUserFactory service account trait."""
        user = AuthenticatedUserFactory(service_account=True)

        assert user.username.startswith("svc_")
        assert "service" in user.roles
        assert user.auth_method == "api_key"

    def test_authenticated_user_factory_expired(self):
        """Test AuthenticatedUserFactory expired trait."""
        user = AuthenticatedUserFactory(expired=True)

        assert user.is_expired() is True

    def test_authenticated_user_factory_applicant(self):
        """Test AuthenticatedUserFactory applicant trait."""
        user = AuthenticatedUserFactory(applicant=True)

        assert user.user_type == "applicant"
        assert user.applicant_id is not None
        assert "applicant" in user.roles

    def test_authenticated_user_factory_mfa(self):
        """Test AuthenticatedUserFactory MFA trait."""
        user = AuthenticatedUserFactory(mfa=True)

        assert user.auth_method == "mfa"
        assert user.metadata.get("mfa_verified") is True

    def test_authenticated_user_factory_batch(self):
        """Test creating multiple users."""
        users = AuthenticatedUserFactory.build_batch(5)

        assert len(users) == 5
        # All should have unique IDs
        ids = [u.user_id for u in users]
        assert len(set(ids)) == 5


class TestDiscoveryFactories:
    """Tests for discovery domain factories."""

    def test_service_endpoint_factory_default(self):
        """Test ServiceEndpointFactory creates valid endpoint."""
        from mmf.discovery.domain.models import ServiceEndpoint, ServiceInstanceType
        from mmf.tests.factories import ServiceEndpointFactory

        endpoint = ServiceEndpointFactory()

        assert isinstance(endpoint, ServiceEndpoint)
        assert endpoint.host is not None
        assert endpoint.port >= 8000
        assert endpoint.protocol == ServiceInstanceType.HTTP

    def test_service_endpoint_factory_https(self):
        """Test ServiceEndpointFactory HTTPS trait."""
        from mmf.discovery.domain.models import ServiceInstanceType
        from mmf.tests.factories import ServiceEndpointFactory

        endpoint = ServiceEndpointFactory(https=True)

        assert endpoint.protocol == ServiceInstanceType.HTTPS
        assert endpoint.ssl_enabled is True
        assert endpoint.port == 443

    def test_service_endpoint_factory_grpc(self):
        """Test ServiceEndpointFactory gRPC trait."""
        from mmf.discovery.domain.models import ServiceInstanceType
        from mmf.tests.factories import ServiceEndpointFactory

        endpoint = ServiceEndpointFactory(grpc=True)

        assert endpoint.protocol == ServiceInstanceType.GRPC
        assert endpoint.port == 50051

    def test_service_endpoint_factory_with_path(self):
        """Test ServiceEndpointFactory with path trait."""
        from mmf.tests.factories import ServiceEndpointFactory

        endpoint = ServiceEndpointFactory(with_path=True)

        assert endpoint.path == "/api/v1"

    def test_service_metadata_factory_default(self):
        """Test ServiceMetadataFactory creates valid metadata."""
        from mmf.discovery.domain.models import ServiceMetadata
        from mmf.tests.factories import ServiceMetadataFactory

        metadata = ServiceMetadataFactory()

        assert isinstance(metadata, ServiceMetadata)
        assert metadata.version is not None
        assert metadata.environment in ["development", "staging", "production"]
        assert metadata.weight == 100

    def test_service_metadata_factory_with_resources(self):
        """Test ServiceMetadataFactory with resources trait."""
        from mmf.tests.factories import ServiceMetadataFactory

        metadata = ServiceMetadataFactory(with_resources=True)

        assert metadata.cpu_cores == 4
        assert metadata.memory_mb == 8192
        assert metadata.disk_gb == 100

    def test_service_metadata_factory_high_weight(self):
        """Test ServiceMetadataFactory high weight trait."""
        from mmf.tests.factories import ServiceMetadataFactory

        metadata = ServiceMetadataFactory(high_weight=True)

        assert metadata.weight == 200

    def test_health_check_factory_default(self):
        """Test HealthCheckFactory creates valid health check."""
        from mmf.discovery.domain.models import HealthCheck
        from mmf.tests.factories import HealthCheckFactory

        hc = HealthCheckFactory()

        assert isinstance(hc, HealthCheck)
        assert hc.url == "/health"
        assert hc.method == "GET"
        assert hc.is_valid() is True

    def test_health_check_factory_tcp(self):
        """Test HealthCheckFactory TCP trait."""
        from mmf.tests.factories import HealthCheckFactory

        hc = HealthCheckFactory(tcp=True)

        assert hc.url is None
        assert hc.tcp_port == 5432
        assert hc.is_valid() is True

    def test_health_check_factory_aggressive(self):
        """Test HealthCheckFactory aggressive trait."""
        from mmf.tests.factories import HealthCheckFactory

        hc = HealthCheckFactory(aggressive=True)

        assert hc.interval == 10.0
        assert hc.failure_threshold == 2
        assert hc.timeout == 2.0

    def test_service_instance_factory_default(self):
        """Test ServiceInstanceFactory creates valid instance."""
        from mmf.discovery.domain.models import ServiceInstance, ServiceStatus
        from mmf.tests.factories import ServiceInstanceFactory

        instance = ServiceInstanceFactory()

        assert isinstance(instance, ServiceInstance)
        assert instance.service_name is not None
        assert instance.instance_id is not None
        assert instance.endpoint is not None
        assert instance.status == ServiceStatus.UNKNOWN

    def test_service_instance_factory_create_healthy(self):
        """Test ServiceInstanceFactory create_healthy method."""
        from mmf.discovery.domain.models import HealthStatus, ServiceStatus
        from mmf.tests.factories import ServiceInstanceFactory

        instance = ServiceInstanceFactory.create_healthy()

        assert instance.status == ServiceStatus.HEALTHY
        assert instance.health_status == HealthStatus.HEALTHY
        assert instance.is_healthy() is True

    def test_service_instance_factory_create_unhealthy(self):
        """Test ServiceInstanceFactory create_unhealthy method."""
        from mmf.discovery.domain.models import HealthStatus, ServiceStatus
        from mmf.tests.factories import ServiceInstanceFactory

        instance = ServiceInstanceFactory.create_unhealthy()

        assert instance.status == ServiceStatus.UNHEALTHY
        assert instance.health_status == HealthStatus.UNHEALTHY
        assert instance.is_healthy() is False

    def test_service_instance_factory_create_batch_healthy(self):
        """Test ServiceInstanceFactory create_batch_healthy method."""
        from mmf.tests.factories import ServiceInstanceFactory

        instances = ServiceInstanceFactory.create_batch_healthy(3)

        assert len(instances) == 3
        assert all(i.is_healthy() for i in instances)

    def test_service_registry_config_factory_default(self):
        """Test ServiceRegistryConfigFactory creates valid config."""
        from mmf.discovery.domain.models import ServiceRegistryConfig
        from mmf.tests.factories import ServiceRegistryConfigFactory

        config = ServiceRegistryConfigFactory()

        assert isinstance(config, ServiceRegistryConfig)
        assert config.enable_health_checks is True
        assert config.enable_clustering is False

    def test_service_registry_config_factory_clustered(self):
        """Test ServiceRegistryConfigFactory clustered trait."""
        from mmf.tests.factories import ServiceRegistryConfigFactory

        config = ServiceRegistryConfigFactory(clustered=True)

        assert config.enable_clustering is True
        assert len(config.cluster_nodes) == 3

    def test_service_registry_config_factory_secure(self):
        """Test ServiceRegistryConfigFactory secure trait."""
        from mmf.tests.factories import ServiceRegistryConfigFactory

        config = ServiceRegistryConfigFactory(secure=True)

        assert config.enable_authentication is True
        assert config.auth_token is not None
        assert config.enable_encryption is True

    def test_service_query_factory_default(self):
        """Test ServiceQueryFactory creates valid query."""
        from mmf.discovery.domain.models import ServiceQuery
        from mmf.tests.factories import ServiceQueryFactory

        query = ServiceQueryFactory()

        assert isinstance(query, ServiceQuery)
        assert query.service_name is not None

    def test_service_query_factory_production(self):
        """Test ServiceQueryFactory production trait."""
        from mmf.tests.factories import ServiceQueryFactory

        query = ServiceQueryFactory(production=True)

        assert query.environment == "production"

    def test_service_query_factory_http_only(self):
        """Test ServiceQueryFactory http only trait."""
        from mmf.tests.factories import ServiceQueryFactory

        query = ServiceQueryFactory(http_only=True)

        assert "http" in query.protocols
        assert "https" in query.protocols
