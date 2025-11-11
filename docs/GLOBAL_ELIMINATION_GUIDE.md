# Global Variable Elimination: Migration Guide

## Overview

This document describes the comprehensive migration from global variables to a strongly-typed dependency injection system in the Marty Microservices Framework (MMF). This migration improves code maintainability, testability, and type safety while maintaining backward compatibility.

## Problems with Global Variables

The original codebase had several issues with global variable usage:

1. **Type Safety**: Global variables made it difficult for mypy to provide proper type checking
2. **Testing**: Global state made unit tests difficult to isolate and run in parallel
3. **Thread Safety**: Some global variables weren't thread-safe
4. **Dependency Injection**: No clear way to inject different implementations for testing
5. **Lifecycle Management**: No proper cleanup or initialization patterns

## Solution: Typed Service Registry

We've implemented a comprehensive solution with the following components:

### Core Components

#### 1. Service Registry (`src/marty_msf/core/registry.py`)

A thread-safe, strongly-typed dependency injection container that replaces global variables:

```python
from marty_msf.core.registry import get_service, register_singleton

# Register a service
register_singleton(MyService, my_service_instance)

# Get a service
service = get_service(MyService)
```

Key features:

- **Type Safety**: Full mypy support with generics
- **Thread Safe**: Uses threading.RLock for all operations
- **Lazy Loading**: Supports factory patterns for delayed initialization
- **Testing Support**: Easy mocking and temporary overrides
- **Lifecycle Management**: Proper initialization and cleanup

#### 2. Service Base Classes (`src/marty_msf/core/services.py`)

Strongly-typed base classes for common service patterns:

- `ConfigService`: Base for configuration services
- `ObservabilityService`: Base for monitoring/tracing services
- `SecurityService`: Base for authentication/authorization
- `MessagingService`: Base for event bus/messaging
- `ManagerService`: Base for general manager classes

#### 3. Atomic Counter (`src/marty_msf/core/registry.py`)

Thread-safe counter to replace global ID generators:

```python
from marty_msf.core.registry import AtomicCounter

counter = AtomicCounter(1)
next_id = counter.increment()  # Thread-safe increment
```

## Migration Examples

### Before: Global Configuration

```python
# OLD: Global variable pattern
_config_instance: DataConsistencyConfig | None = None

def get_config() -> DataConsistencyConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = DataConsistencyConfig.from_env()
    return _config_instance
```

### After: Typed Service

```python
# NEW: Typed service pattern
class DataConsistencyConfigService(ConfigService):
    def __init__(self) -> None:
        super().__init__()
        self._data_config: Optional[DataConsistencyConfig] = None

    def load_from_env(self) -> None:
        self._data_config = DataConsistencyConfig.from_env()
        self._mark_loaded()

    def get_data_config(self) -> DataConsistencyConfig:
        if self._data_config is None:
            self.load_from_env()
        return self._data_config

# Usage
def get_config() -> DataConsistencyConfig:
    return get_config_service().get_data_config()
```

### Before: Global Counters

```python
# OLD: Global counter pattern
next_id = 1

def create_user(user: dict):
    global next_id
    user_data = {"id": next_id, "type": "user", **user}
    store[next_id] = user_data
    next_id += 1
    return user_data
```

### After: Atomic Counter

```python
# NEW: Thread-safe counter
from marty_msf.core.registry import AtomicCounter

id_counter = AtomicCounter(1)

def create_user(user: dict):
    user_id = id_counter.increment()
    user_data = {"id": user_id, "type": "user", **user}
    store[user_id] = user_data
    return user_data
```

## Files Modified

### Core Infrastructure

- **NEW**: `src/marty_msf/core/registry.py` - Service registry and atomic counter
- **NEW**: `src/marty_msf/core/services.py` - Typed service base classes

### Configuration

- `src/marty_msf/patterns/config.py` - Replaced global config with ConfigService

### Observability

- `src/marty_msf/observability/standard.py` - Replaced global observability with ObservabilityService
- `src/marty_msf/observability/tracing.py` - Replaced global tracer with TracingService

### Security

- `src/marty_msf/security/manager.py` - Replaced global security manager with SecurityService

### CLI

- `src/marty_msf/cli/__init__.py` - Replaced global ID counters with AtomicCounter

### Utilities

- **NEW**: `scripts/global_replacement_helper.py` - Tool to identify remaining global patterns

## Migration Strategy

### Phase 1: Core Infrastructure ✅

- Created service registry system
- Created typed service base classes
- Created atomic counter for ID generation

### Phase 2: High-Impact Modules ✅

- Migrated configuration system
- Migrated observability system
- Migrated security manager
- Migrated CLI ID counters

### Phase 3: Remaining Modules (In Progress)

Based on the analysis script, remaining global patterns to migrate:

- Event bus managers
- Resilience managers
- Audit loggers
- Pool managers
- RBAC/ABAC managers

## Benefits Achieved

### 1. Type Safety

All services are now fully typed with mypy validation:

```bash
$ uv run mypy src/marty_msf/core/registry.py
Success: no issues found in 1 source file
```

### 2. Thread Safety

- Service registry uses RLock for thread-safe operations
- AtomicCounter provides thread-safe ID generation
- No more race conditions with global variables

### 3. Testing

- Easy service mocking with `temporary_service_override`
- No global state pollution between tests
- Clear service lifecycle management

### 4. Maintainability

- Clear dependency relationships
- Consistent service patterns
- Better error handling and logging

## Usage Guide

### Registering Services

```python
from marty_msf.core.registry import register_singleton, register_factory

# Register a singleton instance
register_singleton(MyService, my_service_instance)

# Register a factory for lazy loading
register_factory(MyService, lambda: MyService())
```

### Getting Services

```python
from marty_msf.core.registry import get_service, get_service_optional

# Get a service (throws if not registered)
service = get_service(MyService)

# Get a service safely (returns None if not registered)
service = get_service_optional(MyService)
```

### Testing with Services

```python
from marty_msf.core.registry import temporary_service_override

def test_my_feature():
    mock_service = MockService()
    with temporary_service_override(MyService, mock_service):
        # Test code using the mock service
        result = my_function()
        assert result.success
```

### Creating New Services

```python
from marty_msf.core.services import ConfigService

class MyConfigService(ConfigService):
    def load_from_env(self) -> None:
        # Implementation
        self._mark_loaded()

    def validate(self) -> bool:
        # Implementation
        return True
```

## Future Improvements

1. **Auto-Discovery**: Automatically register services on import
2. **Configuration**: YAML/JSON configuration for service registration
3. **Decorators**: `@inject` decorator for automatic dependency injection
4. **Async Support**: Async service initialization and cleanup
5. **Metrics**: Service usage and performance metrics

## Backward Compatibility

All changes maintain backward compatibility through compatibility functions:

```python
# Old function still works
config = get_config()

# Now implemented using new service
def get_config() -> DataConsistencyConfig:
    return get_config_service().get_data_config()
```

This ensures existing code continues to work while new code can use the improved patterns.

## Conclusion

The migration from global variables to a typed service registry system provides:

- ✅ **Full mypy type safety**
- ✅ **Thread-safe operations**
- ✅ **Better testability**
- ✅ **Improved maintainability**
- ✅ **Clear dependency management**
- ✅ **Backward compatibility**

The framework now follows modern Python best practices while maintaining the functionality and ease of use that makes MMF powerful for microservices development.
