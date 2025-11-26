"""
Authorization Framework Public API.

This module exports the core components of the authorization framework,
following the Hexagonal Architecture pattern.
"""

from mmf_new.framework.authorization.domain.models import (
    Permission,
    PermissionAction,
    ResourceType,
    IAuthorizationEngine,
    IPolicyRepository,
)
from mmf_new.framework.authorization.adapters.rbac_engine import (
    RBACManager,
    Role,
)
from mmf_new.framework.authorization.adapters.abac_engine import (
    ABACManager,
    ABACPolicy,
    ABACContext,
)
from mmf_new.framework.authorization.adapters.enforcement import (
    require_permission,
    require_role,
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
