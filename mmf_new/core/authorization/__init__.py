"""
Authorization Module for MMF New

Comprehensive authorization system including:
- Role-Based Access Control (RBAC)
- Attribute-Based Access Control (ABAC)
- Permission-Based Authorization
- Policy Engines (Builtin, ACL, OPA, OSO)
- Security Decorators
- Caching

Example usage:

    # Using decorators
    from mmf_new.core.authorization import require_role, require_permission

    @require_role("admin")
    def admin_only_function():
        pass

    @require_permission("service:user-service:read")
    def read_user_service():
        pass

    # Using authorizers directly
    from mmf_new.core.authorization import (
        create_role_based_authorizer,
        AuthorizationContext,
        User
    )

    authorizer = create_role_based_authorizer()
    context = AuthorizationContext(
        user=User(id="user123", username="john", roles=["admin"]),
        resource="user-service",
        action="read"
    )
    result = authorizer.authorize(context)
    if result.allowed:
        # Proceed with action
        pass
"""

# ABAC
from .abac import (
    ABACManager,
    ABACPolicy,
    AttributeCondition,
    get_abac_manager,
)

# Core API - Interfaces and Data Models
from .api import (
    AttributeType,
    AuthorizationContext,
    AuthorizationResult,
    ConditionOperator,
    IAuthorizer,
    Permission,
    PermissionAction,
    PolicyEffect,
    ResourceType,
    User,
)

# Authorizer Implementations
from .bootstrap import (
    AttributeBasedAuthorizer,
    CompositeAuthorizer,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
    create_attribute_based_authorizer,
    create_composite_authorizer,
    create_permission_based_authorizer,
    create_role_based_authorizer,
)

# Cache Management
from .cache import AuthorizationCacheManager, create_authorization_cache

# Configuration
from .config import AuthorizationConfig, get_default_config

# Decorators
from .decorators import (
    CurrentUserService,
    SecurityContext,
    require_abac,
    require_any_role,
    require_authenticated,
    require_permission,
    require_rbac,
    require_role,
)

# Policy Engines
from .engines import (
    AbstractPolicyEngine,
    ACLPolicyEngine,
    BuiltinPolicyEngine,
    OPAPolicyEngine,
    OsoPolicyEngine,
)
from .engines import SecurityContext as EngineSecurityContext
from .engines import (
    SecurityDecision,
)

# RBAC
from .rbac import Permission as RBACPermission
from .rbac import (
    RBACManager,
    Role,
    get_rbac_manager,
)

__all__ = [
    # Core API
    "IAuthorizer",
    "User",
    "AuthorizationContext",
    "AuthorizationResult",
    "Permission",
    "PermissionAction",
    "ResourceType",
    "PolicyEffect",
    "ConditionOperator",
    "AttributeType",
    # Configuration
    "AuthorizationConfig",
    "get_default_config",
    # Cache
    "AuthorizationCacheManager",
    "create_authorization_cache",
    # RBAC
    "RBACPermission",
    "Role",
    "RBACManager",
    "get_rbac_manager",
    # ABAC
    "ABACManager",
    "ABACPolicy",
    "AttributeCondition",
    "get_abac_manager",
    # Authorizer Implementations
    "RoleBasedAuthorizer",
    "PermissionBasedAuthorizer",
    "AttributeBasedAuthorizer",
    "CompositeAuthorizer",
    "create_role_based_authorizer",
    "create_permission_based_authorizer",
    "create_attribute_based_authorizer",
    "create_composite_authorizer",
    # Decorators
    "require_authenticated",
    "require_role",
    "require_permission",
    "require_any_role",
    "require_rbac",
    "require_abac",
    "SecurityContext",
    "CurrentUserService",
    # Policy Engines
    "AbstractPolicyEngine",
    "BuiltinPolicyEngine",
    "ACLPolicyEngine",
    "OPAPolicyEngine",
    "OsoPolicyEngine",
    "SecurityDecision",
    "EngineSecurityContext",
]
