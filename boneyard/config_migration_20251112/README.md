# Old Configuration Framework - Moved to Boneyard

**Migration Date:** November 12, 2025  
**Reason:** Replaced with new hierarchical configuration system in `mmf_new/config/`

## What Was Moved

This directory contains the old configuration files that were replaced by the new MMF hexagonal architecture configuration system.

### Files Moved:
- `base.yaml` - Old base configuration with mixed service and platform concerns
- `development.yaml` - Old development environment configuration
- `production.yaml` - Old production environment configuration  
- `testing.yaml` - Old testing environment configuration

### Migration Destination:

| Old File | New Location | Improvements |
|----------|-------------|-------------|
| `base.yaml` | `mmf_new/config/base.yaml` | Refactored with clear separation of concerns |
| `development.yaml` | `mmf_new/config/environments/development.yaml` | Environment-specific overrides |
| `production.yaml` | `mmf_new/config/environments/production.yaml` | Enhanced security and production settings |
| `testing.yaml` | `mmf_new/config/environments/testing.yaml` | Optimized for test performance |
| N/A | `mmf_new/config/services/*.yaml` | New service-specific configurations |
| N/A | `mmf_new/config/platform/core.yaml` | New platform-wide configuration |

## Why These Files Were Replaced

The old configuration system had several limitations:

### 🚫 Problems with Old System
1. **Monolithic Structure** - All configurations mixed together
2. **No Service Separation** - One-size-fits-all approach
3. **Limited Secret Management** - Basic environment variable support only
4. **No Platform Configuration** - Cross-cutting concerns mixed with service config
5. **Poor Type Safety** - Dictionary-based access without validation
6. **Inflexible Hierarchy** - Limited override capabilities

### ✅ New System Benefits
1. **Hierarchical Configuration** - Base → Platform → Environment → Service
2. **Service-Specific Configs** - Each service can have its own configuration
3. **Advanced Secret Management** - Multiple backends with `${SECRET:key}` syntax
4. **Platform Separation** - Clear separation of platform and service concerns
5. **Type-Safe Access** - Structured dataclasses with IDE support
6. **Flexible Overrides** - Deep merging with clear precedence rules

## Migration Impact

### Backward Compatibility
- ❌ **Not backward compatible** - New configuration system requires code changes
- ✅ **Migration path provided** - Clear documentation and examples in `mmf_new/config/README.md`
- ✅ **Feature parity** - All old functionality replicated in new system

### Services Affected
- All services that previously used `config/` files
- Services should be migrated to use new configuration system
- Examples provided for `identity-service` and `api-gateway`

## How to Use Old Configuration (Not Recommended)

If you need to reference the old configuration temporarily:

```python
# Old way (deprecated)
import yaml
with open('boneyard/config_migration_20251112/base.yaml') as f:
    old_config = yaml.safe_load(f)
```

## Recommended Migration Path

Use the new configuration system:

```python
# New way (recommended)
from mmf_new.core.infrastructure.config import load_service_configuration

config = load_service_configuration(
    service_name='your-service',
    environment='development'
)
```

See `mmf_new/config/README.md` for complete documentation.

## Files in This Directory

```
boneyard/config_migration_20251112/
├── README.md                 # This file
├── base.yaml                 # Old base configuration
├── development.yaml          # Old development configuration
├── production.yaml           # Old production configuration
└── testing.yaml              # Old testing configuration
```

## Related Migrations

- **Framework Migration (2025-11-06)**: `boneyard/framework_migration_20251106/`
- **Database Infrastructure (2024-11-10)**: `boneyard/database_infrastructure_migration_20241110/`
- **CLI Generators (2025-11-09)**: `boneyard/cli_generators_migration_20251109/`

---

**⚠️ Important:** These files are preserved for reference only. Use the new configuration system in `mmf_new/config/` for all new development.