"""
Integration Domain Exceptions
"""

class IntegrationError(Exception):
    """Base exception for integration errors."""

class ConnectionFailedError(IntegrationError):
    """Raised when connection to external system fails."""

class CircuitBreakerOpenError(IntegrationError):
    """Raised when circuit breaker is open."""

class TransformationError(IntegrationError):
    """Raised when data transformation fails."""

class ConfigurationError(IntegrationError):
    """Raised when configuration is invalid."""

class RequestTimeoutError(IntegrationError):
    """Raised when request times out."""

