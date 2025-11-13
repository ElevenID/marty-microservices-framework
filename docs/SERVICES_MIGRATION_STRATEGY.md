# Services Migration Strategy: Eliminate Templates, Migrate Real Services

## Executive Summary

The `services/` directory contains mostly **service templates and generators** (Jinja2 `.j2` files) that are no longer needed. We are **simplifying the framework by eliminating the generator system entirely**. Only real service implementations will be migrated to `mmf_new/`. This follows our successful "copy and refactor" approach used for mmf integration files and middleware.

## Current State Analysis

### services/ Directory Structure

```
services/
├── fastapi/              # FastAPI service templates (.j2)
│   ├── unified_fastapi_service.py
│   ├── fastapi_service/
│   ├── fastapi-service/
│   ├── production-service/
│   └── simple-fastapi-service/
├── grpc/                 # gRPC service templates (.j2)
│   └── grpc_service/
├── hybrid/               # Hybrid service templates (.j2)
│   └── hybrid_service/
└── shared/               # Shared templates and real services
    ├── modern_service_template.py    # Template file (not .j2)
    ├── unified_service_template.py   # Template file (not .j2)
    ├── api-gateway-service/          # Real service implementation
    ├── api-versioning/               # Real service implementation
    ├── auth_service/                 # Template service (.j2)
    ├── caching_service/              # Template service (.j2)
    ├── database_service/             # Template service (.j2)
    ├── message_queue_service/        # Template service (.j2)
    ├── morty_service/                # ✅ REAL SERVICE (hexagonal architecture)
    ├── go-service/                   # Go service template
    ├── java-service/                 # Java service template
    ├── nodejs-service/               # Node.js service template
    ├── saga-orchestrator/            # Real/template service
    └── service-discovery/            # Real/template service
```

### mmf_new/ Current Structure

```
mmf_new/
├── services/
│   └── identity/         # ✅ Already migrated (hexagonal architecture)
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── integration/
├── core/
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── config/
├── examples/
└── tests/
```

### Framework Context

The framework previously had service generation systems in the boneyard:

- `boneyard/cli_generators_migration_20251109/` - Old generator system (already archived)
- Service templates and generators are no longer part of the framework
- **New approach:** Manual service creation following hexagonal architecture patterns from examples

### Simplification Rationale

**Why eliminate templates and generators:**

1. **Complexity:** Template systems add maintenance overhead
2. **Flexibility:** Developers can copy and adapt real examples more easily
3. **Learning:** Understanding hexagonal architecture by studying real code is better than generated code
4. **Maintenance:** Less code to maintain means fewer bugs
5. **Modern practices:** Most frameworks (NestJS, Spring Boot, etc.) provide examples, not generators

**What developers should use instead:**

- Copy `mmf_new/services/identity/` as a reference implementation
- Follow hexagonal architecture patterns documented in examples
- Use IDE features (copilot, snippets) for boilerplate code

## Migration Strategy: Archive All Templates

### Phase 1: Archive All Template Directories

**Actions:**

1. **Archive FastAPI Templates**

   ```bash
   git mv services/fastapi boneyard/service_templates_fastapi_20251113
   ```

2. **Archive gRPC Templates**

   ```bash
   git mv services/grpc boneyard/service_templates_grpc_20251113
   ```

3. **Archive Hybrid Templates**

   ```bash
   git mv services/hybrid boneyard/service_templates_hybrid_20251113
   ```

4. **Archive Shared Template Services**

   ```bash
   # Archive .j2 template services
   git mv services/shared/auth_service boneyard/service_templates_shared_20251113/
   git mv services/shared/caching_service boneyard/service_templates_shared_20251113/
   git mv services/shared/database_service boneyard/service_templates_shared_20251113/
   git mv services/shared/message_queue_service boneyard/service_templates_shared_20251113/

   # Archive non-Python templates
   git mv services/shared/go-service boneyard/service_templates_shared_20251113/
   git mv services/shared/java-service boneyard/service_templates_shared_20251113/
   git mv services/shared/nodejs-service boneyard/service_templates_shared_20251113/

   # Archive template Python files
   git mv services/shared/modern_service_template.py boneyard/service_templates_shared_20251113/
   git mv services/shared/unified_service_template.py boneyard/service_templates_shared_20251113/
   ```

### Phase 2: Migrate Real Services to mmf_new

**Real services to migrate:**

- `morty_service` → `mmf_new/services/morty/`
- `api-gateway-service` → `mmf_new/services/gateway/`
- `api-versioning` → `mmf_new/services/versioning/`
- `saga-orchestrator` → Evaluate if real service, then migrate or archive
- `service-discovery` → Evaluate if real service, then migrate or archive

### Phase 3: Update Documentation

**Actions:**

1. Remove references to template generation from README
2. Add "Creating New Services" guide referencing mmf_new/services/identity as example
3. Document hexagonal architecture patterns
4. Remove template validation scripts

## Recommended Migration Plan

### Phase 1: Analyze and Identify Real Services (15 min)

1. **Identify Real Service Implementations**
   - `morty_service` - ✅ Real hexagonal service
   - `api-gateway-service` - Check if real or template
   - `api-versioning` - Check if real or template
   - `saga-orchestrator` - Check if real or template
   - `service-discovery` - Check if real or template

2. **Verify Services are Not Templates**
   - Look for `.j2` files (templates)
   - Check for actual business logic vs placeholder code
   - Verify tests exist

### Phase 2: Archive All Templates (30 min)

Execute git moves to boneyard for all template directories and files:

```bash
# Archive all template directories
git mv services/fastapi boneyard/service_templates_20251113/fastapi
git mv services/grpc boneyard/service_templates_20251113/grpc
git mv services/hybrid boneyard/service_templates_20251113/hybrid

# Archive shared template services (ones with .j2 files)
mkdir -p boneyard/service_templates_20251113/shared
git mv services/shared/auth_service boneyard/service_templates_20251113/shared/
git mv services/shared/caching_service boneyard/service_templates_20251113/shared/
git mv services/shared/database_service boneyard/service_templates_20251113/shared/
git mv services/shared/message_queue_service boneyard/service_templates_20251113/shared/

# Archive language templates
git mv services/shared/go-service boneyard/service_templates_20251113/shared/
git mv services/shared/java-service boneyard/service_templates_20251113/shared/
git mv services/shared/nodejs-service boneyard/service_templates_20251113/shared/

# Archive Python template files
git mv services/shared/modern_service_template.py boneyard/service_templates_20251113/shared/
git mv services/shared/unified_service_template.py boneyard/service_templates_20251113/shared/
```

**Git Commit:**

```bash
git add -A
git commit -m "Archive service templates to boneyard

Eliminating template generation system to simplify framework.

Archived:
- services/fastapi/ - All FastAPI service templates (.j2)
- services/grpc/ - All gRPC service templates (.j2)
- services/hybrid/ - All hybrid service templates (.j2)
- services/shared/*_service/ - Template services with .j2 files
- services/shared/go-service/, java-service/, nodejs-service/ - Language templates
- services/shared/modern_service_template.py, unified_service_template.py

Rationale:
- Template generation adds complexity and maintenance overhead
- Developers learn better by copying real examples (mmf_new/services/identity/)
- IDE features (copilot, snippets) handle boilerplate better than generators
- Modern frameworks favor examples over code generation
- Generator system already archived in boneyard/cli_generators_migration_20251109/

Real services (not templates) remain in services/ for migration:
- morty_service, api-gateway-service, api-versioning, etc."
```

### Phase 3: Migrate Real Services (1-2 hours per service)

For each real service:

1. **Create mmf_new structure**

   ```
   mmf_new/services/{service_name}/
   ├── domain/
   │   ├── __init__.py
   │   └── models.py
   ├── application/
   │   ├── __init__.py
   │   └── usecases.py
   ├── infrastructure/
   │   ├── __init__.py
   │   └── adapters/
   └── integration/
       ├── __init__.py
       ├── routes.py
       └── middleware.py
   ```

2. **Copy and refactor code**
   - Change imports from `marty_msf.framework` to `mmf_new.core`
   - Apply hexagonal architecture patterns
   - Separate domain, application, infrastructure, integration

3. **Update configuration**
   - Use mmf_new's config system
   - Update environment variables

4. **Test and validate**
   - Run existing tests
   - Fix any import issues
   - Ensure functionality preserved

### Phase 4: Clean Up Remaining Artifacts (30 min)

1. **Remove Template Validation Scripts**

   ```bash
   # If scripts/dev/validate_templates.py is only for service templates
   git rm scripts/dev/validate_templates.py
   ```

2. **Remove Template References**
   - Update main README
   - Remove generator documentation
   - Add "Creating Services" guide pointing to examples

3. **Final Cleanup**

   ```bash
   # Remove empty services/ directory if all templates archived and services migrated
   # Only if nothing left in services/
   git rm -r services/
   ```

### Phase 5: Update Documentation (30 min)

1. **Create New Service Creation Guide**
   - Location: `docs/guides/CREATING_NEW_SERVICES.md`
   - Content: How to copy and adapt mmf_new/services/identity/ as template
   - Include hexagonal architecture explanation

2. **Update Main README**
   - Remove references to service generators
   - Add link to new service creation guide
   - Emphasize example-based approach

3. **Update CHANGELOG**
   - Document removal of template system
   - Explain new approach

## Service-by-Service Migration Details

### morty_service (PRIORITY 1)

**Current state:** Hexagonal architecture, uses `marty_msf.framework`

**Migration:**

```python
# OLD imports
from marty_msf.framework.config_factory import create_service_config
from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.monitoring import setup_fastapi_monitoring

# NEW imports (after migration)
from mmf_new.core.application.config import create_service_config
from mmf_new.core.infrastructure.logging import UnifiedServiceLogger
from mmf_new.core.infrastructure.monitoring import setup_fastapi_monitoring
```

**Target:** `mmf_new/services/morty/`

### api-gateway-service (PRIORITY 2)

**Current state:** Real service, needs hexagonal refactoring

**Migration:**

1. Extract domain models (Gateway, Route, etc.)
2. Create use cases (RouteRequest, LoadBalance, etc.)
3. Move FastAPI logic to integration layer
4. Adapt external dependencies in infrastructure

**Target:** `mmf_new/services/gateway/`

### api-versioning (PRIORITY 3)

**Current state:** Real service, needs hexagonal refactoring

**Migration:** Similar to api-gateway-service

**Target:** `mmf_new/services/versioning/`

## Import Mapping Guide

### Configuration

```python
# OLD
from marty_msf.framework.config_factory import create_service_config
from marty_msf.framework.config import UnifiedConfigurationManager

# NEW
from mmf_new.core.application.config import ServiceConfig
from mmf_new.core.infrastructure.config import MMFConfiguration
```

### Database

```python
# OLD
from marty_msf.framework.database import DatabaseManager

# NEW
from mmf_new.core.infrastructure.database import DatabaseManager
```

### Logging & Monitoring

```python
# OLD
from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.monitoring import setup_fastapi_monitoring

# NEW
from mmf_new.core.infrastructure.logging import UnifiedServiceLogger
from mmf_new.core.infrastructure.monitoring import MetricsCollector
```

## Success Criteria

- [ ] All service templates archived to boneyard
- [ ] Template validation scripts removed or archived
- [ ] All real services migrated to mmf_new with hexagonal architecture
- [ ] All tests passing after migration
- [ ] Documentation updated to remove generator references
- [ ] New "Creating Services" guide created
- [ ] No references to template generation in main README
- [ ] services/ directory removed (if empty after migration)
- [ ] Git commits with detailed explanations

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing services that use templates | High | Archive templates, don't delete; can restore if needed |
| Developers confused without generators | Medium | Create clear guide showing how to copy identity service |
| Import path changes break services | High | Migrate one service at a time, test thoroughly |
| Configuration incompatibility | Medium | Use mmf_new's config system, create helpers if needed |

## Template Archive Inventory

### What Gets Archived

**FastAPI Templates:**

- `services/fastapi/unified_fastapi_service.py`
- `services/fastapi/fastapi_service/` (.j2 templates)
- `services/fastapi/fastapi-service/` (.j2 templates)
- `services/fastapi/production-service/` (.j2 templates)
- `services/fastapi/simple-fastapi-service/` (.j2 templates)

**gRPC Templates:**

- `services/grpc/grpc_service/` (.j2 templates)

**Hybrid Templates:**

- `services/hybrid/hybrid_service/` (.j2 templates)

**Shared Templates:**

- `services/shared/auth_service/` (.j2 templates)
- `services/shared/caching_service/` (.j2 templates)
- `services/shared/database_service/` (.j2 templates)
- `services/shared/message_queue_service/` (.j2 templates)
- `services/shared/go-service/` (Go templates)
- `services/shared/java-service/` (Java templates)
- `services/shared/nodejs-service/` (Node.js templates)
- `services/shared/modern_service_template.py`
- `services/shared/unified_service_template.py`

**Template Configuration:**

- `services/shared/service_config_template.yaml`

### What Gets Migrated (Real Services)

- `services/shared/morty_service/` → `mmf_new/services/morty/`
- `services/shared/api-gateway-service/` → `mmf_new/services/gateway/` (if real)
- `services/shared/api-versioning/` → `mmf_new/services/versioning/` (if real)
- `services/shared/saga-orchestrator/` → Evaluate then migrate or archive
- `services/shared/service-discovery/` → Evaluate then migrate or archive
- `services/shared/config-service/` → Evaluate then migrate or archive

## Next Steps

1. **Execute Phase 1:** Analyze services directory to identify real vs template services
2. **Execute Phase 2:** Archive all templates to boneyard with git commit
3. **Execute Phase 3:** Migrate morty_service first as proof of concept
4. **Test thoroughly:** Ensure morty_service works after migration
5. **Iterate:** Continue migrating remaining real services
6. **Execute Phase 4:** Clean up template artifacts
7. **Execute Phase 5:** Update documentation

## Quick Start Commands

```bash
# 1. Analyze what needs archiving
find services/ -name "*.j2" -type f | head -20

# 2. Create boneyard directory
mkdir -p boneyard/service_templates_20251113/{fastapi,grpc,hybrid,shared}

# 3. Execute template archival (see Phase 2 for complete commands)
git mv services/fastapi boneyard/service_templates_20251113/

# 4. Migrate first real service
cp -r services/shared/morty_service mmf_new/services/morty
# Then refactor imports and test

# 5. Commit after each phase
git add -A && git commit -m "Archive service templates - Phase 2 complete"
```

## Related Documentation

- `mmf_new/CORE_MIGRATION_GUIDE.md` - Core framework migration patterns
- `boneyard/cli_generators_migration_20251109/` - Old template generation system
- `docs/architecture/hexagonal-architecture.md` - Architecture guidelines (if exists)
- Previous migration: `boneyard/mmf_integration_20251113.py` - Similar pattern used
