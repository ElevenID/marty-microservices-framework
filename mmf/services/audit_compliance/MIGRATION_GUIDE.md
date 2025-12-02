# Audit Compliance Service Migration Guide

## Overview

This guide documents the migration from the monolithic `audit_compliance`
module to the new hexagonal architecture implementation in `mmf`. The
migration transforms a 1,300+ line monolithic monitoring system into a clean,
maintainable, and extensible service following Domain-Driven Design (DDD) and
hexagonal architecture patterns.

## Architecture Transformation

### Before: Monolithic Structure

```text
src/marty_msf/audit_compliance/
├── monitoring.py                    # 1,300+ lines of mixed concerns
├── compliance_scanner.py            # Tightly coupled scanning logic
├── threat_detector.py               # Embedded threat analysis
└── siem_integration.py              # Direct SIEM coupling
```text

### After: Hexagonal Architecture

```text
mmf/services/audit_compliance/
├── domain/                          # Pure business logic
│   ├── entities.py                  # Business entities
│   ├── value_objects.py             # Immutable value objects
│   └── contracts.py                 # Port interfaces
├── application/                     # Use cases & orchestration
│   ├── commands.py                  # Command/Response DTOs
│   └── use_cases.py                 # Business use cases
├── infrastructure/                  # External integrations
│   ├── repository.py                # Data persistence
│   ├── cache.py                     # Redis caching
│   ├── siem_adapter.py              # Elasticsearch integration
│   ├── compliance_scanner.py        # Framework scanning
│   ├── threat_analyzer.py           # ML threat detection
│   ├── metrics_adapter.py           # Prometheus metrics
│   └── report_generator.py          # Multi-format reports
├── di_config.py                     # Dependency injection
├── service_factory.py               # High-level API
└── tests/                           # Comprehensive test suite
    └── integration/
```text

## Key Architectural Improvements

### 1. Separation of Concerns

- **Domain Layer**: Pure business logic with no external dependencies
- **Application Layer**: Orchestrates business workflows through use cases
- **Infrastructure Layer**: Handles external system integration

### 2. Dependency Inversion

- **Ports (Interfaces)**: Define contracts in the domain layer
- **Adapters**: Implement ports in the infrastructure layer
- **Dependency Injection**: Wire components together cleanly

### 3. Framework Integration

- **Repository Pattern**: Extends `Repository[T]` from mmf core
- **Cache Management**: Integrates with `CacheManager` using Redis ZSET
- **Metrics Collection**: Extends `FrameworkMetrics` with domain-specific metrics
- **Entity System**: All entities inherit from core `Entity` base class

## Migration Steps

### Step 1: Update Imports

**Before:**

```python
from src.marty_msf.audit_compliance.monitoring import AuditMonitor
from src.marty_msf.audit_compliance.compliance_scanner import ComplianceScanner
```text

**After:**

```python
from mmf.services.audit_compliance.service_factory import (
    AuditComplianceService,
    create_audit_compliance_service,
    audit_compliance_service
)
```text

### Step 2: Configuration Changes

**Before:**

```python
# Old configuration scattered across multiple files
audit_config = {
    "database_url": "postgresql://localhost/audit",
    "redis_host": "localhost",
    "redis_port": 6379,
    # ... many individual settings
}
```text

**After:**

```python
from mmf.services.audit_compliance.di_config import (
    AuditComplianceConfig,
    create_development_config,
    create_production_config
)

# Environment-specific configurations
config = create_production_config()
# Or customize as needed
config = AuditComplianceConfig(
    database_url="postgresql://prod-db:5432/audit_compliance",
    redis_url="redis://prod-redis:6379/0",
    cache_max_events=50000,
    reports_output_directory="/var/log/security_reports"
)
```text

### Step 3: Service Initialization

**Before:**

```python
# Manual initialization of each component
monitor = AuditMonitor(config)
scanner = ComplianceScanner(config)
threat_detector = ThreatDetector(config)
siem = SIEMIntegration(config)

# Manual wiring of dependencies
monitor.set_compliance_scanner(scanner)
monitor.set_threat_detector(threat_detector)
monitor.set_siem_integration(siem)
```text

**After:**

```python
# Clean service initialization with DI
async def initialize_service():
    service = await create_audit_compliance_service(
        config=config,
        environment="production"
    )
    return service

# Or use context manager for automatic cleanup
async def main():
    async with audit_compliance_service(environment="production") as service:
        # Service is fully initialized and ready to use
        await service.log_audit_event(...)
```text

## Feature Migration Examples

### 1. Audit Event Logging

**Before:**

```python
# Old monolithic approach
monitor = AuditMonitor(config)
monitor.log_event(
    event_type="AUTHENTICATION_SUCCESS",
    user_id="user123",
    details={"ip": "192.168.1.100"}
)
```text

**After:**

```python
# New hexagonal approach
async with audit_compliance_service() as service:
    audit_event = await service.log_audit_event(
        event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
        severity=SecurityEventSeverity.INFO,
        source="auth_service",
        description="User logged in successfully",
        user_id="user123",
        metadata={"ip_address": "192.168.1.100"}
    )
```text

**Benefits:**

- Type-safe enums instead of strings
- Async/await for better performance
- Structured metadata
- Automatic caching and SIEM forwarding

### 2. Compliance Scanning

**Before:**

```python
# Manual scanning with tight coupling
scanner = ComplianceScanner(config)
results = scanner.scan_gdpr_compliance("target_system")
sox_results = scanner.scan_sox_compliance("target_system")
```text

**After:**

```python
# Unified scanning with multiple frameworks
frameworks = [ComplianceFramework.GDPR, ComplianceFramework.SOX]
scan_result = await service.scan_compliance(
    frameworks=frameworks,
    target_resource="target_system",
    scan_depth="thorough"
)

# Results include all frameworks with unified scoring
print(f"Overall compliance score: {scan_result.overall_score}")
for result in scan_result.framework_results:
    print(f"{result.framework}: {result.compliance_score}")
```text

**Benefits:**

- Multi-framework scanning in single call
- Unified scoring system
- Async execution
- Comprehensive reporting

### 3. Threat Analysis

**Before:**

```python
# Manual threat detection
detector = ThreatDetector(config)
threats = detector.analyze_recent_events(hours=24)
```text

**After:**

```python
# Advanced ML-based threat analysis
threat_patterns = await service.analyze_threat_patterns(
    analysis_window_hours=24,
    confidence_threshold=0.7
)

# Get threat intelligence
threat_intel = await service.get_threat_intelligence(
    threat_type="malware",
    active_only=True
)
```text

**Benefits:**

- Machine learning-based detection
- Configurable confidence thresholds
- Real-time threat intelligence
- Pattern correlation across events

### 4. Report Generation

**Before:**

```python
# Limited reporting capabilities
report = monitor.generate_basic_report(start_date, end_date)
```text

**After:**

```python
# Comprehensive multi-format reporting
report_data = await service.generate_security_report(
    report_type="comprehensive",
    start_time=start_time,
    end_time=end_time,
    output_format="pdf",
    include_recommendations=True
)

# Multiple report types available
executive_report = await service.generate_security_report(
    report_type="executive",
    output_format="html"
)
```text

**Benefits:**

- Multiple output formats (JSON, HTML, PDF)
- Various report types (comprehensive, compliance, threat, executive)
- Automated recommendations
- Executive dashboards

## Advanced Usage Patterns

### 1. Bulk Operations

**High-Performance Event Logging:**

```python
# Efficiently log many events
events = [
    {"event_type": SecurityEventType.DATA_ACCESS, ...},
    {"event_type": SecurityEventType.AUTHENTICATION_SUCCESS, ...},
    # ... many more events
]

audit_events = await service.bulk_log_events(events)
```text

### 2. Cached Access

**Fast Event Retrieval:**

```python
# Get recent events from cache (fast)
cached_events = await service.get_cached_events(
    event_types=[SecurityEventType.AUTHENTICATION_FAILURE],
    max_age_hours=1
)

# More comprehensive search (slower but complete)
all_events = await service.get_audit_events(
    start_time=start_time,
    event_types=[SecurityEventType.AUTHENTICATION_FAILURE],
    limit=1000
)
```text

### 3. Concurrent Operations

**Parallel Processing:**

```python
# Run multiple operations concurrently
tasks = [
    service.scan_compliance([ComplianceFramework.GDPR], "system1"),
    service.analyze_threat_patterns(analysis_window_hours=24),
    service.generate_security_report(report_type="threat")
]

results = await asyncio.gather(*tasks)
compliance_result, threat_patterns, report_data = results
```text

### 4. Health Monitoring

**Service Health Checks:**

```python
# Monitor service health
health_status = service.get_health_status()
print(f"Overall status: {health_status['overall_status']}")
print(f"Services initialized: {health_status['initialized_services']}")

# Get detailed metrics
metrics = await service.get_metrics_summary()
print(f"Events processed: {metrics.get('events_processed', 0)}")
```text

## Configuration Reference

### Environment Configurations

**Development:**

```python
config = create_development_config()
# Uses:
# - Local PostgreSQL database
# - Local Redis cache
# - Local Elasticsearch
# - File-based reports
```text

**Production:**

```python
config = create_production_config()
# Uses:
# - Production database cluster
# - Redis cluster
# - Elasticsearch cluster
# - Networked storage for reports
# - Higher connection pools
# - Extended cache limits
```text

**Testing:**

```python
config = create_test_config()
# Uses:
# - In-memory SQLite database
# - Separate Redis database
# - Minimal cache limits
# - Temporary report storage
```text

### Custom Configuration

```python
config = AuditComplianceConfig(
    # Database settings
    database_url="postgresql://host:5432/audit",
    database_pool_size=50,
    database_max_overflow=100,

    # Cache settings
    redis_url="redis://redis-cluster:6379/0",
    cache_ttl_seconds=86400,
    cache_max_events=50000,

    # Elasticsearch settings
    elasticsearch_url="http://es-cluster:9200",
    elasticsearch_index="security-events-prod",
    elasticsearch_timeout=30,

    # Threat analysis settings
    threat_confidence_threshold=0.8,
    threat_analysis_window_hours=24,
    max_events_to_analyze=10000,

    # Report settings
    reports_output_directory="/var/log/security_reports",
    reports_include_charts=True,
    reports_include_recommendations=True,

    # Compliance frameworks
    compliance_frameworks=["GDPR", "HIPAA", "SOX", "PCI_DSS", "ISO27001"]
)
```text

## Testing Strategy

### Integration Tests

Run the comprehensive test suite:

```bash
# Run all integration tests
pytest mmf/services/audit_compliance/tests/integration/ -v

# Run specific test categories
pytest mmf/services/audit_compliance/tests/integration/test_audit_compliance_integration.py::TestAuditEventOperations -v

# Run performance tests
pytest mmf/services/audit_compliance/tests/integration/test_audit_compliance_integration.py::TestPerformanceAndScalability -v
```text

### Custom Testing

```python
# Test your own integration
async def test_custom_workflow():
    async with audit_compliance_service(environment="test") as service:
        # Log test events
        events = await service.bulk_log_events(test_events)

        # Verify functionality
        assert len(events) == len(test_events)

        # Test compliance scanning
        scan_result = await service.scan_compliance(
            [ComplianceFramework.GDPR],
            "test_system"
        )

        assert scan_result.overall_score >= 0
```text

## Performance Considerations

### 1. Bulk Operations

- Use `bulk_log_events()` for multiple events
- Leverage async/await for concurrent operations
- Cache frequently accessed data

### 2. Database Optimization

- Configure appropriate connection pool sizes
- Use database indexes for common queries
- Consider read replicas for heavy workloads

### 3. Cache Strategy

- Redis ZSET provides time-based sliding window
- Configurable cache limits prevent memory issues
- Cache hit rates improve response times

### 4. SIEM Integration

- Asynchronous event forwarding
- Batch processing for efficiency
- Configurable retry policies

## Troubleshooting

### Common Issues

**1. Service Won't Initialize**

```python
# Check configuration
config = create_development_config()
print(f"Database URL: {config.database_url}")
print(f"Redis URL: {config.redis_url}")

# Validate environment
from mmf.services.audit_compliance.tests.integration.conftest import validate_test_environment
assert validate_test_environment()
```text

**2. Database Connection Issues**

```python
# Test database connectivity
container = get_container(config)
db_manager = container.get_database_manager()
await db_manager.initialize()
```text

**3. Cache Performance Issues**

```python
# Monitor cache performance
cache = container.get_audit_event_cache()
cache_stats = await cache.get_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']}")
```text

**4. High Memory Usage**

```python
# Adjust cache limits
config.cache_max_events = 10000  # Reduce from default
config.cache_ttl_seconds = 3600  # Reduce from 24 hours
```text

### Debug Mode

Enable verbose logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Initialize service with debug configuration
service = await create_audit_compliance_service(
    config=config,
    environment="development"
)
```text

## Migration Checklist

### Pre-Migration

- [ ] Review current audit_compliance usage
- [ ] Identify custom configurations
- [ ] Plan testing strategy
- [ ] Set up new environment (database, Redis, Elasticsearch)

### During Migration

- [ ] Update import statements
- [ ] Migrate configuration to new format
- [ ] Update service initialization code
- [ ] Migrate event logging calls
- [ ] Update compliance scanning logic
- [ ] Migrate threat analysis code
- [ ] Update report generation
- [ ] Add error handling for async operations

### Post-Migration

- [ ] Run integration tests
- [ ] Verify performance meets requirements
- [ ] Monitor service health
- [ ] Validate data integrity
- [ ] Update monitoring and alerting
- [ ] Train team on new APIs

### Rollback Plan

- [ ] Keep old code available during transition
- [ ] Implement feature flags for gradual rollout
- [ ] Monitor key metrics during migration
- [ ] Have rollback procedure documented

## Support and Resources

### Documentation

- [Architecture Decision Records](./docs/architecture/)
- [API Reference](./docs/api/)
- [Configuration Guide](./docs/configuration/)

### Code Examples

- [Basic Usage Examples](./examples/)
- [Integration Patterns](./examples/integration/)
- [Performance Optimization](./examples/performance/)

### Community

- Report issues in the project repository
- Join discussion forums for questions
- Contribute improvements and extensions

## Conclusion

The migration to hexagonal architecture provides:

1. **Better Separation of Concerns**: Clean domain logic separated from infrastructure
2. **Improved Testability**: Comprehensive test coverage with mocking capabilities
3. **Enhanced Maintainability**: Modular design with clear interfaces
4. **Greater Extensibility**: Easy to add new features and integrations
5. **Framework Integration**: Seamless integration with mmf core services
6. **Performance Improvements**: Async operations, caching, and bulk processing
7. **Production Ready**: Health checks, metrics, and monitoring built-in

The new architecture provides a solid foundation for future enhancements while maintaining backwards compatibility through the migration period.
