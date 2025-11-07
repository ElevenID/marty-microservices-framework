"""
Integration layer for Marty Microservices Framework.

This module provides framework-specific bindings for core business logic,
following hexagonal architecture principles.
"""

from .configuration import IntegrationConfig
from .http_endpoints import router
from .middleware import JWTAuthenticationMiddleware

__all__ = [
    "router",
    "JWTAuthenticationMiddleware",
    "IntegrationConfig",
]
