"""
Security Framework for Marty Microservices Framework

DEPRECATED: This module has been restructured into specialized modules.
New code should import from the specific modules:

- marty_msf.security_core: Core interfaces and configuration
- marty_msf.authentication: Authentication implementations
- marty_msf.authorization: Authorization and access control
- marty_msf.audit_compliance: Auditing and compliance
- marty_msf.security_infra: Infrastructure and middleware
- marty_msf.threat_management: Threat detection and security tools

This module maintains backward compatibility but will be removed in a future version.
"""

import logging
import warnings

from ..audit_compliance.events import SecurityEvent
from ..audit_compliance.monitoring import (
    SecurityEventCollector,
    SecurityMonitoringSystem,
)
from ..authentication.auth import (
    APIKeyAuthenticator,
    AuthenticatedUser,
    JWTAuthenticator,
    MTLSAuthenticator,
)
from ..authorization.decorators import requires_auth, requires_permission, requires_role
from ..security_core import (
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
    SecurityConfig,
    SecurityError,
    SecurityHardeningFramework,
    SecurityServiceFactory,
)
from ..security_core.exceptions import PermissionDeniedError, RoleRequiredError
from ..threat_management.rate_limiting import RateLimiter
from ..threat_management.scanning.scanner import SecurityScanner

# Issue deprecation warning
warnings.warn(
    "The 'marty_msf.security' module is deprecated. "
    "Use the new modular security structure: security_core, authentication, "
    "authorization, audit_compliance, security_infra, threat_management",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)

# Import from new modular structure for backward compatibility
# Core interfaces and configuration (from security_core)
# Events and monitoring (from audit_compliance)

# Authentication (from authentication)

# Authorization (from authorization)

# Additional exceptions

# Middleware components (basic imports)
# Note: Some middleware classes may not be available yet
# Rate limiting and threat management (from threat_management)

# Legacy imports that may still be needed
# These will gradually be phased out
__all__ = [
    # Core interfaces and configuration (from security_core)
    "SecurityConfig",
    "SecurityHardeningFramework",
    "SecurityServiceFactory",
    # Authentication (from authentication)
    "AuthenticatedUser",
    "JWTAuthenticator",
    "APIKeyAuthenticator",
    "MTLSAuthenticator",
    # Authorization (from authorization)
    "requires_auth",
    "requires_role",
    "requires_permission",
    # Events and monitoring (from audit_compliance)
    "SecurityEvent",
    "SecurityEventCollector",
    "SecurityMonitoringSystem",
    # Middleware (from security_infra)
    # "SecurityMiddleware", "AuthMiddleware", "RateLimitMiddleware",
    # Rate limiting and threat management (from threat_management)
    "RateLimiter",
    "SecurityScanner",
    # Exceptions (from security_core)
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "PermissionDeniedError",
    "RoleRequiredError",
    "RateLimitExceededError",
]
