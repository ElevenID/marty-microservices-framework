# Marty Microservices Framework - Architecture Restructure

This project is being restructured from a monolithic security framework to a **hexagonal architecture** with **ports and adapters** pattern, implementing **bounded contexts** and supporting both **service-scope** and **platform-scope** plugins.

## Current State

### Working Code (Keep Running)

- **`mmf/`** - Current working microservices structure with identity service
- **`src/marty_msf/`** - Legacy security framework (authentication, authorization, etc.)

### New Architecture (Under Development)

- **`mmf_new/`** - Minimal example implementing the new hexagonal architecture
- **`platform_core/`** - Cross-cutting contracts (secrets, telemetry, policy)
- **`platform_plugins/`** - Operator-scope infrastructure providers
- **`infrastructure/`** - Cross-service infrastructure
- **`deploy/`** - Deployment configurations

### Deprecated Code

- **`boneyard/`** - Code that has been fully migrated and replaced

## Architecture Vision

```
mmf_new/
├─ services/
│ └─ <BoundedContext>/           # e.g., identity, issuer, verifier
│   ├─ domain/                   # Pure business logic
│   │ ├─ models/                 # Entities, value objects, policies
│   │ └─ contracts/              # Domain-level interfaces
│   ├─ application/              # Use cases and orchestration
│   │ ├─ ports_in/               # Inbound ports (use case interfaces)
│   │ ├─ ports_out/              # Outbound ports (external dependencies)
│   │ ├─ usecases/               # Use case implementations
│   │ └─ policies/               # Application policies
│   ├─ infrastructure/
│   │ └─ adapters/               # All adapters (inbound + outbound)
│   ├─ plugins/                  # Service-scope feature plugins
│   ├─ platform/                 # Platform wiring and DI
│   └─ tests/                    # All test types
│
├─ platform_core/                # Cross-cutting contracts
│ ├─ contracts/                  # Abstract interfaces
│ ├─ policies/                   # Policy frameworks
│ ├─ plugin_api.py              # Plugin base classes
│ └─ registry.py                # Service registry
│
├─ platform_plugins/             # Operator-scope plugins
│ ├─ mesh.istio/                # Service mesh providers
│ ├─ secrets.vault/             # Secret management
│ └─ telemetry.otlp/            # Observability
│
├─ infrastructure/               # Cross-service infrastructure
└─ deploy/                      # Deployment manifests
```

## Migration Strategy

### Phase 1: ✅ Prove the Architecture

- **Status**: COMPLETE
- **Goal**: Create a minimal working example that demonstrates all concepts
- **Deliverable**: `mmf_new/services/identity/` with full TDD test suite

### Phase 2: Expand the Example

- **Status**: NEXT
- **Goal**: Add more use cases and realistic infrastructure adapters
- **Tasks**:
  - Add authorization use cases
  - Create database and HTTP adapters
  - Implement service-scope plugins
  - Connect to platform_core contracts

### Phase 3: Begin Migration

- **Status**: PLANNED
- **Goal**: Start moving functionality from existing code to new architecture
- **Approach**:
  - Migrate piece by piece with full test coverage
  - Keep existing code running during migration
  - Move to boneyard only after full replacement

### Phase 4: Platform Integration

- **Status**: PLANNED
- **Goal**: Implement cross-cutting concerns and platform plugins
- **Tasks**:
  - Complete platform_core contracts
  - Implement platform_plugins for mesh, secrets, telemetry
  - Cross-service infrastructure setup

## Key Principles

### Hexagonal Architecture (Ports & Adapters)

- **Domain**: Pure business logic, no external dependencies
- **Application**: Use cases that orchestrate domain and external world
- **Infrastructure**: Adapters that implement ports and handle I/O
- **Ports**: Abstract interfaces that define contracts

### Test-Driven Development (TDD)

- Domain models driven by unit tests
- Use cases tested in isolation with mocks
- Integration tests verify complete flows
- Contract tests ensure port implementations are correct

### Bounded Contexts

- Each service represents a business capability
- Clear boundaries with explicit interfaces
- Independent deployment and scaling
- Domain-specific languages and models

### Plugin Architecture

- **Service-scope plugins**: Feature extensions within a service
- **Platform-scope plugins**: Infrastructure provider choices
- Clear plugin contracts and lifecycle management
- Runtime composition and configuration

## Current Progress

- ✅ **Boneyard structure** for deprecated code
- ✅ **New directory structure** following hexagonal architecture
- ✅ **Minimal identity service** with complete domain model
- ✅ **Port definitions** for inbound and outbound dependencies
- ✅ **Use case implementation** with proper business logic
- ✅ **Infrastructure adapters** (in-memory for testing)
- ✅ **Comprehensive test suite** (unit, integration, TDD)
- ✅ **Documentation** of architecture and migration strategy

## Running the Minimal Example

```bash
# Install dependencies (adjust as needed)
pip install pytest

# Run all tests for the minimal example
pytest mmf_new/services/identity/tests/

# Run specific test types
pytest mmf_new/services/identity/tests/test_domain_models.py
pytest mmf_new/services/identity/tests/test_authentication_usecases.py
pytest mmf_new/services/identity/tests/test_integration.py
```

## Next Steps

1. **Expand the minimal example**:
   - Add authorization use cases
   - Create realistic database adapters
   - Implement HTTP inbound adapters
   - Add service-scope plugin examples

2. **Platform core development**:
   - Complete contracts for secrets, telemetry, policy
   - Implement plugin loading and lifecycle
   - Create contract test framework

3. **Begin selective migration**:
   - Identify high-value, low-risk components to migrate first
   - Maintain parallel operation during migration
   - Prove each migration with comprehensive tests

4. **Platform plugin implementation**:
   - Service mesh integration (Istio/Linkerd)
   - Secret management (Vault/AWS SSM)
   - Observability (OpenTelemetry)

## Why This Approach

- **De-risk the migration**: Prove architecture before committing
- **Enable parallel development**: Keep existing code working
- **Test-driven quality**: Every component has comprehensive tests
- **Clear progression**: Each phase builds on proven foundations
- **Maintainable code**: Clean boundaries and clear responsibilities
