"""
Test Factories Module

This module provides factory_boy factories for generating test data.
Factories provide consistent, valid test objects with sensible defaults
that can be easily customized for specific test cases.

Usage:
    from mmf.tests.factories import (
        GatewayRequestFactory,
        GatewayResponseFactory,
        MessageFactory,
        AuthenticatedUserFactory,
        RouteConfigFactory,
        UpstreamServerFactory,
    )

    # Create with defaults
    request = GatewayRequestFactory()

    # Override specific fields
    request = GatewayRequestFactory(method=HTTPMethod.POST, path="/api/users")

    # Create multiple instances
    requests = GatewayRequestFactory.build_batch(5)
"""

from .discovery import (
    HealthCheckFactory,
    ServiceEndpointFactory,
    ServiceInstanceFactory,
    ServiceMetadataFactory,
    ServiceQueryFactory,
    ServiceRegistryConfigFactory,
)
from .gateway import (
    GatewayRequestFactory,
    GatewayResponseFactory,
    RateLimitConfigFactory,
    RouteConfigFactory,
    RoutingRuleFactory,
    UpstreamGroupFactory,
    UpstreamServerFactory,
)
from .messaging import (
    BackendConfigFactory,
    ExchangeConfigFactory,
    MessageFactory,
    MessageHeadersFactory,
    ProducerConfigFactory,
    QueueConfigFactory,
)
from .security import AuthenticatedUserFactory

__all__ = [
    # Gateway
    "GatewayRequestFactory",
    "GatewayResponseFactory",
    "RouteConfigFactory",
    "UpstreamServerFactory",
    "UpstreamGroupFactory",
    "RateLimitConfigFactory",
    "RoutingRuleFactory",
    # Messaging
    "MessageFactory",
    "MessageHeadersFactory",
    "QueueConfigFactory",
    "ExchangeConfigFactory",
    "BackendConfigFactory",
    "ProducerConfigFactory",
    # Security
    "AuthenticatedUserFactory",
    # Discovery
    "ServiceEndpointFactory",
    "ServiceMetadataFactory",
    "HealthCheckFactory",
    "ServiceInstanceFactory",
    "ServiceRegistryConfigFactory",
    "ServiceQueryFactory",
]
