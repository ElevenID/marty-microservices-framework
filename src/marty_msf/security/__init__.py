"""
Enhanced Security Framework for Marty Microservices Framework

Provides comprehensive security features including:
- JWT authentication with configurable validation
- Role-Based Access Control (RBAC) with hierarchical permissions
- Attribute-Based Access Control (ABAC) with policy evaluation
- Comprehensive audit logging for all security events
- Enhanced decorators with robust error handling
- External policy engine integration (OPA, Casbin)
- Zero Trust architecture support

Key Changes:
- Consolidated multiple duplicate SecurityManager implementations into a single ConsolidatedSecurityManager
- Enhanced decorators with robust error handling for token expiry, malformation, and claims verification
- Comprehensive audit logging for all security events
- Integration with UnifiedSecurityFramework for ABAC and policy evaluation
"""

import logging

from . import policy_engines
from .abac import (
    ABACContext,
    ABACManager,
    ABACPolicy,
    AttributeCondition,
    AttributeType,
    ConditionOperator,
    PolicyEffect,
    PolicyEvaluationResult,
)
from .audit import (
    AuditLevel,
    AuditSink,
    DatabaseAuditSink,
    FileAuditSink,
    SecurityAuditEvent,
    SecurityAuditor,
    SecurityEventType,
    SyslogAuditSink,
)
from .authentication import (
    AuthenticationManager,
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
from .exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ClaimsVerificationError,
    ExternalProviderError,
    PermissionDeniedError,
    PolicyEvaluationError,
    RateLimitExceededError,
    RoleRequiredError,
    SecurityError,
    SecurityErrorType,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMalformedError,
    handle_security_exception,
    require_authentication,
    require_permission,
    require_role,
)
from .manager import (  # Canonical functions - single source of truth for these operations
    audit_security_event,
    authenticate_credentials,
    authorize_principal,
    configure_security_manager,
    get_security_manager,
)
from .policy_engines import (
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    configure_opa_service,
    configure_policy_service,
    create_policy_service_from_service_config,
    evaluate_policy,
    get_policy_service,
)
from .rbac import Permission, PermissionAction, RBACManager, ResourceType, Role

logger = logging.getLogger(__name__)


__all__ = [
    # Authentication
    "get_security_manager",
    "configure_security_manager",
    # Canonical functions - single source of truth
    "authenticate_credentials",
    "authorize_principal",
    "audit_security_event",
    "SecurityContext",
    "requires_auth",
    "requires_role",
    "requires_permission",
    "requires_rbac",
    "requires_abac",
    "get_current_user",

    # Exceptions
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "PolicyEvaluationError",
    "ExternalProviderError",

    # RBAC
    "Permission",
    "Role",
    "RBACManager",

    # ABAC
    "AttributeCondition",
    "ABACPolicy",
    "ABACManager",
    "ABACContext",
    "PolicyEffect",

    # Audit
    "SecurityAuditEvent",
    "SecurityAuditor",
    "AuditSink",
    "FileAuditSink",
    "SyslogAuditSink",

    # Policy Engine (OPA)
    "get_policy_service",
    "create_policy_service_from_service_config",
    "configure_policy_service",
    "configure_opa_service",
    "evaluate_policy",
    "PolicyEvaluationRequest",
    "PolicyEvaluationResponse",
    "policy_engines"
]
