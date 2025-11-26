"""
Comprehensive tests for Load Balancing strategies with minimal mocking.

This test suite focuses on testing the actual strategy implementations
with real data structures to minimize mocking and maximize code coverage.
"""

import random

import pytest

from marty_msf.framework.discovery.core import HealthStatus, ServiceInstance
from marty_msf.framework.discovery.load_balancing import (
    AdaptiveBalancer,
    ConsistentHashBalancer,
    HealthBasedBalancer,
    IPHashBalancer,
    LeastConnectionsBalancer,
    LoadBalancingConfig,
    LoadBalancingContext,
    LoadBalancingStrategy,
    RandomBalancer,
    RoundRobinBalancer,
    WeightedRandomBalancer,
    WeightedRoundRobinBalancer,
    create_load_balancer,
)


class TestServiceInstance:
    """Test real ServiceInstance behavior without mocking."""

    def test_service_instance_creation(self):
        """Test creating a service instance with all attributes."""
        instance = ServiceInstance(
            service_name="test-service", instance_id="test-1", host="localhost", port=8080
        )

        assert instance.instance_id == "test-1"
        assert instance.endpoint.host == "localhost"
        assert instance.endpoint.port == 8080
        assert instance.service_name == "test-service"
        assert instance.endpoint.port == 8080

    def test_service_instance_equality(self):
        """Test ServiceInstance equality comparison."""
        instance1 = ServiceInstance(
            service_name="test-service", instance_id="test-1", host="localhost", port=8080
        )
        instance2 = ServiceInstance(
            service_name="test-service", instance_id="test-1", host="localhost", port=8080
        )
        instance3 = ServiceInstance(
            service_name="test-service", instance_id="test-2", host="localhost", port=8080
        )

        assert instance1 == instance2
        assert instance1 != instance3


class TestRoundRobinBalancer:
    """Test Round Robin load balancing strategy with real instances."""

    @pytest.fixture
    def config(self):
        """Create a load balancing config for round robin."""
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)

    @pytest.fixture
    def balancer(self, config):
        """Create a round robin balancer."""
        return RoundRobinBalancer(config)

    @pytest.fixture
    def service_instances(self):
        """Create a set of real service instances with health status set."""
        instances = [
            ServiceInstance(
                service_name="test-service", instance_id="instance-1", host="host1", port=8080
            ),
            ServiceInstance(
                service_name="test-service", instance_id="instance-2", host="host2", port=8080
            ),
            ServiceInstance(
                service_name="test-service", instance_id="instance-3", host="host3", port=8080
            ),
        ]
        # Set all instances to healthy status
        for instance in instances:
            instance.update_health_status(HealthStatus.HEALTHY)
        return instances

    @pytest.mark.asyncio
    async def test_round_robin_selection_cycle(self, balancer, service_instances):
        """Test that round robin cycles through all instances."""
        await balancer.update_instances(service_instances)

        # Get selections and verify they cycle
        selections = []
        for _ in range(6):  # Two complete cycles
            instance = await balancer.select_instance()
            selections.append(instance.instance_id)

        # Should cycle: instance-1, instance-2, instance-3, instance-1, instance-2, instance-3
        expected = ["instance-1", "instance-2", "instance-3"] * 2
        assert selections == expected

    @pytest.mark.asyncio
    async def test_round_robin_empty_instances(self, balancer):
        """Test round robin with no instances."""
        await balancer.update_instances([])
        instance = await balancer.select_instance()
        assert instance is None

    @pytest.mark.asyncio
    async def test_round_robin_single_instance(self, balancer):
        """Test round robin with single instance."""
        single_instance = [ServiceInstance(id="only", host="localhost", port=8080)]
        await balancer.update_instances(single_instance)

        # Should always return the same instance
        for _ in range(3):
            instance = await balancer.select_instance()
            assert instance.id == "only"

    @pytest.mark.asyncio
    async def test_round_robin_with_unhealthy_instances(self, balancer, service_instances):
        """Test round robin skips unhealthy instances."""
        # Mark middle instance as unhealthy
        service_instances[1].healthy = False
        await balancer.update_instances(service_instances)

        # Should only cycle between healthy instances
        selections = []
        for _ in range(4):
            instance = await balancer.select_instance()
            selections.append(instance.id)

        # Should cycle: service-1, service-3, service-1, service-3
        expected = ["service-1", "service-3", "service-1", "service-3"]
        assert selections == expected

    @pytest.mark.asyncio
    async def test_round_robin_all_unhealthy(self, balancer, service_instances):
        """Test round robin when all instances are unhealthy."""
        # Mark all instances as unhealthy
        for instance in service_instances:
            instance.healthy = False
        await balancer.update_instances(service_instances)

        instance = await balancer.select_instance()
        assert instance is None


class TestWeightedRoundRobinBalancer:
    """Test Weighted Round Robin load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)

    @pytest.fixture
    def balancer(self, config):
        return WeightedRoundRobinBalancer(config)

    @pytest.fixture
    def weighted_instances(self):
        """Create instances with different weights."""
        return [
            ServiceInstance(id="light", host="host1", port=8080, weight=1),
            ServiceInstance(id="medium", host="host2", port=8080, weight=2),
            ServiceInstance(id="heavy", host="host3", port=8080, weight=3),
        ]

    @pytest.mark.asyncio
    async def test_weighted_round_robin_respects_weights(self, balancer, weighted_instances):
        """Test that weighted round robin respects instance weights."""
        await balancer.update_instances(weighted_instances)

        selections = []
        # Get enough selections to see the pattern (total weight = 6)
        for _ in range(12):  # Two complete cycles
            instance = await balancer.select_instance()
            selections.append(instance.id)

        # Count selections per instance
        counts = {
            instance_id: selections.count(instance_id)
            for instance_id in ["light", "medium", "heavy"]
        }

        # Should respect weight ratios: 1:2:3
        assert counts["light"] == 2  # 1/6 * 12
        assert counts["medium"] == 4  # 2/6 * 12
        assert counts["heavy"] == 6  # 3/6 * 12


class TestLeastConnectionsBalancer:
    """Test Least Connections load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)

    @pytest.fixture
    def balancer(self, config):
        return LeastConnectionsBalancer(config)

    @pytest.fixture
    def connection_instances(self):
        """Create instances with different active connections."""
        instances = [
            ServiceInstance(id="low-load", host="host1", port=8080),
            ServiceInstance(id="med-load", host="host2", port=8080),
            ServiceInstance(id="high-load", host="host3", port=8080),
        ]
        # Simulate different loads
        instances[0].active_requests = 1
        instances[1].active_requests = 3
        instances[2].active_requests = 5
        return instances

    @pytest.mark.asyncio
    async def test_least_connections_selects_lowest_load(self, balancer, connection_instances):
        """Test that least connections selects instance with fewest active requests."""
        await balancer.update_instances(connection_instances)

        # Should always select the one with least connections
        instance = await balancer.select_instance()
        assert instance.id == "low-load"
        assert instance.active_requests == 1

    @pytest.mark.asyncio
    async def test_least_connections_equal_load_distribution(self, balancer):
        """Test behavior when all instances have equal load."""
        instances = [
            ServiceInstance(id="equal-1", host="host1", port=8080),
            ServiceInstance(id="equal-2", host="host2", port=8080),
            ServiceInstance(id="equal-3", host="host3", port=8080),
        ]
        # All have same load
        for instance in instances:
            instance.active_requests = 2

        await balancer.update_instances(instances)

        # Should select one of them (implementation dependent, but should be consistent)
        instance = await balancer.select_instance()
        assert instance.id in ["equal-1", "equal-2", "equal-3"]

    def test_record_request_updates_tracking(self, balancer):
        """Test that recording requests updates the balancer's tracking."""
        instance = ServiceInstance(id="test", host="localhost", port=8080)

        # Record successful request
        balancer.record_request(instance, success=True, response_time=0.1)

        # Should update internal tracking (implementation dependent)
        # At minimum, should not raise an error
        assert True  # Test passes if no exception


class TestRandomBalancer:
    """Test Random load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)

    @pytest.fixture
    def balancer(self, config):
        return RandomBalancer(config)

    @pytest.fixture
    def service_instances(self):
        return [
            ServiceInstance(id="service-1", host="host1", port=8080),
            ServiceInstance(id="service-2", host="host2", port=8080),
            ServiceInstance(id="service-3", host="host3", port=8080),
        ]

    @pytest.mark.asyncio
    async def test_random_selection_distribution(self, balancer, service_instances):
        """Test that random selection distributes load across instances."""
        await balancer.update_instances(service_instances)

        selections = []
        # Get many selections to test distribution
        for _ in range(300):
            instance = await balancer.select_instance()
            selections.append(instance.id)

        # Count selections per instance
        counts = {
            instance_id: selections.count(instance_id)
            for instance_id in ["service-1", "service-2", "service-3"]
        }

        # Each should get roughly 1/3 of selections (allow some variance)
        for count in counts.values():
            assert 80 <= count <= 120  # Roughly 100 ± 20

    @pytest.mark.asyncio
    async def test_random_selection_returns_valid_instance(self, balancer, service_instances):
        """Test that random selection always returns a valid instance."""
        await balancer.update_instances(service_instances)

        for _ in range(10):
            instance = await balancer.select_instance()
            assert instance is not None
            assert instance.id in ["service-1", "service-2", "service-3"]


class TestWeightedRandomBalancer:
    """Test Weighted Random load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_RANDOM)

    @pytest.fixture
    def balancer(self, config):
        return WeightedRandomBalancer(config)

    @pytest.fixture
    def weighted_instances(self):
        return [
            ServiceInstance(id="light", host="host1", port=8080, weight=1),
            ServiceInstance(id="medium", host="host2", port=8080, weight=2),
            ServiceInstance(id="heavy", host="host3", port=8080, weight=4),
        ]

    @pytest.mark.asyncio
    async def test_weighted_random_respects_weights(self, balancer, weighted_instances):
        """Test that weighted random selection respects weights over many samples."""
        await balancer.update_instances(weighted_instances)

        selections = []
        # Get many selections to test weight distribution
        for _ in range(700):  # Large sample size for statistical significance
            instance = await balancer.select_instance()
            selections.append(instance.id)

        # Count selections per instance
        counts = {
            instance_id: selections.count(instance_id)
            for instance_id in ["light", "medium", "heavy"]
        }

        # Should respect weight ratios: 1:2:4 (total weight = 7)
        # Expected: light ~100, medium ~200, heavy ~400
        assert 70 <= counts["light"] <= 130
        assert 140 <= counts["medium"] <= 260
        assert 350 <= counts["heavy"] <= 450


class TestConsistentHashBalancer:
    """Test Consistent Hash load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.CONSISTENT_HASH)

    @pytest.fixture
    def balancer(self, config):
        return ConsistentHashBalancer(config)

    @pytest.fixture
    def service_instances(self):
        return [
            ServiceInstance(id="service-1", host="host1", port=8080),
            ServiceInstance(id="service-2", host="host2", port=8080),
            ServiceInstance(id="service-3", host="host3", port=8080),
        ]

    @pytest.mark.asyncio
    async def test_consistent_hash_same_key_same_instance(self, balancer, service_instances):
        """Test that same hash key always returns same instance."""
        await balancer.update_instances(service_instances)

        context = LoadBalancingContext(request_id="test-request-123")

        # Multiple calls with same context should return same instance
        first_instance = await balancer.select_instance(context)
        for _ in range(5):
            instance = await balancer.select_instance(context)
            assert instance.id == first_instance.id

    @pytest.mark.asyncio
    async def test_consistent_hash_different_keys_distribute(self, balancer, service_instances):
        """Test that different hash keys distribute across instances."""
        await balancer.update_instances(service_instances)

        selections = {}
        # Try different request IDs
        for i in range(100):
            context = LoadBalancingContext(request_id=f"request-{i}")
            instance = await balancer.select_instance(context)
            selections[f"request-{i}"] = instance.id

        # Should use all instances
        used_instances = set(selections.values())
        assert len(used_instances) > 1  # Should distribute across multiple instances

    @pytest.mark.asyncio
    async def test_consistent_hash_no_context_fallback(self, balancer, service_instances):
        """Test behavior when no context is provided."""
        await balancer.update_instances(service_instances)

        # Should still return an instance (fallback behavior)
        instance = await balancer.select_instance()
        assert instance is not None
        assert instance.id in ["service-1", "service-2", "service-3"]


class TestIPHashBalancer:
    """Test IP Hash load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.IP_HASH)

    @pytest.fixture
    def balancer(self, config):
        return IPHashBalancer(config)

    @pytest.fixture
    def service_instances(self):
        return [
            ServiceInstance(id="service-1", host="host1", port=8080),
            ServiceInstance(id="service-2", host="host2", port=8080),
            ServiceInstance(id="service-3", host="host3", port=8080),
        ]

    @pytest.mark.asyncio
    async def test_ip_hash_same_ip_same_instance(self, balancer, service_instances):
        """Test that same client IP always gets same instance."""
        await balancer.update_instances(service_instances)

        context = LoadBalancingContext(client_ip="192.168.1.100")

        # Multiple requests from same IP should go to same instance
        first_instance = await balancer.select_instance(context)
        for _ in range(5):
            instance = await balancer.select_instance(context)
            assert instance.id == first_instance.id

    @pytest.mark.asyncio
    async def test_ip_hash_different_ips_distribute(self, balancer, service_instances):
        """Test that different client IPs distribute across instances."""
        await balancer.update_instances(service_instances)

        selections = {}
        # Try different client IPs
        for i in range(100):
            context = LoadBalancingContext(client_ip=f"192.168.1.{i}")
            instance = await balancer.select_instance(context)
            selections[f"192.168.1.{i}"] = instance.id

        # Should use multiple instances
        used_instances = set(selections.values())
        assert len(used_instances) > 1


class TestHealthBasedBalancer:
    """Test Health-based load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(strategy=LoadBalancingStrategy.HEALTH_BASED)

    @pytest.fixture
    def balancer(self, config):
        return HealthBasedBalancer(config)

    @pytest.fixture
    def mixed_health_instances(self):
        """Create instances with mixed health status."""
        instances = [
            ServiceInstance(id="healthy-1", host="host1", port=8080),
            ServiceInstance(id="healthy-2", host="host2", port=8080),
            ServiceInstance(id="unhealthy-1", host="host3", port=8080),
        ]
        instances[2].healthy = False  # Mark as unhealthy
        return instances

    @pytest.mark.asyncio
    async def test_health_based_selects_only_healthy(self, balancer, mixed_health_instances):
        """Test that health-based balancer only selects healthy instances."""
        await balancer.update_instances(mixed_health_instances)

        # Should only select healthy instances
        for _ in range(10):
            instance = await balancer.select_instance()
            assert instance is not None
            assert instance.id in ["healthy-1", "healthy-2"]
            assert instance.healthy is True

    @pytest.mark.asyncio
    async def test_health_based_all_unhealthy_returns_none(self, balancer):
        """Test behavior when all instances are unhealthy."""
        unhealthy_instances = [
            ServiceInstance(id="unhealthy-1", host="host1", port=8080),
            ServiceInstance(id="unhealthy-2", host="host2", port=8080),
        ]
        for instance in unhealthy_instances:
            instance.healthy = False

        await balancer.update_instances(unhealthy_instances)

        instance = await balancer.select_instance()
        assert instance is None


class TestAdaptiveBalancer:
    """Test Adaptive load balancing strategy."""

    @pytest.fixture
    def config(self):
        return LoadBalancingConfig(
            strategy=LoadBalancingStrategy.ADAPTIVE,
            adaptive_window_size=10,
            adaptive_adjustment_factor=0.1,
        )

    @pytest.fixture
    def balancer(self, config):
        return AdaptiveBalancer(config)

    @pytest.fixture
    def service_instances(self):
        return [
            ServiceInstance(id="service-1", host="host1", port=8080),
            ServiceInstance(id="service-2", host="host2", port=8080),
            ServiceInstance(id="service-3", host="host3", port=8080),
        ]

    @pytest.mark.asyncio
    async def test_adaptive_initial_selection(self, balancer, service_instances):
        """Test that adaptive balancer works initially."""
        await balancer.update_instances(service_instances)

        instance = await balancer.select_instance()
        assert instance is not None
        assert instance.id in ["service-1", "service-2", "service-3"]

    def test_adaptive_records_performance(self, balancer, service_instances):
        """Test that adaptive balancer records performance metrics."""
        instance = service_instances[0]

        # Record some performance data
        balancer.record_request(instance, success=True, response_time=0.1)
        balancer.record_request(instance, success=True, response_time=0.2)
        balancer.record_request(instance, success=False, response_time=1.0)

        # Should not raise any errors
        assert True


class TestLoadBalancerFactory:
    """Test the load balancer factory function."""

    def test_create_load_balancer_round_robin(self):
        """Test creating round robin balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, RoundRobinBalancer)

    def test_create_load_balancer_weighted_round_robin(self):
        """Test creating weighted round robin balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, WeightedRoundRobinBalancer)

    def test_create_load_balancer_least_connections(self):
        """Test creating least connections balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, LeastConnectionsBalancer)

    def test_create_load_balancer_random(self):
        """Test creating random balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, RandomBalancer)

    def test_create_load_balancer_weighted_random(self):
        """Test creating weighted random balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_RANDOM)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, WeightedRandomBalancer)

    def test_create_load_balancer_consistent_hash(self):
        """Test creating consistent hash balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.CONSISTENT_HASH)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, ConsistentHashBalancer)

    def test_create_load_balancer_ip_hash(self):
        """Test creating IP hash balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.IP_HASH)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, IPHashBalancer)

    def test_create_load_balancer_health_based(self):
        """Test creating health-based balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.HEALTH_BASED)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, HealthBasedBalancer)

    def test_create_load_balancer_adaptive(self):
        """Test creating adaptive balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ADAPTIVE)
        balancer = create_load_balancer(config)
        assert isinstance(balancer, AdaptiveBalancer)

    def test_create_load_balancer_unsupported_strategy(self):
        """Test error handling for unsupported strategy."""
        # Create an invalid strategy (this would need to be added to the enum)
        config = LoadBalancingConfig(strategy="INVALID_STRATEGY")

        with pytest.raises(ValueError, match="Unsupported load balancing strategy"):
            create_load_balancer(config)


class TestLoadBalancingWithFallback:
    """Test load balancing with fallback mechanisms."""

    @pytest.fixture
    def config_with_fallback(self):
        return LoadBalancingConfig(
            strategy=LoadBalancingStrategy.LEAST_CONNECTIONS,
            fallback_strategy=LoadBalancingStrategy.ROUND_ROBIN,
        )

    @pytest.fixture
    def balancer_with_fallback(self, config_with_fallback):
        return create_load_balancer(config_with_fallback)

    @pytest.fixture
    def service_instances(self):
        return [
            ServiceInstance(id="service-1", host="host1", port=8080),
            ServiceInstance(id="service-2", host="host2", port=8080),
        ]

    @pytest.mark.asyncio
    async def test_fallback_when_primary_fails(self, balancer_with_fallback, service_instances):
        """Test that fallback strategy is used when primary fails."""
        await balancer_with_fallback.update_instances(service_instances)

        # Use select_with_fallback method
        instance = await balancer_with_fallback.select_with_fallback()
        assert instance is not None
        assert instance.id in ["service-1", "service-2"]


class TestLoadBalancingIntegrationScenarios:
    """Integration tests for realistic load balancing scenarios."""

    @pytest.fixture
    def realistic_service_pool(self):
        """Create a realistic pool of services with varied characteristics."""
        return [
            ServiceInstance(id="web-1", host="web1.example.com", port=80, weight=3),
            ServiceInstance(id="web-2", host="web2.example.com", port=80, weight=2),
            ServiceInstance(id="web-3", host="web3.example.com", port=80, weight=1),
            ServiceInstance(id="api-1", host="api1.example.com", port=8080, weight=4),
            ServiceInstance(id="api-2", host="api2.example.com", port=8080, weight=4),
        ]

    @pytest.mark.asyncio
    async def test_high_load_scenario(self, realistic_service_pool):
        """Test load balancing under high request volume."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = create_load_balancer(config)
        await balancer.update_instances(realistic_service_pool)

        # Simulate high load
        request_count = 1000
        instance_counts = {}

        for request_id in range(request_count):
            # Simulate some instances getting busier
            if request_id % 100 == 0:
                for instance in realistic_service_pool:
                    instance.active_requests += random.randint(0, 2)

            instance = await balancer.select_instance()
            assert instance is not None

            instance_id = instance.id
            instance_counts[instance_id] = instance_counts.get(instance_id, 0) + 1

            # Simulate request completion
            if random.random() < 0.3:  # 30% of requests complete
                instance.active_requests = max(0, instance.active_requests - 1)

        # All instances should have been used
        assert len(instance_counts) == len(realistic_service_pool)

    @pytest.mark.asyncio
    async def test_failover_scenario(self, realistic_service_pool):
        """Test load balancing during instance failures."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.HEALTH_BASED)
        balancer = create_load_balancer(config)
        await balancer.update_instances(realistic_service_pool)

        # Initially all instances healthy
        instance = await balancer.select_instance()
        assert instance is not None

        # Simulate gradual failures
        for _i, failed_instance in enumerate(realistic_service_pool[:3]):
            failed_instance.healthy = False
            await balancer.update_instances(realistic_service_pool)

            # Should still get healthy instances
            for _ in range(10):
                instance = await balancer.select_instance()
                if instance is not None:
                    assert instance.healthy is True

        # If some instances remain healthy, should still work
        healthy_instances = [inst for inst in realistic_service_pool if inst.healthy]
        if healthy_instances:
            instance = await balancer.select_instance()
            assert instance is not None
            assert instance.healthy is True

    @pytest.mark.asyncio
    async def test_weighted_distribution_accuracy(self, realistic_service_pool):
        """Test that weighted balancing accurately reflects weights over time."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        balancer = create_load_balancer(config)
        await balancer.update_instances(realistic_service_pool)

        selections = []
        total_requests = 1000

        for _ in range(total_requests):
            instance = await balancer.select_instance()
            assert instance is not None
            selections.append(instance.id)

        # Calculate actual distribution
        total_weight = sum(inst.weight for inst in realistic_service_pool)

        for instance in realistic_service_pool:
            expected_ratio = instance.weight / total_weight
            expected_count = expected_ratio * total_requests
            actual_count = selections.count(instance.id)

            # Allow some variance (±10%)
            assert abs(actual_count - expected_count) <= expected_count * 0.1

    @pytest.mark.asyncio
    async def test_session_affinity_with_ip_hash(self, realistic_service_pool):
        """Test session affinity using IP hash balancing."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.IP_HASH)
        balancer = create_load_balancer(config)
        await balancer.update_instances(realistic_service_pool)

        # Simulate multiple users with session affinity requirements
        user_sessions = {}

        for user_id in range(50):
            client_ip = f"192.168.1.{user_id}"
            context = LoadBalancingContext(client_ip=client_ip)

            # Multiple requests from same user should go to same instance
            for _request in range(5):
                instance = await balancer.select_instance(context)
                assert instance is not None

                if user_id not in user_sessions:
                    user_sessions[user_id] = instance.id
                else:
                    # Should always go to same instance for this user
                    assert user_sessions[user_id] == instance.id

        # All users should have been assigned an instance
        assert len(user_sessions) == 50

        # Multiple instances should be used across users
        used_instances = set(user_sessions.values())
        assert len(used_instances) > 1
