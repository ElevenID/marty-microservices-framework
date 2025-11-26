"""
Service Discovery Exceptions
"""

class ServiceDiscoveryError(Exception):
    """Base exception for service discovery errors."""
    pass

class ServiceNotFoundError(ServiceDiscoveryError):
    """Raised when a service is not found."""
    pass

class ServiceRegistrationError(ServiceDiscoveryError):
    """Raised when service registration fails."""
    pass

class ServiceDeregistrationError(ServiceDiscoveryError):
    """Raised when service deregistration fails."""
    pass

class HealthCheckError(ServiceDiscoveryError):
    """Raised when health check fails."""
    pass
