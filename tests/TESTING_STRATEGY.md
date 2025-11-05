# MMF Testing Strategy

## Overview

The Marty Microservices Framework (MMF) employs a comprehensive testing strategy following the testing pyramid principle, ensuring reliability, maintainability, and confidence in the codebase throughout the migration from monolithic to hexagonal architecture.

## Testing Philosophy

### 1. **Testing Pyramid Structure**
```
                    🔺 E2E Tests (Few, Slow, High Value)
                  🔹🔹 Integration Tests (Some, Medium Speed)
              🔸🔸🔸🔸 Contract Tests (Focused, Fast API Validation)
          🔹🔹🔹🔹🔹🔹 Unit Tests (Many, Fast, Isolated)
```

### 2. **Test-Driven Development (TDD)**
- Write tests before implementation
- Red → Green → Refactor cycle
- Validate business requirements through tests

### 3. **Hexagonal Architecture Testing**
- **Domain Layer**: Pure unit tests, no dependencies
- **Application Layer**: Mock external dependencies
- **Infrastructure Layer**: Integration tests with real adapters

## Directory Structure

```
tests/
├── conftest.py                 # Global pytest configuration
├── fixtures/                   # Shared test data and utilities
│   ├── data/                   # Test data files (JSON, YAML, etc.)
│   ├── factories.py            # Test object factories
│   └── helpers.py              # Test helper functions
├── unit/                       # Fast, isolated component tests
│   ├── conftest.py             # Unit test configuration
│   ├── domain/                 # Domain layer tests
│   ├── application/            # Application layer tests
│   ├── infrastructure/         # Infrastructure layer tests
│   └── framework/              # Framework component tests
├── integration/                # Component interaction tests
│   ├── conftest.py             # Integration test configuration
│   ├── database/               # Database integration tests
│   ├── messaging/              # Message bus integration tests
│   ├── external/               # External service integration tests
│   └── services/               # Service-to-service integration
├── contract/                   # API contract validation tests
│   ├── conftest.py             # Contract test configuration
│   ├── openapi/                # OpenAPI specification tests
│   ├── schemas/                # Data schema validation tests
│   └── compatibility/          # Backward compatibility tests
├── e2e/                        # End-to-end system tests
│   ├── conftest.py             # E2E test configuration
│   ├── kind/                   # KIND-based e2e tests
│   │   ├── automated/          # Automated e2e test suite
│   │   ├── manual/             # Manual test scenarios
│   │   └── config/             # KIND cluster configurations
│   ├── playwright/             # Browser-based e2e tests
│   ├── api/                    # Full API workflow tests
│   └── scenarios/              # Business scenario tests
├── performance/                # Performance and load tests
│   ├── conftest.py             # Performance test configuration
│   ├── load/                   # Load testing scenarios
│   ├── stress/                 # Stress testing scenarios
│   ├── benchmark/              # Performance benchmarks
│   └── monitoring/             # Performance monitoring tests
├── security/                   # Security validation tests
│   ├── conftest.py             # Security test configuration
│   ├── authentication/         # Auth mechanism tests
│   ├── authorization/          # Permission and access tests
│   ├── vulnerability/          # Security vulnerability scans
│   └── penetration/            # Penetration testing scripts
├── chaos/                      # Chaos engineering tests
│   ├── conftest.py             # Chaos test configuration
│   ├── fault_injection/        # Fault injection tests
│   ├── resilience/             # System resilience tests
│   ├── recovery/               # Disaster recovery tests
│   └── network/                # Network partition tests
├── quality/                    # Code quality validation tests
│   ├── conftest.py             # Quality test configuration
│   ├── static_analysis/        # Static code analysis tests
│   ├── dependency_validation/  # Dependency security and health
│   ├── observability/          # Monitoring and logging tests
│   └── compliance/             # Standards compliance tests
├── examples/                   # Example tests for documentation
│   ├── basic/                  # Basic test examples
│   ├── advanced/               # Advanced test patterns
│   └── tutorials/              # Step-by-step test tutorials
├── utils/                      # Test utilities and helpers
│   ├── assertions.py           # Custom assertions
│   ├── generators.py           # Test data generators
│   ├── mocks.py                # Mock objects and stubs
│   └── runners.py              # Custom test runners
└── plugins/                    # Custom pytest plugins
    ├── __init__.py
    ├── fixtures.py             # Custom fixtures
    ├── markers.py              # Custom test markers
    └── reporters.py            # Custom test reporters
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)
**Purpose**: Test individual components in isolation
**Characteristics**:
- Fast execution (< 1ms per test)
- No external dependencies
- High code coverage (>90%)
- Isolated from infrastructure

**Example**:
```python
def test_user_id_creation():
    user_id = UserId("user123")
    assert user_id.value == "user123"
    assert str(user_id) == "user123"
```

### 2. Integration Tests (`tests/integration/`)
**Purpose**: Test component interactions and external dependencies
**Characteristics**:
- Medium execution speed (1-100ms per test)
- Real databases, message buses, external services
- Focused on integration points
- Environment setup/teardown

**Example**:
```python
def test_user_repository_integration(postgres_db):
    repository = PostgresUserRepository(postgres_db)
    user = User(UserId("test"), "testuser")
    repository.save(user)
    retrieved = repository.find_by_id(UserId("test"))
    assert retrieved == user
```

### 3. Contract Tests (`tests/contract/`)
**Purpose**: Validate API contracts and data schemas
**Characteristics**:
- Fast execution
- Schema validation
- Backward compatibility
- API specification compliance

**Example**:
```python
def test_authentication_api_contract(api_client):
    response = api_client.post("/authenticate", json={
        "username": "test",
        "password": "test123"
    })
    assert response.status_code == 200
    assert response.json().keys() >= {
        "success", "user_id", "authenticated_at"
    }
```

### 4. End-to-End Tests (`tests/e2e/`)
**Purpose**: Test complete user workflows and system behavior
**Characteristics**:
- Slow execution (1-10 seconds per test)
- Real environment simulation
- Complete user journeys
- Infrastructure validation

**Types**:
- **KIND-based**: Kubernetes deployment testing
- **Playwright**: Browser-based UI testing
- **API workflows**: Complete business scenarios

### 5. Performance Tests (`tests/performance/`)
**Purpose**: Validate system performance and scalability
**Characteristics**:
- Load testing (normal traffic)
- Stress testing (peak traffic)
- Benchmark testing (performance regression)
- Resource usage monitoring

### 6. Security Tests (`tests/security/`)
**Purpose**: Validate security mechanisms and find vulnerabilities
**Characteristics**:
- Authentication/authorization testing
- Input validation and sanitization
- Vulnerability scanning
- Penetration testing scenarios

### 7. Chaos Tests (`tests/chaos/`)
**Purpose**: Test system resilience and fault tolerance
**Characteristics**:
- Fault injection
- Network partitions
- Service failures
- Recovery scenarios

## Test Execution Strategy

### Development Workflow
```bash
# Fast feedback loop (< 30 seconds)
make test-unit                  # Run unit tests only

# Medium feedback loop (< 2 minutes)
make test-integration          # Run integration tests

# Contract validation (< 1 minute)
make test-contract             # Run contract tests

# Complete validation (< 10 minutes)
make test-e2e-quick           # Run essential e2e tests

# Full system validation (< 30 minutes)
make test-all                 # Run complete test suite
```

### CI/CD Pipeline
1. **Pre-commit**: Unit tests + linting
2. **PR validation**: Unit + integration + contract tests
3. **Merge to main**: Full test suite including e2e
4. **Release**: Complete validation + performance + security tests

### Test Markers
```python
# Pytest markers for test categorization
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.contract
@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.security
@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.fast
@pytest.mark.requires_docker
@pytest.mark.requires_kubernetes
```

## Quality Metrics

### Coverage Targets
- **Unit tests**: >90% code coverage
- **Integration tests**: >80% integration point coverage
- **E2E tests**: >95% critical user journey coverage

### Performance Targets
- **Unit tests**: <1ms average execution
- **Integration tests**: <100ms average execution
- **E2E tests**: <10s average execution
- **Full suite**: <30 minutes total execution

### Success Criteria
- All tests pass before merge
- No flaky tests (>99% success rate)
- Fast feedback (<30s for unit tests)
- Comprehensive coverage (business scenarios)

## Migration Strategy

### Phase 1: Foundation (Current)
- ✅ Unit tests for domain layer
- ✅ Integration tests for infrastructure
- ✅ E2E tests for identity service
- ✅ Contract tests for API endpoints

### Phase 2: Expansion
- [ ] Performance test suite
- [ ] Security test automation
- [ ] Chaos engineering tests
- [ ] Visual regression tests

### Phase 3: Optimization
- [ ] Parallel test execution
- [ ] Test result caching
- [ ] Intelligent test selection
- [ ] Advanced reporting and analytics

## Tools and Technologies

### Testing Frameworks
- **pytest**: Primary testing framework
- **KIND**: Kubernetes testing environment
- **Playwright**: Browser automation
- **locust**: Load testing
- **safety**: Security vulnerability scanning

### Infrastructure
- **Docker**: Containerized test environments
- **Kubernetes**: Orchestration testing
- **GitHub Actions**: CI/CD automation
- **Allure**: Test reporting and analytics

### Monitoring
- **pytest-cov**: Code coverage
- **pytest-benchmark**: Performance benchmarking
- **pytest-html**: HTML test reports
- **pytest-xdist**: Parallel test execution

## Best Practices

### 1. Test Independence
- Each test should be completely independent
- No shared state between tests
- Proper setup/teardown for each test

### 2. Clear Test Names
```python
def test_should_authenticate_user_when_valid_credentials_provided():
    # Test implementation
```

### 3. Arrange-Act-Assert Pattern
```python
def test_user_authentication():
    # Arrange
    credentials = Credentials("user", "password")
    use_case = AuthenticateUserUseCase(mock_repository)

    # Act
    result = use_case.execute(credentials)

    # Assert
    assert result.success is True
```

### 4. Test Data Management
- Use factories for test object creation
- Keep test data minimal and focused
- Use fixtures for complex setup

### 5. Error Testing
- Test both success and failure scenarios
- Validate error messages and codes
- Test edge cases and boundary conditions

## Conclusion

This testing strategy ensures comprehensive validation of the MMF during the migration from monolithic to hexagonal architecture. The multi-layered approach provides fast feedback during development while ensuring system reliability and performance in production.
