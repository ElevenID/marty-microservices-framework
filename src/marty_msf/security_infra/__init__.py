"""
Security Infrastructure Module

Provides service mesh, middleware, and platform integration implementations.
"""

# Import from new implementations
from .implementations import (
    BasicSessionManager,
    SecurityContextManager,
    SecurityDecorator,
    SecurityMiddleware,
    ServiceMeshSecurityManager,
    require_authentication,
    require_permission,
    require_role,
)

__all__ = [
    "BasicSessionManager",
    "SecurityMiddleware",
    "ServiceMeshSecurityManager",
    "SecurityDecorator",
    "SecurityContextManager",
    "require_permission",
    "require_role",
    "require_authentication",
]

__all__ = []
