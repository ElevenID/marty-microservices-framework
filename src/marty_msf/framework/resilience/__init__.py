"""
Advanced Resilience Patterns Framework

Provides enterprise-grade resilience patterns for microservices including:
- Circuit Breakers: Prevent cascading failures
- Retry Mechanisms: Exponential backoff and jittered retries
- Bulkhead Isolation: Resource isolation and thread pools
- Connection Pools: HTTP, Redis, and database connection pooling
- Timeout Management: Request and operation timeouts
- Fallback Strategies: Graceful degradation patterns
- Chaos Engineering: Fault injection and resilience testing
- Enhanced Monitoring: Comprehensive metrics and health checks
- Middleware Integration: FastAPI and other framework integration
- Consolidated Resilience Manager: Unified resilience patterns (NEW)
- API & Bootstrap Pattern: Level contract architecture for dependency management
"""

# Import API interfaces and data models
from .api import (
    BulkheadRejectedError,
    CircuitBreakerOpenError,
    IResilienceManager,
    IResilienceService,
    ResilienceConfig,
    ResilienceMetrics,
    ResilienceStrategy,
    ResilienceTimeoutError,
    RetryExhaustedError,
)

# Import bootstrap for dependency injection
from .bootstrap import ResilienceBootstrap

# Import basic resilience patterns
from .bulkhead import (
    BulkheadConfig,
    BulkheadError,
    BulkheadPool,
    SemaphoreBulkhead,
    ThreadPoolBulkhead,
    bulkhead_isolate,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
)

# Import connection pools and middleware
# Import connection pools and middleware
from .connection_pools import (
    ConnectionPoolManager,
    HealthCheckConfig,
    HTTPConnectionPool,
    HTTPPoolConfig,
    PoolConfig,
    PoolHealthChecker,
    RedisConnectionPool,
    RedisPoolConfig,
)
from .connection_pools.manager import (
    close_all_pools,
    get_pool,
    get_pool_manager,
    initialize_pools,
)

# Import consolidated resilience manager (NEW)
from .consolidated_manager import (
    ConsolidatedResilienceConfig,
    ConsolidatedResilienceManager,
    create_consolidated_resilience_manager,
)

# Enhanced resilience patterns will be imported when available
# from .enhanced import (...) - Module not yet implemented
# from .external_dependencies import (...) - Module not yet implemented
# Enhanced resilience patterns
from .fallback import (
    CacheFallback,
    FallbackConfig,
    FallbackError,
    FallbackStrategy,
    FunctionFallback,
    StaticFallback,
    with_fallback,
)
from .middleware import (
    ResilienceMiddleware,
    ResilienceService,
    close_resilience_service,
    get_resilience_service,
    resilient,
)
from .patterns import (
    ResilienceManager,
    ResiliencePattern,
    initialize_resilience,
    resilience_pattern,
)
from .retry import (
    ConstantBackoff,
    ExponentialBackoff,
    LinearBackoff,
    RetryConfig,
    RetryError,
    RetryStrategy,
    retry_async,
    retry_with_circuit_breaker,
)
from .timeout import TimeoutConfig, TimeoutManager, timeout_async, with_timeout

__all__ = [
    # Basic resilience patterns
    "BulkheadConfig",
    "BulkheadError",
    "BulkheadPool",
    "CacheFallback",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "ConstantBackoff",
    "ExponentialBackoff",
    "FallbackConfig",
    "FallbackError",
    "FallbackStrategy",
    "FunctionFallback",
    "LinearBackoff",
    "ResilienceConfig",
    "ResilienceManager",
    "ResiliencePattern",
    "ResilienceTimeoutError",
    "RetryConfig",
    "RetryError",
    "RetryStrategy",
    "SemaphoreBulkhead",
    "StaticFallback",
    "ThreadPoolBulkhead",
    "TimeoutConfig",
    "TimeoutManager",
    "bulkhead_isolate",
    "circuit_breaker",
    "initialize_resilience",
    "resilience_pattern",
    "retry_async",
    "retry_with_circuit_breaker",
    "timeout_async",
    "with_fallback",
    "with_timeout",

    # Connection pools and middleware
    "HTTPConnectionPool",
    "HTTPPoolConfig",
    "RedisConnectionPool",
    "RedisPoolConfig",
    "ConnectionPoolManager",
    "PoolConfig",
    "PoolHealthChecker",
    "HealthCheckConfig",
    "ResilienceMiddleware",
    "ResilienceService",
    "resilient",
    "get_pool_manager",
    "initialize_pools",
    "get_pool",
    "close_all_pools",
    "get_resilience_service",
    "close_resilience_service",

    # Consolidated Resilience Manager (NEW)
    "ConsolidatedResilienceConfig",
    "ConsolidatedResilienceManager",
    "create_consolidated_resilience_manager",

    # API and Bootstrap Pattern (NEW)
    "IResilienceManager",
    "IResilienceService",
    "ResilienceBootstrap",
]
