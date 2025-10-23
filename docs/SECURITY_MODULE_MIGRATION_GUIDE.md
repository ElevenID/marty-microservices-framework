# Security Module Migration Guide

## Overview

The security module has been restructured into specialized modules for better separation of concerns and maintainability. This guide helps you migrate your code to use the new modular structure.

## New Module Structure

### Before (Deprecated)
```python
from marty_msf.security import *
from marty_msf.security.api import IAuthenticator, User
from marty_msf.security.bootstrap import SecurityBootstrap
```

### After (Recommended)
```python
# Core interfaces and configuration
from marty_msf.security_core import IAuthenticator, User, SecurityBootstrap

# Authentication functionality
from marty_msf.authentication import BasicAuthenticator, JwtAuthenticator

# Authorization functionality
from marty_msf.authorization import RoleBasedAuthorizer, requires_role

# Auditing and compliance
from marty_msf.audit_compliance import SecurityAuditor, SecurityEventManager

# Infrastructure and middleware
from marty_msf.security_infra import AuthMiddleware, SecurityHeadersMiddleware

# Threat management
from marty_msf.threat_management import ThreatDetector, SecurityScanner
```

## Module Responsibilities

### 1. `security_core/`
**Purpose**: Core interfaces, configuration, and canonical functions
- Core interfaces (IAuthenticator, IAuthorizer, IAuditor)
- Security models (User, AuthenticationResult, etc.)
- Bootstrap and configuration
- Exception classes

### 2. `authentication/`
**Purpose**: User authentication implementations
- Authentication managers and providers
- Session management
- Authentication implementations (Basic, JWT, OAuth2, etc.)

### 3. `authorization/`
**Purpose**: Access control and authorization
- Authorization engines (RBAC, ABAC, ACL)
- Policy evaluation
- Permission decorators
- Caching for authorization decisions

### 4. `audit_compliance/`
**Purpose**: Security auditing and compliance
- Audit implementations and sinks
- Security event management
- Compliance scanning and reporting
- Security monitoring

### 5. `security_infra/`
**Purpose**: Platform integration and middleware
- Service mesh security (Istio, Linkerd)
- Security middleware
- Zero trust implementations
- Platform-specific policies

### 6. `threat_management/`
**Purpose**: Security operations and threat detection
- Threat detection and analysis
- Security scanning
- Rate limiting
- Security tools and utilities

### 7. `crypto_secrets/` *(Future)*
**Purpose**: Cryptography and secrets management
- Encryption services
- Key management
- Secrets storage and rotation

## Migration Strategy

### Recommended Approach: Direct Migration
Update imports to use new modules directly for clean, fail-fast behavior:

```python
# Recommended migration - fail fast approach
from marty_msf.security_core import IAuthenticator, User
from marty_msf.authentication import BasicAuthenticator
from marty_msf.authorization import requires_role
```

### Why Fail Fast?
- **Clear dependencies**: Import errors immediately reveal missing functionality
- **No hidden issues**: Problems surface early in development
- **Better debugging**: Clear error messages show exactly what's missing
- **Cleaner code**: No fallback logic cluttering imports

### Legacy Support
The original `marty_msf.security` module maintains backward compatibility and will continue to work during the transition period, but new code should use the modular imports directly.

## Common Migration Patterns

### Authentication Code
```python
# Before
from marty_msf.security import BasicAuthenticator, JwtAuthenticator
from marty_msf.security.factory import get_security_factory

# After
from marty_msf.authentication import BasicAuthenticator, JwtAuthenticator
from marty_msf.authentication import get_security_factory
```

### Authorization Code
```python
# Before
from marty_msf.security import requires_role, requires_permission
from marty_msf.security.decorators import requires_auth

# After
from marty_msf.authorization import requires_role, requires_permission
from marty_msf.authorization import requires_auth
```

### Audit Code
```python
# Before
from marty_msf.security.events import SecurityEventManager
from marty_msf.security.status import SecurityStatusReporter

# After
from marty_msf.audit_compliance import SecurityEventManager
from marty_msf.audit_compliance import SecurityStatusReporter
```

### Infrastructure Code
```python
# Before
from marty_msf.security.middleware import AuthMiddleware
from marty_msf.security.mesh import IstioSecurity

# After
from marty_msf.security_infra import AuthMiddleware
from marty_msf.security_infra import IstioSecurity
```

## Backward Compatibility

The original `marty_msf.security` module maintains backward compatibility by:

1. **Deprecation warnings**: Alerts developers about the new structure
2. **Import delegation**: Automatically imports from new modules where available
3. **Graceful fallbacks**: Handles missing components during transition

## Migration Checklist

- [ ] Update imports to use new modular structure
- [ ] Test that all functionality still works
- [ ] Remove fallback imports once confident
- [ ] Update documentation and examples
- [ ] Run tests to ensure no regressions

## Breaking Changes

### Removed Deprecations
- Some internal modules may have been consolidated
- Import paths have changed for specialized functionality
- Wildcard imports (`from marty_msf.security import *`) are discouraged

### New Requirements
- More explicit imports required
- Better separation of concerns in your code
- May need to import from multiple modules for complex functionality

## Benefits

### For Developers
- **Clearer dependencies**: Know exactly what functionality you're using
- **Better IDE support**: More precise autocomplete and error detection
- **Reduced coupling**: Modules have clear responsibilities
- **Easier testing**: Test specific functionality in isolation

### For Architecture
- **Separation of concerns**: Each module has a single responsibility
- **Maintainability**: Easier to modify and extend specific functionality
- **Performance**: Only import what you need
- **Layer contracts**: Clean dependencies between modules

## Troubleshooting

### Import Errors
If you get import errors, check:
1. Are you using the correct new module path?
2. Is the functionality available in the new structure?
3. Do you need a fallback import during transition?

### Missing Functionality
Some functionality may have moved or been renamed:
1. Check the new module structure above
2. Look for similar functionality in related modules
3. Consult the API documentation for the new modules

### Performance Issues
If you notice performance degradation:
1. Remove wildcard imports (`import *`)
2. Import only what you need
3. Check for circular dependencies

## Examples

See the `examples/` directory for updated examples using the new modular structure:
- `examples/security/basic_security_example.py`
- `examples/security_recovery_demo_fixed.py`
- `examples/security_level_contract_example.py`

## Support

For questions or issues with migration:
1. Check this guide first
2. Review the module documentation
3. Look at the updated examples
4. File an issue if you find problems

The migration is designed to be gradual and safe, with backward compatibility maintained during the transition period.
