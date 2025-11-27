# Marty Microservices Framework - Architecture Standards

## Golden Standard: Hexagonal Architecture (Ports and Adapters)

All services and framework modules MUST follow the Hexagonal Architecture pattern with explicit separation of concerns. This is a **hard requirement** with zero tolerance for violations.

## Directory Structure Requirements

### Services (Bounded Contexts)

Every service under `mmf_new/services/<service_name>/` MUST have this structure:

```
<service_name>/
├── domain/                      # Pure business logic (NO external dependencies)
│   ├── entities.py             # Aggregate roots and entities
│   ├── value_objects.py        # Immutable value objects
│   ├── contracts.py            # Port interfaces (abstract base classes)
│   └── models/                 # Domain models subdirectory (if needed)
├── application/                 # Use cases and application logic
│   ├── commands.py             # Command/response DTOs
│   ├── use_cases.py            # Business use case orchestration
│   └── queries.py              # Query handlers (optional)
├── infrastructure/              # External world adapters
│   ├── adapters/
│   │   ├── in/                 # Driving adapters (HTTP, gRPC, CLI)
│   │   └── out/                # Driven adapters (DB, external APIs, messaging)
│   ├── models.py               # Database ORM models
│   └── repository.py           # Repository implementations
├── tests/                       # Comprehensive test suite
│   ├── fixtures.py             # Test fixtures
│   ├── test_domain.py          # Domain unit tests
│   ├── test_use_cases.py       # Application layer tests
│   └── test_integration.py     # Integration tests
├── di_config.py                 # Dependency injection container (REQUIRED)
├── service_factory.py           # High-level service factory
└── __init__.py                  # Public API exports
```

### Framework Modules

Every framework module under `mmf_new/framework/<module_name>/` MUST have this structure:

```
<module_name>/
├── domain/                      # Core abstractions and business logic
│   ├── protocols.py            # Abstract protocols/interfaces
│   └── models.py               # Domain models
├── adapters/                    # Concrete implementations
│   ├── <provider_name>.py      # Specific adapter implementations
│   └── factories.py            # Adapter factories
├── ports/                       # Port interfaces (optional if protocols.py suffices)
│   ├── input.py                # Inbound ports
│   └── output.py               # Outbound ports
└── __init__.py                  # Public API
```

## Dependency Rules (STRICT)

The dependency rule is **NON-NEGOTIABLE**. Dependencies can only point inward:

```
Infrastructure → Application → Domain
      ↓              ↓
   (Adapters)   (Use Cases)    (Business Logic)
```

### ❌ FORBIDDEN Imports

- **Domain Layer** CANNOT import:
  - `application.*`
  - `infrastructure.*`
  - Any external libraries (FastAPI, SQLAlchemy, etc.) except standard library and typing
- **Application Layer** CANNOT import:
  - `infrastructure.*` (must depend on `domain.contracts` instead)
- **Infrastructure Layer** CAN import:
  - `domain.*`
  - `application.*`
  - External libraries

### Violation Enforcement

All violations will be caught by automated architectural tests in `tests/test_architecture.py` using `pytest-archon`. **Builds will fail** if any violation is detected.

## Dependency Injection Pattern (REQUIRED)

Every service MUST implement an explicit `DIContainer` class in `di_config.py`.

### Base Container (Core)

All service containers MUST inherit from `mmf_new.core.di.BaseDIContainer`:

```python
from mmf_new.core.di import BaseDIContainer

class MyServiceDIContainer(BaseDIContainer):
    """Dependency injection container for MyService."""

    def __init__(self, config: MyServiceConfig):
        super().__init__()
        self.config = config
        self._repository: Optional[MyRepository] = None
        self._use_case: Optional[MyUseCase] = None

    def initialize(self) -> None:
        """Wire all dependencies. Called once at startup."""
        # Initialize infrastructure
        self._repository = MyRepositoryImpl(self.config.database_url)

        # Initialize application
        self._use_case = MyUseCase(repository=self._repository)

    @property
    def use_case(self) -> MyUseCase:
        """Lazy access to use case."""
        if self._use_case is None:
            raise RuntimeError("Container not initialized")
        return self._use_case

    def cleanup(self) -> None:
        """Cleanup resources. Called at shutdown."""
        if self._repository:
            self._repository.close()
```

### No Implicit Wiring

❌ **FORBIDDEN**: Scattered instantiation logic across the codebase
❌ **FORBIDDEN**: Global variables or module-level singletons
❌ **FORBIDDEN**: Config files that do instantiation

✅ **REQUIRED**: All wiring happens in `di_config.py`
✅ **REQUIRED**: Explicit lifecycle management (`initialize()`, `cleanup()`)

## Testing Standards

### Test Organization

Tests MUST mirror the source structure:

- `test_domain.py` - Pure domain logic (no mocks needed)
- `test_use_cases.py` - Application logic (mock repositories)
- `test_integration.py` - Full stack integration tests
- `fixtures.py` - Shared test fixtures and factories

### Architectural Tests

`tests/test_architecture.py` MUST contain:

```python
import pytest_archon

def test_domain_has_no_infrastructure_imports():
    """Domain layer must not import infrastructure."""
    pytest_archon.assert_no_import(
        source="mmf_new.services.*.domain",
        target="mmf_new.services.*.infrastructure"
    )

def test_domain_has_no_application_imports():
    """Domain layer must not import application."""
    pytest_archon.assert_no_import(
        source="mmf_new.services.*.domain",
        target="mmf_new.services.*.application"
    )

def test_application_has_no_infrastructure_imports():
    """Application layer must not import infrastructure."""
    pytest_archon.assert_no_import(
        source="mmf_new.services.*.application",
        target="mmf_new.services.*.infrastructure"
    )
```

## Migration Strategy

When refactoring existing code to match this standard:

1. **No Backwards Compatibility**: Delete old files, move code to new locations. No deprecation warnings, no stub files.
2. **Fix Imports**: Update all imports immediately. Let the build fail, then fix it.
3. **Update Tests**: Ensure all tests pass after restructuring.
4. **Document in MIGRATION_SUMMARY.md**: Each service/module should have a migration summary explaining the changes.

## Non-Compliance

Any code that does not follow this architecture will be **rejected** in code review and will **fail** CI/CD builds.

## Examples

Reference implementations:

- **Service**: `mmf_new/services/audit/` - Complete hexagonal architecture with DI container
- **Framework Module**: `mmf_new/framework/gateway/` - Proper layering in framework code

---

**Last Updated**: November 25, 2025
**Status**: **MANDATORY** for all new code. Existing code must be refactored to comply.
