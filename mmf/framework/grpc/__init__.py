"""
gRPC infrastructure components for enterprise microservices.

This package provides:
- Unified gRPC server with observability integration
- Service definition patterns for structured service management
- Managed gRPC client with channel pooling and stub factory
- Client-side interceptors (auth, metrics)
- Health checking and monitoring
- Production-ready server configuration
"""

from .client import (
    AuthTokenInterceptor,
    GrpcChannelManager,
    GrpcStubFactory,
    MetricsClientInterceptor,
)
from .unified_grpc_server import (
    ObservableGrpcServiceMixin,
    ServiceDefinition,
    ServiceRegistrationProtocol,
    ServicerFactoryProtocol,
    UnifiedGrpcServer,
    create_document_signer_server,
    create_service_server,
    create_trust_anchor_server,
)

__all__ = [
    # Server
    "UnifiedGrpcServer",
    "ObservableGrpcServiceMixin",
    "ServiceDefinition",
    "ServicerFactoryProtocol",
    "ServiceRegistrationProtocol",
    "create_trust_anchor_server",
    "create_document_signer_server",
    "create_service_server",
    # Client
    "GrpcChannelManager",
    "GrpcStubFactory",
    "MetricsClientInterceptor",
    "AuthTokenInterceptor",
]
