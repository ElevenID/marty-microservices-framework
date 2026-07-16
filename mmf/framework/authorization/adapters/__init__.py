"""Authorization adapters - concrete implementations of port interfaces."""

from mmf.framework.authorization.adapters.abac_engine import (
    ABACManager,
    ABACManagerService,
    ABACPolicy,
    ABACPolicyEvaluator,
    AttributeCondition,
    InMemoryPolicyCache,
    InMemoryPolicyRepository,
)
from mmf.framework.authorization.adapters.enforcement import (
    CurrentUserService,
    SecurityContext,
)
from mmf.framework.authorization.adapters.rbac_engine import (
    RBACManager,
    RBACManagerService,
    Role,
)

__all__ = [
    # ABAC Engine
    "ABACManager",
    "ABACManagerService",
    "ABACPolicy",
    "ABACPolicyEvaluator",
    "AttributeCondition",
    "InMemoryPolicyCache",
    "InMemoryPolicyRepository",
    # Enforcement
    "CurrentUserService",
    "SecurityContext",
    # RBAC Engine
    "RBACManager",
    "RBACManagerService",
    "Role",
]
