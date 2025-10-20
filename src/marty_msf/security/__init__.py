"""
Enhanced Security Framework for Marty Microservices Framework

Provides comprehensive security features following a clean level contract architecture:

Core Architecture:
- Level Contract principle: Clean layered dependencies (api -> implementations -> bootstrap)
- Dependency Inversion: Implementations depend on abstractions, not concrete classes
- No circular dependencies by design
- Pluggable authentication, authorization, and secret management

New Modular Components:
- security.api: Core interfaces and contracts (foundation layer)
- security.auth_impl: Authentication implementations (BasicAuthenticator, JwtAuthenticator, etc.)
- security.authz_impl: Authorization implementations (RoleBasedAuthorizer, PermissionBasedAuthorizer, etc.)
- security.secrets_impl: Secret management implementations (EnvironmentSecretManager, FileSecretManager, etc.)
- security.bootstrap: Composition root for wiring components together

Legacy Components (maintained for backward compatibility):
- Existing RBAC, ABAC, audit, and policy engine components
- Original decorators and authentication managers
- UnifiedSecurityFramework (being phased out in favor of modular approach)

Migration Path:
- New applications should use the bootstrap module and interfaces
- Existing applications can continue using legacy components during transition
- Gradual migration path available through compatibility layer
"""

import logging

# New modular security architecture
from . import policy_engines

# Legacy components (maintained for backward compatibility)
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
from .api import (  # Core interfaces; Data models; Enums; Exceptions; Abstract base classes
    AbstractAuthenticator,
    AbstractAuthorizer,
    AbstractSecretManager,
    AuthenticationError,
    AuthenticationMethod,
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationError,
    AuthorizationResult,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ISecretManager,
    PermissionAction,
    SecretManagerError,
    SecurityError,
    User,
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

# Audit implementations
from .audit_impl import (
    CompositeAuditor,
    FileAuditor,
    FilteringAuditor,
    NoOpAuditor,
    StructuredAuditor,
    create_default_auditor,
)

# Authentication implementations
from .auth_impl import BasicAuthenticator, EnvironmentAuthenticator, JwtAuthenticator
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

# Authorization implementations
from .authz_impl import (
    AttributeBasedAuthorizer,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
)

# Bootstrap and composition root
from .bootstrap import (
    SecurityBootstrap,
    configure_security_in_container,
    create_default_security_system,
    create_development_security_system,
    create_production_security_system,
    create_testing_security_system,
    get_security_components_from_container,
)

# Compatibility bridge
from .bridge import UnifiedSecurityFrameworkBridge

# Caching implementations
from .caching import AdvancedCache, InMemoryCacheManager, SecurityCacheManager
from .exceptions import (
    AccountLockedError,
    ClaimsVerificationError,
    ExternalProviderError,
    PermissionDeniedError,
    PolicyEvaluationError,
    RateLimitExceededError,
    RoleRequiredError,
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
from .rbac import Permission, RBACManager, ResourceType, Role

# Secret management implementations
from .secrets_impl import (
    CompositeSecretManager,
    EnvironmentSecretManager,
    FileSecretManager,
    InMemorySecretManager,
)

# Session management implementations
from .sessions import InMemorySessionManager, NoOpSessionManager

logger = logging.getLogger(__name__)


__all__ = [
    # New modular architecture - Core interfaces
    "IAuthenticator",
    "IAuthorizer",
    "ISecretManager",
    "IAuditor",

    # New modular architecture - Data models
    "User",
    "AuthenticationResult",
    "AuthorizationContext",
    "AuthorizationResult",

    # New modular architecture - Enums
    "AuthenticationMethod",
    "PermissionAction",

    # New modular architecture - Bootstrap
    "SecurityBootstrap",
    "create_default_security_system",
    "create_development_security_system",
    "create_testing_security_system",
    "create_production_security_system",
    "configure_security_in_container",
    "get_security_components_from_container",

    # New modular architecture - Authentication implementations
    "BasicAuthenticator",
    "JwtAuthenticator",
    "EnvironmentAuthenticator",

    # New modular architecture - Authorization implementations
    "RoleBasedAuthorizer",
    "PermissionBasedAuthorizer",
    "AttributeBasedAuthorizer",

    # New modular architecture - Secret management implementations
    "EnvironmentSecretManager",
    "FileSecretManager",
    "InMemorySecretManager",
    "CompositeSecretManager",

    # New modular architecture - Abstract base classes
    "AbstractAuthenticator",
    "AbstractAuthorizer",
    "AbstractSecretManager",

    # Legacy components (maintained for backward compatibility)
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
    "SecretManagerError",

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
