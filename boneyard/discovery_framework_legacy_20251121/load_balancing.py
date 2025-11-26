"""
Load Balancing Strategies and Algorithms

Comprehensive load balancing framework with multiple algorithms including
round-robin, weighted, least-connections, consistent hashing, and adaptive strategies.
"""

import asyncio
import builtins
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .core import ServiceInstance

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing strategy types."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"
    CONSISTENT_HASH = "consistent_hash"
    IP_HASH = "ip_hash"
    HEALTH_BASED = "health_based"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


class StickySessionType(Enum):
    """Sticky session types."""

    NONE = "none"
    SOURCE_IP = "source_ip"
    COOKIE = "cookie"
    HEADER = "header"
    CUSTOM = "custom"


@dataclass
class LoadBalancingConfig:
    """Configuration for load balancing."""

    # Strategy configuration
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    fallback_strategy: LoadBalancingStrategy = LoadBalancingStrategy.RANDOM

    # Health checking
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2

    # Sticky sessions
    sticky_sessions: StickySessionType = StickySessionType.NONE
    session_timeout: float = 3600.0  # 1 hour

    # Circuit breaker integration
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_half_open_max_calls: int = 3

    # Adaptive behavior
    adaptive_enabled: bool = False
    adaptive_window_size: int = 100
    adaptive_adjustment_factor: float = 0.1

    # Performance settings
    max_retries: int = 3
    retry_delay: float = 1.0
    connection_timeout: float = 5.0

    # Consistent hashing
    virtual_nodes: int = 150
    hash_function: str = "md5"  # md5, sha1, sha256

    # Monitoring
    enable_metrics: bool = True
    metrics_window_size: int = 1000


@dataclass
class LoadBalancingContext:
    """Context for load balancing decisions."""

    # Request information
    client_ip: str | None = None
    session_id: str | None = None
    request_headers: builtins.dict[str, str] = field(default_factory=dict)
    request_path: str | None = None
    request_method: str | None = None

    # Load balancing hints
    preferred_zone: str | None = None
    preferred_region: str | None = None
    exclude_instances: builtins.set[str] = field(default_factory=set)

    # Custom data
    custom_data: builtins.dict[str, Any] = field(default_factory=dict)


class LoadBalancer(ABC):
    """Abstract load balancer interface."""

    def __init__(self, config: LoadBalancingConfig):
        self.config = config
        self._instances: builtins.list[ServiceInstance] = []
        self._last_update = 0.0

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "instance_selections": {},
            "strategy_switches": 0,
        }

    async def update_instances(self, instances: builtins.list[ServiceInstance]):
        """Update the list of available instances."""
        # Filter healthy instances if health checking is enabled
        if self.config.health_check_enabled:
            instances = [instance for instance in instances if instance.is_healthy()]

        self._instances = instances
        self._last_update = time.time()

        # Reset selection counters for new instances
        for instance in instances:
            if instance.instance_id not in self._stats["instance_selections"]:
                self._stats["instance_selections"][instance.instance_id] = 0

    @abstractmethod
    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select an instance using the load balancing strategy."""

    async def select_with_fallback(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance with fallback strategy if primary fails."""
        try:
            instance = await self.select_instance(context)
            if instance:
                return instance
        except Exception as e:
            logger.warning("Primary load balancing strategy failed: %s", e)
            self._stats["strategy_switches"] += 1

        # Try fallback strategy
        if self.config.fallback_strategy != self.config.strategy:
            try:
                fallback_balancer = self._create_fallback_balancer()
                await fallback_balancer.update_instances(self._instances)
                return await fallback_balancer.select_instance(context)
            except Exception as e:
                logger.error("Fallback load balancing strategy failed: %s", e)

        return None

    def _create_fallback_balancer(self) -> "LoadBalancer":
        """Create fallback balancer instance."""
        fallback_config = LoadBalancingConfig(strategy=self.config.fallback_strategy)
        return create_load_balancer(fallback_config)

    def record_request(self, instance: ServiceInstance, success: bool, response_time: float):
        """Record request result for metrics."""
        self._stats["total_requests"] += 1

        if success:
            self._stats["successful_requests"] += 1
        else:
            self._stats["failed_requests"] += 1

        self._stats["total_response_time"] += response_time
        self._stats["instance_selections"][instance.instance_id] = (
            self._stats["instance_selections"].get(instance.instance_id, 0) + 1
        )

        # Update instance statistics
        instance.record_request(response_time, success)

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get load balancer statistics."""
        avg_response_time = 0.0
        if self._stats["total_requests"] > 0:
            avg_response_time = self._stats["total_response_time"] / self._stats["total_requests"]

        success_rate = 0.0
        if self._stats["total_requests"] > 0:
            success_rate = self._stats["successful_requests"] / self._stats["total_requests"]

        return {
            **self._stats,
            "average_response_time": avg_response_time,
            "success_rate": success_rate,
            "instance_count": len(self._instances),
            "healthy_instances": len([i for i in self._instances if i.is_healthy()]),
            "last_update": self._last_update,
        }


class RoundRobinBalancer(LoadBalancer):
    """Round-robin load balancer."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._current_index = 0

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select next instance in round-robin order."""
        if not self._instances:
            return None

        # Handle sticky sessions
        if context and self.config.sticky_sessions != StickySessionType.NONE:
            sticky_instance = await self._get_sticky_instance(context)
            if sticky_instance:
                return sticky_instance

        # Select next instance
        instance = self._instances[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._instances)

        return instance

    async def _get_sticky_instance(self, context: LoadBalancingContext) -> ServiceInstance | None:
        """Get instance based on sticky session configuration."""
        if self.config.sticky_sessions == StickySessionType.SOURCE_IP and context.client_ip:
            # Hash client IP to instance
            hash_value = hashlib.sha256(context.client_ip.encode()).hexdigest()
            index = int(hash_value, 16) % len(self._instances)
            return self._instances[index]

        if self.config.sticky_sessions == StickySessionType.COOKIE and context.session_id:
            # Hash session ID to instance
            hash_value = hashlib.sha256(context.session_id.encode()).hexdigest()
            index = int(hash_value, 16) % len(self._instances)
            return self._instances[index]

        return None


class WeightedRoundRobinBalancer(LoadBalancer):
    """Weighted round-robin load balancer."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._current_weights: builtins.dict[str, float] = {}
        self._effective_weights: builtins.dict[str, float] = {}
        self._total_weight = 0.0

    async def update_instances(self, instances: builtins.list[ServiceInstance]):
        """Update instances and recalculate weights."""
        await super().update_instances(instances)
        self._calculate_weights()

    def _calculate_weights(self):
        """Calculate effective weights for instances."""
        self._current_weights = {}
        self._effective_weights = {}
        self._total_weight = 0.0

        for instance in self._instances:
            weight = instance.get_weight()
            self._current_weights[instance.instance_id] = weight
            self._effective_weights[instance.instance_id] = weight
            self._total_weight += weight

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance using weighted round-robin algorithm."""
        if not self._instances or self._total_weight <= 0:
            return None

        # Find instance with highest current weight
        selected_instance = None
        max_weight = -1.0

        for instance in self._instances:
            instance_id = instance.instance_id
            current_weight = self._current_weights.get(instance_id, 0)

            if current_weight > max_weight:
                max_weight = current_weight
                selected_instance = instance

        if not selected_instance:
            return None

        # Update weights
        selected_id = selected_instance.instance_id
        self._current_weights[selected_id] -= self._total_weight

        # Restore weights
        for instance in self._instances:
            instance_id = instance.instance_id
            effective_weight = self._effective_weights.get(instance_id, 0)
            self._current_weights[instance_id] += effective_weight

        return selected_instance


class LeastConnectionsBalancer(LoadBalancer):
    """Least connections load balancer."""

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance with least active connections."""
        if not self._instances:
            return None

        # Find instance with minimum connections
        min_connections = float("inf")
        selected_instance = None

        for instance in self._instances:
            if instance.active_connections < min_connections:
                min_connections = instance.active_connections
                selected_instance = instance

        return selected_instance


class WeightedLeastConnectionsBalancer(LoadBalancer):
    """Weighted least connections load balancer."""

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance with best connections-to-weight ratio."""
        if not self._instances:
            return None

        # Find instance with minimum connections/weight ratio
        min_ratio = float("inf")
        selected_instance = None

        for instance in self._instances:
            weight = instance.get_weight()
            if weight <= 0:
                continue

            ratio = instance.active_connections / weight
            if ratio < min_ratio:
                min_ratio = ratio
                selected_instance = instance

        return selected_instance


class RandomBalancer(LoadBalancer):
    """Random load balancer."""

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select random instance."""
        if not self._instances:
            return None

        return random.choice(self._instances)


class WeightedRandomBalancer(LoadBalancer):
    """Weighted random load balancer."""

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select random instance based on weights."""
        if not self._instances:
            return None

        # Calculate total weight
        total_weight = sum(instance.get_weight() for instance in self._instances)
        if total_weight <= 0:
            return random.choice(self._instances)

        # Select random weight point
        random_weight = random.uniform(0, total_weight)

        # Find corresponding instance
        current_weight = 0.0
        for instance in self._instances:
            current_weight += instance.get_weight()
            if random_weight <= current_weight:
                return instance

        # Fallback to last instance
        return self._instances[-1]


class ConsistentHashBalancer(LoadBalancer):
    """Consistent hash load balancer."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._hash_ring: builtins.dict[int, ServiceInstance] = {}
        self._sorted_keys: builtins.list[int] = []

    async def update_instances(self, instances: builtins.list[ServiceInstance]):
        """Update instances and rebuild hash ring."""
        await super().update_instances(instances)
        self._build_hash_ring()

    def _build_hash_ring(self):
        """Build consistent hash ring."""
        self._hash_ring = {}

        for instance in self._instances:
            for i in range(self.config.virtual_nodes):
                key = f"{instance.instance_id}:{i}"
                hash_value = self._hash_key(key)
                self._hash_ring[hash_value] = instance

        self._sorted_keys = sorted(self._hash_ring.keys())

    def _hash_key(self, key: str) -> int:
        """Hash a key using configured hash function."""
        if self.config.hash_function == "md5":
            # MD5 is deprecated for security, using SHA256 instead
            return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        if self.config.hash_function == "sha1":
            # SHA1 is deprecated for security, using SHA256 instead
            return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        if self.config.hash_function == "sha256":
            return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        # Default to sha256 for security
        return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance using consistent hashing."""
        if not self._instances or not self._sorted_keys:
            return None

        # Determine hash key
        hash_key = self._get_hash_key(context)
        hash_value = self._hash_key(hash_key)

        # Find next instance in ring
        for key in self._sorted_keys:
            if hash_value <= key:
                return self._hash_ring[key]

        # Wrap around to first instance
        return self._hash_ring[self._sorted_keys[0]]

    def _get_hash_key(self, context: LoadBalancingContext | None) -> str:
        """Get hash key from context."""
        if context:
            if context.session_id:
                return context.session_id
            if context.client_ip:
                return context.client_ip
            if context.request_path:
                return context.request_path

        # Fallback to random key for even distribution
        return str(random.random())


class HealthBasedBalancer(LoadBalancer):
    """Health-based load balancer that prioritizes healthy instances."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._base_balancer = RoundRobinBalancer(config)

    async def update_instances(self, instances: builtins.list[ServiceInstance]):
        """Update instances for both this and base balancer."""
        await super().update_instances(instances)
        await self._base_balancer.update_instances(instances)

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance prioritizing health and performance."""
        if not self._instances:
            return None

        # Categorize instances by health
        healthy_instances = [i for i in self._instances if i.is_healthy()]
        available_instances = [i for i in self._instances if i.is_available()]

        # Prefer healthy instances
        if healthy_instances:
            # Use base balancer for healthy instances
            temp_balancer = RoundRobinBalancer(self.config)
            await temp_balancer.update_instances(healthy_instances)
            return await temp_balancer.select_instance(context)

        # Fallback to available instances
        if available_instances:
            temp_balancer = RoundRobinBalancer(self.config)
            await temp_balancer.update_instances(available_instances)
            return await temp_balancer.select_instance(context)

        # Last resort: any instance
        return await self._base_balancer.select_instance(context)


class AdaptiveBalancer(LoadBalancer):
    """Adaptive load balancer that adjusts strategy based on performance."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._strategies = [
            RoundRobinBalancer(config),
            LeastConnectionsBalancer(config),
            WeightedRandomBalancer(config),
        ]
        self._current_strategy = 0
        self._performance_history: builtins.list[float] = []
        self._strategy_performance: builtins.dict[int, builtins.list[float]] = {
            i: [] for i in range(len(self._strategies))
        }
        self._last_adaptation = 0.0

    async def update_instances(self, instances: builtins.list[ServiceInstance]):
        """Update instances for all strategies."""
        await super().update_instances(instances)

        for strategy in self._strategies:
            await strategy.update_instances(instances)

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance using adaptive strategy."""
        if not self._instances:
            return None

        # Adapt strategy if needed
        await self._adapt_strategy()

        # Use current strategy
        current_balancer = self._strategies[self._current_strategy]
        return await current_balancer.select_instance(context)

    async def _adapt_strategy(self):
        """Adapt load balancing strategy based on performance."""
        current_time = time.time()

        # Only adapt periodically
        if current_time - self._last_adaptation < 60.0:  # 1 minute
            return

        self._last_adaptation = current_time

        # Calculate average performance for each strategy
        best_strategy = self._current_strategy
        best_performance = float("inf")

        for i, performance_list in self._strategy_performance.items():
            if len(performance_list) >= 10:  # Minimum samples
                avg_response_time = sum(performance_list[-50:]) / min(50, len(performance_list))

                if avg_response_time < best_performance:
                    best_performance = avg_response_time
                    best_strategy = i

        # Switch strategy if significant improvement
        if best_strategy != self._current_strategy:
            improvement = (
                sum(self._strategy_performance[self._current_strategy][-10:]) / 10
                - best_performance
            ) / best_performance

            if improvement > self.config.adaptive_adjustment_factor:
                logger.info(
                    "Switching load balancing strategy from %d to %d (%.2f%% improvement)",
                    self._current_strategy,
                    best_strategy,
                    improvement * 100,
                )
                self._current_strategy = best_strategy

    def record_request(self, instance: ServiceInstance, success: bool, response_time: float):
        """Record request result for adaptive learning."""
        super().record_request(instance, success, response_time)

        # Record performance for current strategy
        strategy_perf = self._strategy_performance[self._current_strategy]
        strategy_perf.append(response_time)

        # Keep only recent performance data
        if len(strategy_perf) > self.config.adaptive_window_size:
            strategy_perf[:] = strategy_perf[-self.config.adaptive_window_size :]


class IPHashBalancer(LoadBalancer):
    """IP hash load balancer for session affinity."""

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select instance based on client IP hash."""
        if not self._instances:
            return None

        # Use client IP if available
        if context and context.client_ip:
            hash_value = hashlib.sha256(context.client_ip.encode()).hexdigest()
            index = int(hash_value, 16) % len(self._instances)
            return self._instances[index]

        # Fallback to random selection
        return random.choice(self._instances)


def create_load_balancer(config: LoadBalancingConfig) -> LoadBalancer:
    """Factory function to create load balancer based on strategy."""

    strategy_map = {
        LoadBalancingStrategy.ROUND_ROBIN: RoundRobinBalancer,
        LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN: WeightedRoundRobinBalancer,
        LoadBalancingStrategy.LEAST_CONNECTIONS: LeastConnectionsBalancer,
        LoadBalancingStrategy.WEIGHTED_LEAST_CONNECTIONS: WeightedLeastConnectionsBalancer,
        LoadBalancingStrategy.RANDOM: RandomBalancer,
        LoadBalancingStrategy.WEIGHTED_RANDOM: WeightedRandomBalancer,
        LoadBalancingStrategy.CONSISTENT_HASH: ConsistentHashBalancer,
        LoadBalancingStrategy.IP_HASH: IPHashBalancer,
        LoadBalancingStrategy.HEALTH_BASED: HealthBasedBalancer,
        LoadBalancingStrategy.ADAPTIVE: AdaptiveBalancer,
    }

    balancer_class = strategy_map.get(config.strategy)

    if not balancer_class:
        raise ValueError(f"Unsupported load balancing strategy: {config.strategy}")

    return balancer_class(config)


class LoadBalancingMiddleware:
    """Middleware for integrating load balancing with requests."""

    def __init__(self, load_balancer: LoadBalancer):
        self.load_balancer = load_balancer

    async def handle_request(
        self,
        request_handler: Callable,
        context: LoadBalancingContext | None = None,
        max_retries: int = 3,
    ) -> Any:
        """Handle request with load balancing and retries."""

        for attempt in range(max_retries + 1):
            # Select instance
            instance = await self.load_balancer.select_with_fallback(context)

            if not instance:
                raise RuntimeError("No available instances for load balancing")

            start_time = time.time()

            try:
                # Execute request
                result = await request_handler(instance)

                # Record successful request
                response_time = time.time() - start_time
                self.load_balancer.record_request(instance, True, response_time)

                return result

            except Exception as e:
                # Record failed request
                response_time = time.time() - start_time
                self.load_balancer.record_request(instance, False, response_time)

                # Update circuit breaker if enabled
                if self.load_balancer.config.circuit_breaker_enabled:
                    instance.circuit_breaker_failures += 1
                    instance.circuit_breaker_last_failure = time.time()

                    if (
                        instance.circuit_breaker_failures
                        >= self.load_balancer.config.circuit_breaker_failure_threshold
                    ):
                        instance.circuit_breaker_open = True
                        logger.warning("Circuit breaker opened for instance: %s", instance)

                # Retry on next instance if not last attempt
                if attempt < max_retries:
                    logger.warning("Request failed, retrying with different instance: %s", e)
                    await asyncio.sleep(self.load_balancer.config.retry_delay)
                    continue

                # Re-raise exception on final attempt
                raise

        raise RuntimeError("All retry attempts exhausted")
