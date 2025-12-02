"""Domain layer initialization."""

from .contracts import (
    IAuditDestination,
    IAuditEncryption,
    IAuditLogger,
    IAuditRepository,
    IMiddlewareAuditor,
)
from .entities import ApiCallEvent, MiddlewareAuditEvent, RequestAuditEvent
from .value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResourceInfo,
    ResponseMetadata,
    ServiceContext,
)

__all__ = [
    # Entities
    "RequestAuditEvent",
    "ApiCallEvent",
    "MiddlewareAuditEvent",
    # Value Objects
    "RequestContext",
    "ResponseMetadata",
    "PerformanceMetrics",
    "ActorInfo",
    "ResourceInfo",
    "ServiceContext",
    # Contracts (Ports)
    "IAuditDestination",
    "IAuditEncryption",
    "IAuditRepository",
    "IAuditLogger",
    "IMiddlewareAuditor",
]
