"""
Platform Layer for MMF Core Framework.

This package provides cross-cutting platform services and infrastructure
for the MMF framework, including service registry, configuration, observability,
security, and messaging services following hexagonal architecture principles.
"""

# Base service classes
from .base_services import BaseService, ServiceWithDependencies

# Service contracts (protocols)
from .contracts import (
    IConfigurationService,
    IMessagingService,
    IObservabilityService,
    ISecurityService,
    IServiceRegistry,
)

# Service implementations
# from .implementations import (
#     ConfigurationService,
#     MessagingService,
#     ObservabilityService,
#     SecurityService,
#     ServiceRegistry,
# )

# Utilities
# from .utilities import AtomicCounter, Registry, TypedSingleton

# Bootstrap
# from .bootstrap import (
#     create_atomic_counter,
#     create_configuration_service,
#     create_messaging_service,
#     create_observability_service,
#     create_security_service,
#     create_service_registry,
#     initialize_platform_services,
#     shutdown_platform_services,
# )

__all__ = [
    # Base classes
    "BaseService",
    "ServiceWithDependencies",
    # Contracts
    "IServiceRegistry",
    "IConfigurationService",
    "IObservabilityService",
    "ISecurityService",
    "IMessagingService",
    # Implementations
    # "ServiceRegistry",
    # "ConfigurationService",
    # "ObservabilityService",
    # "SecurityService",
    # "MessagingService",
    # Utilities
    # "Registry",
    # "AtomicCounter",
    # "TypedSingleton",
    # Bootstrap
    # "initialize_platform_services",
    # "shutdown_platform_services",
    # "create_service_registry",
    # "create_configuration_service",
    # "create_observability_service",
    # "create_security_service",
    # "create_messaging_service",
    # "create_atomic_counter",
]
