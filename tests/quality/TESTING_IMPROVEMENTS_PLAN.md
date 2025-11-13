# Testing Improvements Plan

## Current Issues

### Basic Import/Enum Tests

Current tests focus on:

- Import validation (`test_import_deployment_strategies()`)
- Enum membership checks (`assert hasattr(DeploymentStrategy, 'BLUE_GREEN')`)
- Basic type checking (`assert issubclass(DeploymentStrategy, Enum)`)

### Unnecessary Shim Modules

- `src/framework/discovery/discovery.py` - Only re-exports symbols (41 lines)
- Similar patterns may exist in other modules

## Proposed Improvements

### 1. Behavior-Driven Testing

Replace basic import tests with actual behavior validation:

#### Before (Current)

```python
def test_deployment_strategy_enum():
    """Test DeploymentStrategy enum values."""
    from framework.deployment.strategies import DeploymentStrategy
    assert hasattr(DeploymentStrategy, 'BLUE_GREEN')
    assert hasattr(DeploymentStrategy, 'CANARY')
```

#### After (Improved)

```python
@pytest.mark.asyncio
async def test_blue_green_deployment_workflow():
    """Test complete blue-green deployment workflow."""
    orchestrator = DeploymentOrchestrator(config=test_config)

    # Test actual deployment behavior
    result = await orchestrator.deploy(
        strategy=DeploymentStrategy.BLUE_GREEN,
        service_version=ServiceVersion("test-service", "v2.0.0"),
        target=DeploymentTarget("production")
    )

    assert result.status == DeploymentStatus.SUCCESS
    assert result.strategy == DeploymentStrategy.BLUE_GREEN
    assert len(result.phases_completed) > 0
```

### 2. Integration Testing

Add realistic integration scenarios:

```python
@pytest.mark.asyncio
async def test_canary_deployment_with_rollback():
    """Test canary deployment with automatic rollback on failure."""
    orchestrator = DeploymentOrchestrator(config=canary_config)

    # Simulate validation failure
    with patch.object(orchestrator.validation_manager, 'validate') as mock_validate:
        mock_validate.return_value = ValidationResult.FAIL

        result = await orchestrator.deploy(
            strategy=DeploymentStrategy.CANARY,
            service_version=ServiceVersion("test-service", "v2.0.0"),
        )

        assert result.status == DeploymentStatus.ROLLING_BACK
        # Verify rollback actually occurred
        assert orchestrator.current_version == "v1.0.0"
```

### 3. Remove Unnecessary Shims

#### discovery.py Removal

The `src/framework/discovery/discovery.py` file should be removed because:

- It only re-exports symbols (no actual logic)
- The decomposed modules are already properly structured
- Direct imports are cleaner: `from framework.discovery.clients import ServiceDiscoveryClient`

#### Action Plan

1. **Audit imports:** Find all code importing from `discovery.py`
2. **Update imports:** Change to direct module imports
3. **Remove shim:** Delete the unnecessary wrapper file
4. **Update documentation:** Reflect new import patterns

### 4. Test Coverage Improvements

#### Current Coverage Issues

- Tests focus on structure rather than behavior
- Missing integration test scenarios
- No testing of error conditions
- Limited async workflow testing

#### Improvement Areas

##### A. Deployment Orchestrator

```python
class TestDeploymentOrchestrator:
    """Comprehensive orchestrator behavior tests."""

    async def test_deployment_lifecycle(self):
        """Test complete deployment from start to finish."""

    async def test_error_handling_during_deployment(self):
        """Test orchestrator handles errors gracefully."""

    async def test_concurrent_deployments(self):
        """Test handling of multiple simultaneous deployments."""
```

##### B. Service Discovery

```python
class TestServiceDiscoveryBehavior:
    """Test actual service discovery workflows."""

    async def test_service_registration_and_lookup(self):
        """Test end-to-end service registration/discovery."""

    async def test_health_check_integration(self):
        """Test discovery responds to health check failures."""

    async def test_load_balancing_behavior(self):
        """Test different load balancing strategies work correctly."""
```

##### C. External Connectors

```python
class TestExternalConnectorBehavior:
    """Test real external system integration workflows."""

    async def test_rest_connector_with_auth(self):
        """Test REST connector handles authentication properly."""

    async def test_circuit_breaker_behavior(self):
        """Test circuit breaker opens/closes correctly."""

    async def test_retry_logic(self):
        """Test retry mechanisms work as expected."""
```

### 5. Implementation Steps

1. ✅ **Audit current tests:** Identify basic import/enum tests
2. **Create behavior test examples:** Demonstrate improved testing patterns
3. **Update existing tests:** Replace basic tests with behavior tests
4. **Remove shim modules:** Start with `discovery.py`
5. **Update import statements:** Throughout codebase
6. **Add integration tests:** Focus on real-world workflows
7. **Improve coverage:** Target actual business logic

### 6. Benefits

#### Code Quality

- **Real validation:** Tests verify actual functionality works
- **Regression prevention:** Behavior tests catch breaking changes
- **Documentation:** Tests serve as usage examples

#### Maintainability

- **Cleaner imports:** Direct module imports are more explicit
- **Reduced complexity:** Fewer indirection layers
- **Better IDE support:** Direct imports provide better autocomplete

#### Development Velocity

- **Faster debugging:** Behavior tests pinpoint actual issues
- **Confident refactoring:** Tests validate changes don't break functionality
- **Better onboarding:** Clear examples of how components work

## Next Steps

This testing improvement should be a focused effort after the module decomposition is complete. The improved test patterns will be easier to implement once the modular structure is in place.
