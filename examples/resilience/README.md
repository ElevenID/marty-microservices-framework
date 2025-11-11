# Resilience Framework Examples

This directory contains examples demonstrating the resilience patterns and capabilities of the Marty Microservices Framework.

## Overview

The resilience framework provides:

- **Standardized Connection Pools**: HTTP and Redis connection pooling with health checking
- **Circuit Breakers**: Automatic failure detection and recovery
- **Bulkheads**: Resource isolation and concurrency control
- **Middleware Integration**: Seamless FastAPI integration
- **Load Testing**: Comprehensive testing framework for validation
- **Health Monitoring**: Real-time health checks and metrics

## Examples

### 1. Example Resilient Service (`example_resilient_service.py`)

A complete FastAPI service demonstrating all resilience patterns:

```bash
# Run the example service
python examples/resilience/example_resilient_service.py
```

**Features:**

- HTTP connection pooling for external API calls
- Redis connection pooling with caching
- Circuit breaker protection
- Bulkhead isolation for different operations
- Health check endpoints
- Error simulation for testing
- Comprehensive logging and metrics

**Endpoints:**

- `GET /health` - Health check
- `GET /health/detailed` - Detailed health information
- `GET /api/external-data` - External API call with circuit breaker
- `GET /api/cache/{key}` - Redis cache operations
- `POST /api/cache/{key}` - Set cache value
- `GET /api/heavy-computation` - CPU-intensive operation with bulkhead
- `GET /api/error-prone` - Simulated errors for circuit breaker testing
- `GET /metrics` - Prometheus-style metrics

### 2. Load Testing Script (`run_load_tests.py`)

Comprehensive load testing to validate resilience under realistic concurrency:

```bash
# Start the example service first
python examples/resilience/example_resilient_service.py

# Then run load tests in another terminal
python examples/resilience/run_load_tests.py
```

**Test Types:**

- **Individual Tests**: Custom spike testing scenarios
- **Resilience Suite**: Pre-configured test scenarios covering all patterns
- **Endurance Tests**: Long-duration stability testing

**Validation:**

- Error rate thresholds
- Response time percentiles (P95, P99)
- Throughput requirements
- Circuit breaker behavior
- Connection pool health
- Bulkhead effectiveness

## Quick Start

1. **Start the Example Service:**

   ```bash
   cd /path/to/marty-microservices-framework
   python examples/resilience/example_resilient_service.py
   ```

2. **Test Basic Functionality:**

   ```bash
   # Health check
   curl http://localhost:8000/health

   # External data with circuit breaker
   curl http://localhost:8000/api/external-data

   # Cache operations
   curl -X POST http://localhost:8000/api/cache/test -d '{"value": "hello"}'
   curl http://localhost:8000/api/cache/test

   # Heavy computation with bulkhead
   curl http://localhost:8000/api/heavy-computation
   ```

3. **Run Load Tests:**

   ```bash
   python examples/resilience/run_load_tests.py
   ```

4. **Monitor Health:**

   ```bash
   # Detailed health information
   curl http://localhost:8000/health/detailed

   # Metrics
   curl http://localhost:8000/metrics
   ```

## Resilience Patterns Demonstrated

### Connection Pooling

The example service shows how to:

- Configure HTTP connection pools with health checking
- Set up Redis connection pools with cluster support
- Manage pool lifecycle and monitoring
- Handle connection failures gracefully

```python
from marty_msf.framework.resilience.connection_pools import (
    HTTPConnectionPool,
    RedisConnectionPool,
    ConnectionPoolManager
)

# HTTP pool configuration
http_pool = HTTPConnectionPool(
    name="external_api",
    base_url="https://httpbin.org",
    max_connections=50,
    max_connections_per_host=10,
    connection_timeout=5.0,
    read_timeout=30.0,
    health_check_interval=60,
    health_check_path="/status/200"
)

# Redis pool configuration
redis_pool = RedisConnectionPool(
    name="main_cache",
    host="localhost",
    port=6379,
    max_connections=20,
    health_check_interval=60
)
```

### Circuit Breakers

Automatic failure detection and recovery:

```python
from marty_msf.framework.resilience.patterns import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,      # Trip after 5 failures
    recovery_timeout=30,      # Try recovery after 30s
    expected_exception=Exception
)

@circuit_breaker
async def protected_operation():
    # This operation is protected by circuit breaker
    return await external_service_call()
```

### Bulkheads

Resource isolation and concurrency control:

```python
from marty_msf.framework.resilience.patterns import SemaphoreBulkhead

# Limit concurrent heavy operations
heavy_computation_bulkhead = SemaphoreBulkhead(
    name="heavy_computation",
    max_concurrent=3
)

async def heavy_operation():
    async with heavy_computation_bulkhead:
        # Resource-intensive operation
        return await cpu_intensive_task()
```

### Middleware Integration

Automatic resilience for all FastAPI routes:

```python
from marty_msf.framework.resilience.middleware import ResilienceMiddleware

app = FastAPI()
app.add_middleware(
    ResilienceMiddleware,
    timeout=30.0,
    rate_limit_requests=100,
    rate_limit_window=60,
    circuit_breaker_enabled=True,
    bulkhead_enabled=True
)
```

## Load Testing Scenarios

The load testing framework provides several pre-configured scenarios:

### Basic Load Test

- Gradual ramp-up to moderate load
- Validates basic functionality under load
- Checks response times and error rates

### Spike Test

- Sudden increase in load
- Tests circuit breaker activation
- Validates connection pool behavior

### Endurance Test

- Long-duration sustained load
- Checks for memory leaks and performance degradation
- Validates system stability over time

### Chaos Test

- Introduces random failures
- Tests recovery mechanisms
- Validates overall system resilience

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# External API Configuration
EXTERNAL_API_BASE_URL=https://httpbin.org
EXTERNAL_API_TIMEOUT=30

# Resilience Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30
BULKHEAD_MAX_CONCURRENT=10

# Load Testing Configuration
LOAD_TEST_OUTPUT_DIR=./load_test_results
LOAD_TEST_MAX_USERS=50
LOAD_TEST_DURATION=120
```

### Configuration Files

The framework supports YAML configuration:

```yaml
# config/resilience.yaml
resilience:
  connection_pools:
    http:
      external_api:
        base_url: "https://httpbin.org"
        max_connections: 50
        connection_timeout: 5.0
        health_check_interval: 60

    redis:
      main_cache:
        host: "localhost"
        port: 6379
        max_connections: 20
        health_check_interval: 60

  circuit_breakers:
    default:
      failure_threshold: 5
      recovery_timeout: 30

  bulkheads:
    heavy_computation:
      max_concurrent: 3

  middleware:
    timeout: 30.0
    rate_limit_requests: 100
    rate_limit_window: 60
```

## Monitoring and Observability

### Health Checks

The framework provides comprehensive health checking:

- **Connection Pool Health**: Pool size, active connections, failed connections
- **Circuit Breaker Status**: Open/closed state, failure count, last failure time
- **Bulkhead Metrics**: Active operations, queue size, rejection count
- **Overall System Health**: Aggregated health status

### Metrics

Prometheus-compatible metrics are available:

```
# Connection pool metrics
connection_pool_active_connections{pool_name="external_api"} 5
connection_pool_failed_connections{pool_name="external_api"} 0
connection_pool_health_check_failures{pool_name="external_api"} 0

# Circuit breaker metrics
circuit_breaker_state{name="external_api"} 0  # 0=closed, 1=open, 2=half-open
circuit_breaker_failure_count{name="external_api"} 2
circuit_breaker_success_count{name="external_api"} 98

# Bulkhead metrics
bulkhead_active_operations{name="heavy_computation"} 2
bulkhead_rejected_operations{name="heavy_computation"} 0
```

### Logging

Structured logging provides detailed insights:

```python
logger.info("Circuit breaker opened", extra={
    "circuit_breaker": "external_api",
    "failure_count": 5,
    "failure_threshold": 5,
    "recovery_timeout": 30
})

logger.info("Connection pool health check failed", extra={
    "pool_name": "redis_cache",
    "error": "Connection timeout",
    "consecutive_failures": 3
})
```

## Testing Circuit Breakers

To test circuit breaker behavior:

1. Start the example service
2. Call the error-prone endpoint multiple times:

   ```bash
   # This will cause failures and eventually trip the circuit breaker
   for i in {1..10}; do curl http://localhost:8000/api/error-prone; echo; done
   ```

3. Monitor the health endpoint to see circuit breaker status:

   ```bash
   curl http://localhost:8000/health/detailed
   ```

## Performance Characteristics

### Connection Pools

- **HTTP Pools**: 50-100 concurrent connections, sub-millisecond acquisition
- **Redis Pools**: 20-50 connections, microsecond command execution
- **Health Checks**: Background monitoring with configurable intervals
- **Recovery**: Automatic bad connection replacement

### Circuit Breakers

- **Detection**: Configurable failure thresholds (typically 3-10 failures)
- **Recovery**: Exponential backoff with configurable timeouts
- **Overhead**: <1ms per operation when closed
- **Half-Open Testing**: Single request validation before full recovery

### Bulkheads

- **Semaphore Bulkheads**: Nanosecond acquisition, memory-efficient
- **Thread Pool Bulkheads**: Microsecond task submission, CPU isolation
- **Queue Management**: Configurable queue sizes and rejection policies
- **Monitoring**: Real-time metrics for capacity and utilization

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   - Increase pool size or connection timeout
   - Check for connection leaks in application code
   - Monitor pool metrics for usage patterns

2. **Circuit Breaker False Positives**
   - Adjust failure threshold or recovery timeout
   - Check for transient network issues
   - Review error classification logic

3. **Bulkhead Resource Starvation**
   - Increase bulkhead capacity
   - Optimize operation performance
   - Consider operation prioritization

4. **Load Test Failures**
   - Verify service is running and accessible
   - Check resource constraints (CPU, memory, network)
   - Adjust test parameters for local environment

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger("marty_msf.framework.resilience").setLevel(logging.DEBUG)
```

## Best Practices

1. **Connection Pool Sizing**
   - Start with conservative sizes (10-50 connections)
   - Monitor utilization and adjust based on actual usage
   - Consider connection setup/teardown costs

2. **Circuit Breaker Configuration**
   - Set failure thresholds based on acceptable error rates
   - Use appropriate recovery timeouts (30-60 seconds)
   - Implement proper fallback mechanisms

3. **Bulkhead Design**
   - Isolate different types of operations
   - Size bulkheads based on resource capacity
   - Monitor rejection rates and queue depths

4. **Load Testing Strategy**
   - Start with baseline performance tests
   - Gradually increase load to find breaking points
   - Test different failure scenarios (chaos engineering)
   - Validate under sustained load (endurance testing)

5. **Monitoring and Alerting**
   - Set up alerts for circuit breaker state changes
   - Monitor connection pool health continuously
   - Track bulkhead utilization and rejections
   - Review load test results regularly

## Integration with Existing Services

To integrate the resilience framework into existing services:

1. **Add Dependencies**

   ```python
   from marty_msf.framework.resilience import (
       ConnectionPoolManager,
       ResilienceMiddleware
   )
   ```

2. **Configure Connection Pools**

   ```python
   pool_manager = ConnectionPoolManager()
   await pool_manager.create_http_pool("api", base_url="https://api.example.com")
   await pool_manager.create_redis_pool("cache", host="redis.example.com")
   ```

3. **Add Middleware**

   ```python
   app.add_middleware(ResilienceMiddleware)
   ```

4. **Use Pools in Handlers**

   ```python
   @app.get("/data")
   async def get_data():
       async with pool_manager.get_http_pool("api") as client:
           response = await client.get("/data")
           return response.json()
   ```

5. **Monitor and Test**

   ```python
   # Add health checks
   @app.get("/health")
   async def health():
       return await pool_manager.get_health_status()
   ```

This comprehensive resilience framework provides a solid foundation for building robust, scalable microservices that can handle failures gracefully and maintain performance under load.
