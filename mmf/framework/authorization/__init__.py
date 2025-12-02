"""
Authorization Framework Public API.

This module exports the core components of the authorization framework,
following the Hexagonal Architecture pattern.
"""

from mmf.framework.authorization.adapters.abac_engine import (
    ABACContext,
    ABACManager,
    ABACPolicy,
)
from mmf.framework.authorization.adapters.enforcement import (
    require_permission,
    require_role,
)
from mmf.framework.authorization.adapters.rbac_engine import RBACManager, Role
from mmf.framework.authorization.domain.models import (
    IAuthorizationEngine,
    IPolicyRepository,
    Permission,
    PermissionAction,
    ResourceType,
)

__all__ = [
    "Permission",
    "PermissionAction",
    "ResourceType",
    "IAuthorizationEngine",
    "IPolicyRepository",
    "RBACManager",
    "Role",
    "ABACManager",
    "ABACPolicy",
    "ABACContext",
    "require_permission",
    "require_role",
]


__all__ = [
    "Permission",
    "PermissionAction",
    "ResourceType",
    "IAuthorizationEngine",
    "IPolicyRepository",
    "RBACManager",
    "Role",
    "ABACManager",
    "ABACPolicy",
    "ABACContext",
    "require_permission",
    "require_role",
]
