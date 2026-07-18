# Testing Guide

## Overview

MMF follows a testing strategy emphasizing real implementations over mocks, following the test pyramid pattern (70% unit, 20% integration, 10% e2e).

## Test Structure

```
tests/
├── conftest.py              # Global fixtures
├── unit/                    # Fast, isolated tests (70%)
├── integration/             # Component interaction tests (20%)
├── e2e/                     # Full workflow tests (10%)
├── fixtures/                # Shared test data
└── utils/                   # Testing utilities
```

## Running Tests

```bash
# Run all tests
marty test

# Run specific test types
marty test unit
marty test integration
marty test e2e

# Run tests with coverage
marty test --coverage

# Run specific test file
pytest tests/unit/test_service.py

# Run tests matching pattern
pytest -k "test_authentication"
```

## Writing Tests

### Unit Tests

```python
import pytest
from marty_msf.framework.config import create_service_config

def test_service_configuration():
    config = create_service_config("test_service")
    assert config.service.name == "test_service"
    assert config.service.port > 0
```

### Integration Tests

```python
import pytest
from marty_msf.framework.database import DatabaseManager

@pytest.mark.integration
async def test_database_connection(db_config):
    db_manager = DatabaseManager(db_config)
    result = await db_manager.execute("SELECT 1")
    assert result == [(1,)]
```

### E2E Tests

```python
import pytest
import httpx

@pytest.mark.e2e
async def test_service_health_endpoint(service_url):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{service_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
```

## Test Fixtures

### Common Fixtures

```python
# In conftest.py
@pytest.fixture
async def db_config():
    return DatabaseConfig(
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password="test_pass"
    )

@pytest.fixture
async def test_client():
    from your_service.main import app
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### Database Fixtures

```python
@pytest.fixture
async def clean_database(db_manager):
    # Setup: Create test data
    await db_manager.execute("TRUNCATE users CASCADE")
    yield db_manager
    # Teardown: Clean up
    await db_manager.execute("TRUNCATE users CASCADE")
```

## Testing Best Practices

### General

- **Test behavior, not implementation**
- **Use descriptive test names** (`test_should_reject_invalid_email`)
- **Arrange, Act, Assert** structure
- **One assertion per test** (when possible)

### Data Management

- **Use factories** for test data creation
- **Clean state** between tests
- **Realistic test data** that reflects production scenarios

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### Mock External Dependencies

```python
@pytest.fixture
def mock_external_api(mocker):
    return mocker.patch('your_service.external_client.ExternalAPI')

def test_external_integration(mock_external_api):
    mock_external_api.get_data.return_value = {"status": "success"}
    # Test your service logic
```

## Test Categories

### Unit Tests (70%)

- Test individual functions/methods
- Mock external dependencies
- Fast execution (< 1s per test)
- No network or file I/O

### Integration Tests (20%)

- Test component interactions
- Use real databases/message queues
- Test configuration loading
- Test database queries

### E2E Tests (10%)

- Test complete user workflows
- Full service stack
- Real external dependencies
- Deployment validation

## Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v6
      - name: Run Tests
        run: |
          marty test --coverage
          marty test integration
```

## Code Coverage

```bash
# Generate coverage report
marty test --coverage --html

# View coverage
open htmlcov/index.html

# Coverage requirements
# Minimum 80% overall coverage
# Minimum 90% for critical paths
```

## Debugging Tests

```bash
# Run with debugging
pytest --pdb tests/unit/test_service.py

# Verbose output
pytest -v tests/

# Show print statements
pytest -s tests/

# Run failed tests only
pytest --lf
```
