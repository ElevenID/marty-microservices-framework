"""
Security Decorators - Compatibility Layer

This module provides a compatibility layer for security decorators.
It re-exports all functionality from the new modular decorator system.
"""

# Re-export all decorators from the new implementation
from .new_decorators import (
    SecurityContext,
    get_current_user,
    requires_abac,
    requires_any_role,
    requires_auth,
    requires_permission,
    requires_rbac,
    requires_role,
    verify_jwt_token,
)

__all__ = [
    "SecurityContext",
    "get_current_user",
    "requires_abac",
    "requires_any_role",
    "requires_auth",
    "requires_permission",
    "requires_rbac",
    "requires_role",
    "verify_jwt_token",
]
