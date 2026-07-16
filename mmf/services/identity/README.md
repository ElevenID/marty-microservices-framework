# Minimal Identity Service - Hexagonal Architecture Example

This directory contains a **minimal working example** of the new hexagonal architecture (ports and adapters) for the Marty Microservices Framework. It demonstrates the core concepts with a simple identity service that handles authentication.

## Architecture Overview

This example follows the hexagonal architecture pattern with clear separation of concerns:

```
mmf/services/identity/
├── domain/           # Pure business logic (no dependencies)
│   ├── models/       # Entities, value objects, domain policies
│   └── contracts/    # Domain-level interfaces (no I/O)
├── application/      # Use cases (orchestrates domain + external world)
│   ├── ports_in/     # Inbound ports (use case interfaces)
│   ├── ports_out/    # Outbound ports (external dependencies)
│   ├── usecases/     # Use case implementations
│   └── policies/     # Application policies (idempotency, etc.)
├── infrastructure/   # Adapters (implements ports)
│   └── adapters/     # Inbound and outbound adapters
├── plugins/          # Service-scope feature plugins
├── platform/         # Wiring to platform_core
└── tests/           # All test types (unit, integration, contract)
```

## Key Principles Demonstrated

### 1. **Ports and Adapters**

- **Inbound Ports**: `AuthenticatePrincipal` - defines what the service can do
- **Outbound Ports**: `UserRepository`, `EventBus` - defines what the service needs
- **Adapters**: `InMemoryUserRepository`, `InMemoryEventBus` - implement the ports

### 2. **Dependency Inversion**

- Domain depends on nothing
- Application depends only on domain and its own port interfaces
- Infrastructure depends on application ports but not the reverse

### 3. **Test-Driven Development (TDD)**

- Domain models have comprehensive unit tests
- Use cases have isolated unit tests with mocks
- Integration tests verify the complete flow
- Tests drive the design and ensure quality

### 4. **Clean Boundaries**

- No framework code in domain or application layers
- Infrastructure details isolated in adapters
- Clear contracts between layers

## Domain Model

The domain contains core business entities:

- **`UserId`**: Value object for user identification
- **`Credentials`**: Value object for authentication data
- **`Principal`**: Entity representing an authenticated user
- **`AuthenticationResult`**: Result of authentication attempts
- **`AuthenticationStatus`**: Enumeration of possible authentication states

## Use Cases

Currently implements one core use case:

- **`AuthenticatePrincipalUseCase`**: Validates credentials and creates authenticated principals

## Infrastructure Adapters

Simple in-memory implementations for testing:

- **`InMemoryUserRepository`**: Stores users in memory with simple password hashing
- **`InMemoryEventBus`**: Collects events for verification in tests

## Running Tests

```bash
# Run all tests
pytest mmf/services/identity/tests/

# Run specific test types
pytest mmf/services/identity/tests/test_domain_models.py      # Domain unit tests
pytest mmf/services/identity/tests/test_authentication_usecases.py  # Use case tests
pytest mmf/services/identity/tests/test_integration.py       # Integration tests
```

## Migration Strategy

This minimal example serves as the **template and proving ground** for migrating the existing code:

### Current State

- **`mmf/`** - Existing working code with similar structure
- **`mmf/`** - This minimal example
- **`src/marty_msf/`** - Legacy security framework
- **`boneyard/`** - Code to be deprecated (currently empty)

### Migration Process

1. **✅ Prove the architecture** - This minimal example demonstrates the pattern
2. **Next: Expand the example** - Add more use cases (authorization, token validation, etc.)
3. **Then: Migrate piece by piece** - Move functionality from `mmf/` and `src/` to the new structure
4. **Finally: Deprecate old code** - Move replaced code to `boneyard/` only after full migration

### Why This Approach

- **De-risk the migration** - Prove the architecture works before committing
- **Enable parallel development** - Old code keeps working while new is built
- **Test-driven migration** - Every migrated piece has comprehensive tests
- **Clear progression** - Each step builds on proven foundations

## Next Steps

1. **Expand use cases**: Add authorization, token validation, user management
2. **Add real adapters**: Database, HTTP, message queue implementations
3. **Platform integration**: Connect to `platform_core` contracts
4. **Plugin system**: Demonstrate service-scope plugins
5. **Migration execution**: Begin moving functionality from existing code

## Platform Integration

Eventually this service will integrate with:

- **`platform_core/`** - Cross-cutting contracts (secrets, telemetry, policy)
- **`platform_plugins/`** - Operator-scope infrastructure providers
- **`infrastructure/`** - Cross-service infrastructure (gateway, mesh, etc.)
- **`deploy/`** - Deployment manifests and configurations

This minimal example focuses on the service-level architecture first, then will integrate with the platform concerns.
