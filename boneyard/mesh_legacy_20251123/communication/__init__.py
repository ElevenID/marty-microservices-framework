"""
Communication package for Marty Microservices Framework

This package provides comprehensive service communication functionality including:
- Communication models and protocols
- Health checking for services
- Service-to-service communication management
- Service dependency management
- Advanced service discovery

Migration note: This package consolidates all communication functionality.
The previous communication.py file has been merged into this __init__.py to prevent
divergent entry points and duplicate exports.

For new development, import directly from this package:
- from marty_mmf.framework.mesh.communication import ServiceHealthChecker
- from marty_mmf.framework.mesh.communication import CommunicationProtocol
- etc.
"""

from .health_checker import ServiceHealthChecker
from .models import (
    CommunicationMetrics,
    CommunicationProtocol,
    DependencyType,
    HealthStatus,
    ServiceContract,
    ServiceDependency,
    ServiceInstance,
    ServiceState,
    ServiceType,
)

__all__ = [
    "CommunicationProtocol",
    "ServiceType",
    "HealthStatus",
    "ServiceState",
    "DependencyType",
    "ServiceInstance",
    "ServiceDependency",
    "ServiceContract",
    "CommunicationMetrics",
    "ServiceHealthChecker",
]
