# Authorization Module - Migrated to mmf_new

**Migration Date:** November 16, 2025  
**New Location:** `mmf_new/core/authorization/`

## Migration Summary

This authorization module has been successfully migrated to the new `mmf_new` structure following established patterns. The new implementation consolidates and improves upon the original code.

## What Was Migrated

### Core Components
- **RBAC System** → `mmf_new/core/authorization/rbac.py`
  - Role hierarchy with circular dependency detection
  - Permission inheritance and resolution
  - RBACManager with DI integration

- **ABAC System** → `mmf_new/core/authorization/abac.py`
  - Attribute-based policies with complex conditions
  - Policy evaluation engine
  - Support for regex, time ranges, and nested conditions

- **Authorizer Implementations** → `mmf_new/core/authorization/bootstrap.py`
  - RoleBasedAuthorizer
  - PermissionBasedAuthorizer
  - AttributeBasedAuthorizer
  - CompositeAuthorizer (combines multiple strategies)

- **Policy Engines** → `mmf_new/core/authorization/engines/`
  - Builtin JSON policy engine
  - ACL (Access Control List) engine
  - OPA integration (stub)
  - OSO integration (stub)

- **Security Decorators** → `mmf_new/core/authorization/decorators.py`
  - @require_authenticated
  - @require_role
  - @require_permission
  - @require_any_role
  - @require_rbac
  - @require_abac

- **Caching** → `mmf_new/core/authorization/cache.py`
  - Integrated with mmf_new.infrastructure.cache.CacheManager
  - Authorization-specific cache patterns

### Key Improvements

1. **Better Structure** - Clear separation between API, implementation, and subsystems
2. **Infrastructure Reuse** - Uses existing CacheManager instead of custom implementation
3. **Cleaner Imports** - Proper dependency management with relative imports
4. **Factory Functions** - Easy-to-use factory functions for creating authorizers
5. **Comprehensive Exports** - Clean public API in `__init__.py`

## Migration Statistics

- **Total Lines:** ~5,543 lines migrated
- **Files Created:** 14 files
- **Modules:** 
  - Core: api.py, bootstrap.py, cache.py, config.py, decorators.py
  - RBAC: rbac.py (723 lines)
  - ABAC: abac.py (968 lines)
  - Engines: 6 files (base, builtin, acl, opa, oso, __init__)

## Usage in New Location

```python
from mmf_new.core.authorization import (
    require_role,
    require_permission,
    create_role_based_authorizer,
    AuthorizationContext,
    User
)

# Using decorators
@require_role("admin")
def admin_function():
    pass

# Using authorizers directly
authorizer = create_role_based_authorizer()
context = AuthorizationContext(
    user=User(id="user123", username="john", roles=["admin"]),
    resource="user-service",
    action="read"
)
result = authorizer.authorize(context)
```

## Dependencies

The new authorization module:
- ✅ Re-exports from `marty_msf.security_core.api` (not yet migrated)
- ✅ Uses `mmf_new.infrastructure.cache.CacheManager`
- ✅ Uses `marty_msf.core.enhanced_di` (not yet migrated)
- ✅ Imports exceptions from `marty_msf.security_core.exceptions`

## Notes

- The old `authz_impl.py` was deprecated and its best features were consolidated into `bootstrap.py`
- Both `implementations.py` and `authz_impl.py` were merged, taking the cleanest approach from each
- Caching was simplified by leveraging the infrastructure cache instead of custom implementation
- All complex RBAC/ABAC logic was preserved including circular dependency detection

## Do Not Use This Code

This directory is archived. Use the new implementation at:
**`mmf_new/core/authorization/`**
