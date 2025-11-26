"""
Enhanced Resilience Framework Integration for Marty Microservices Framework

This module provides comprehensive resilience patterns by integrating Marty's
advanced resilience capabilities into the MMF, including:
- Chaos engineering and fault injection
- Advanced retry mechanisms with multiple backoff strategies
- Enhanced circuit breakers with monitoring
- Comprehensive gRPC interceptors
- Graceful degradation patterns
- Integrated metrics and monitoring
"""

from .advanced_retry import (
    AdvancedRetryConfig,
    AdvancedRetryManager,
    AdvancedRetryMetrics,
    BackoffStrategy,
    RetryResult,
    async_retry_with_advanced_policy,
    get_all_retry_manager_stats,
    get_retry_manager,
    retry_with_advanced_policy,
)
from .chaos_engineering import (
    ChaosConfig,
    ChaosInjector,
    ChaosType,
    ResilienceTestSuite,
    chaos_context,
)
from .enhanced_circuit_breaker import (
    CircuitBreakerState,
    DefaultErrorClassifier,
    EnhancedCircuitBreaker,
    EnhancedCircuitBreakerConfig,
    ErrorClassifier,
)
from .graceful_degradation import (
    CachedValueProvider,
    DefaultValueProvider,
    DegradationLevel,
    FallbackProvider,
    FeatureToggle,
    GracefulDegradationManager,
    HealthBasedDegradationMonitor,
    ServiceFallbackProvider,
)
from .grpc_interceptors import (
    AsyncResilienceClientInterceptor,
    CompositeResilienceInterceptor,
    EnhancedResilienceServerInterceptor,
    ResilienceClientInterceptor,
)
from .monitoring import (
    ResilienceHealthCheck,
    ResilienceMonitor,
    generate_resilience_health_report,
    get_global_monitor,
    get_resilience_health_status,
    register_circuit_breaker_for_monitoring,
    register_retry_manager_for_monitoring,
)
from .outbound_resilience import async_call_with_resilience

__all__ = [
    # Advanced retry mechanisms
    "AdvancedRetryConfig",
    "AdvancedRetryManager",
    "AdvancedRetryMetrics",
    "async_retry_with_advanced_policy",
    "BackoffStrategy",
    "get_all_retry_manager_stats",
    "get_retry_manager",
    "retry_with_advanced_policy",
    "RetryResult",
    # Chaos engineering
    "ChaosConfig",
    "ChaosInjector",
    "ChaosType",
    "ResilienceTestSuite",
    "chaos_context",
    # Enhanced circuit breaker
    "EnhancedCircuitBreaker",
    "EnhancedCircuitBreakerConfig",
    "CircuitBreakerState",
    "ErrorClassifier",
    "DefaultErrorClassifier",
    # Graceful degradation
    "CachedValueProvider",
    "DefaultValueProvider",
    "DegradationLevel",
    "FallbackProvider",
    "FeatureToggle",
    "GracefulDegradationManager",
    "HealthBasedDegradationMonitor",
    "ServiceFallbackProvider",
    # gRPC interceptors
    "AsyncResilienceClientInterceptor",
    "CompositeResilienceInterceptor",
    "EnhancedResilienceServerInterceptor",
    "ResilienceClientInterceptor",
    # Monitoring
    "ResilienceHealthCheck",
    "ResilienceMonitor",
    "generate_resilience_health_report",
    "get_global_monitor",
    "get_resilience_health_status",
    "register_circuit_breaker_for_monitoring",
    "register_retry_manager_for_monitoring",
    # Outbound calls
    "async_call_with_resilience",
]
