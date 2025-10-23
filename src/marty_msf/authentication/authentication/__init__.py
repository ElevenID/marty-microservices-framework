"""
Authentication Module

This module provides authentication management and utilities for the security framework.
"""

from ..decorators import (
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
from .manager import AuthenticationManager

__all__ = [
    "AuthenticationManager",
    "requires_auth",
    "requires_role",
    "requires_permission",
    "requires_any_role",
    "requires_rbac",
    "requires_abac",
    "verify_jwt_token",
    "SecurityContext",
    "get_current_user"
]
