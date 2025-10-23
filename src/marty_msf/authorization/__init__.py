"""
Authorization Module

Provides authorization and access control implementations.
"""

# Import from new implementations only (skip problematic legacy imports for now)
from .implementations import (
    AttributeBasedAuthorizer,
    CompositeAuthorizer,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
)

__all__ = [
    "RoleBasedAuthorizer",
    "AttributeBasedAuthorizer",
    "PermissionBasedAuthorizer",
    "CompositeAuthorizer",
]
