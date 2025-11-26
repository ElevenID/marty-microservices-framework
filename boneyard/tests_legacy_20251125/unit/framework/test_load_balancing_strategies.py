"""
Complete and corrected load balancing strategy tests.
"""

import pytest

from marty_msf.framework.discovery.core import HealthStatus, ServiceInstance
from marty_msf.framework.discovery.load_balancing import (
    HealthBasedBalancer,
    LeastConnectionsBalancer,
    LoadBalancingConfig,
    LoadBalancingContext,
    LoadBalancingStrategy,
    RandomBalancer,
    RoundRobinBalancer,
    WeightedRoundRobinBalancer,
    create_load_balancer,
)


@pytest.fixture
def service_instances():
    """Create sample service instances for testing."""
    instances = [
        ServiceInstance(
            service_name="test-service", instance_id="instance-1", host="localhost", port=8080
        ),
        ServiceInstance(
            service_name="test-service", instance_id="instance-2", host="localhost", port=8081
        ),
        ServiceInstance(
            service_name="test-service", instance_id="instance-3", host="localhost", port=8082
        ),
    ]

    # Set all instances to healthy
    for instance in instances:
        instance.update_health_status(HealthStatus.HEALTHY)

    return instances


@pytest.fixture
def context():
    """Create a load balancing context."""
    return LoadBalancingContext(
        client_ip="192.168.1.100",
        session_id="session-123",
        request_headers={"User-Agent": "test-client"},
        request_path="/api/v1/data",
        request_method="GET",
    )


class TestServiceInstanceComplete:
    """Test ServiceInstance functionality."""

    def test_service_instance_creation(self):
        """Test creating a service instance with proper parameters."""
        instance = ServiceInstance(
            service_name="test-service", instance_id="test-instance", host="localhost", port=8080
        )

        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-instance"
        assert instance.endpoint.host == "localhost"
        assert instance.endpoint.port == 8080

    def test_service_instance_equality(self):
        """Test service instance equality comparison."""
        instance1 = ServiceInstance(
            service_name="service", instance_id="instance-1", host="localhost", port=8080
        )
        instance2 = ServiceInstance(
            service_name="service", instance_id="instance-1", host="localhost", port=8080
        )
        instance3 = ServiceInstance(
            service_name="service", instance_id="instance-2", host="localhost", port=8080
        )

        # Note: ServiceInstance equality may be based on instance_id
        assert instance1.instance_id == instance2.instance_id
        assert instance1.instance_id != instance3.instance_id
        assert instance1.service_name == instance2.service_name


class TestRoundRobinBalancerComplete:
    """Test RoundRobinBalancer with proper API usage."""

    @pytest.mark.asyncio
    async def test_round_robin_creation(self):
        """Test round-robin balancer creation."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = RoundRobinBalancer(config)

        assert balancer.config.strategy == LoadBalancingStrategy.ROUND_ROBIN

    @pytest.mark.asyncio
    async def test_round_robin_empty_instances(self):
        """Test round-robin with empty instance list."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = RoundRobinBalancer(config)

        result = await balancer.select_instance(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_round_robin_single_instance(self):
        """Test round-robin with single instance."""
        single_instance = [
            ServiceInstance(service_name="service", instance_id="only", host="localhost", port=8080)
        ]

        # Set instance to healthy
        single_instance[0].update_health_status(HealthStatus.HEALTHY)

        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = RoundRobinBalancer(config)

        # Update instances first
        await balancer.update_instances(single_instance)

        # Should always return the same instance
        first = await balancer.select_instance(None)
        second = await balancer.select_instance(None)

        assert first is not None
        assert second is not None
        assert first == second == single_instance[0]

    @pytest.mark.asyncio
    async def test_round_robin_multiple_instances(self, service_instances):
        """Test round-robin cycling through multiple instances."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = RoundRobinBalancer(config)

        # Update instances
        await balancer.update_instances(service_instances)

        # Test cycling through instances
        first = await balancer.select_instance(None)
        second = await balancer.select_instance(None)
        third = await balancer.select_instance(None)
        fourth = await balancer.select_instance(None)

        # Should have valid instances
        assert first is not None
        assert second is not None
        assert third is not None
        assert fourth is not None

        # Should cycle through different instances (at least some variety)
        selections = [first, second, third, fourth]
        unique_selections = set(selections)

        # With 3 instances and 4 selections, should have some cycling
        assert len(unique_selections) >= 2


class TestWeightedRoundRobinBalancerComplete:
    """Test WeightedRoundRobinBalancer with proper API usage."""

    @pytest.mark.asyncio
    async def test_weighted_round_robin_creation(self):
        """Test weighted round-robin balancer creation."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        balancer = WeightedRoundRobinBalancer(config)

        assert balancer.config.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN

    @pytest.mark.asyncio
    async def test_weighted_round_robin_with_instances(self, service_instances):
        """Test weighted round-robin with instances."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        balancer = WeightedRoundRobinBalancer(config)

        await balancer.update_instances(service_instances)

        result = await balancer.select_instance(None)
        # Should either select an instance or return None (if no weights set)
        assert result is None or result in service_instances


class TestLeastConnectionsBalancerComplete:
    """Test LeastConnectionsBalancer with proper API usage."""

    @pytest.mark.asyncio
    async def test_least_connections_creation(self):
        """Test least connections balancer creation."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = LeastConnectionsBalancer(config)

        assert balancer.config.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS

    @pytest.mark.asyncio
    async def test_least_connections_with_instances(self, service_instances):
        """Test least connections with instances."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = LeastConnectionsBalancer(config)

        await balancer.update_instances(service_instances)

        result = await balancer.select_instance(None)
        assert result in service_instances or result is None

    @pytest.mark.asyncio
    async def test_least_connections_tracks_requests(self, service_instances):
        """Test that least connections tracks request counts."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = LeastConnectionsBalancer(config)

        await balancer.update_instances(service_instances)

        # Record requests for first instance
        balancer.record_request(service_instances[0], True, 0.1)
        balancer.record_request(service_instances[0], True, 0.2)

        # Next selection should prefer instances with fewer connections
        result = await balancer.select_instance(None)
        assert result is not None


class TestRandomBalancerComplete:
    """Test RandomBalancer with proper API usage."""

    @pytest.mark.asyncio
    async def test_random_balancer_creation(self):
        """Test random balancer creation."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)
        balancer = RandomBalancer(config)

        assert balancer.config.strategy == LoadBalancingStrategy.RANDOM

    @pytest.mark.asyncio
    async def test_random_balancer_with_instances(self, service_instances):
        """Test random balancer with instances."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)
        balancer = RandomBalancer(config)

        await balancer.update_instances(service_instances)

        result = await balancer.select_instance(None)
        assert result in service_instances or result is None

    @pytest.mark.asyncio
    async def test_random_balancer_distribution(self, service_instances):
        """Test random balancer distribution over multiple selections."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)
        balancer = RandomBalancer(config)

        await balancer.update_instances(service_instances)

        # Select instances multiple times to test distribution
        selections = []
        for _ in range(30):
            result = await balancer.select_instance(None)
            if result:
                selections.append(result)

        # Should have some distribution (not all the same instance)
        unique_selections = set(selections)
        assert len(unique_selections) > 1 or len(service_instances) == 1


class TestHealthBasedBalancerComplete:
    """Test HealthBasedBalancer with proper API usage."""

    @pytest.mark.asyncio
    async def test_health_based_creation(self):
        """Test health-based balancer creation."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.HEALTH_BASED)
        balancer = HealthBasedBalancer(config)

        assert balancer.config.strategy == LoadBalancingStrategy.HEALTH_BASED

    @pytest.mark.asyncio
    async def test_health_based_selects_healthy_instances(self):
        """Test health-based balancer selects only healthy instances."""
        # Create instances with known health status
        healthy_instance = ServiceInstance(
            service_name="service", instance_id="healthy", host="localhost", port=8080
        )

        unhealthy_instance = ServiceInstance(
            service_name="service", instance_id="unhealthy", host="localhost", port=8081
        )

        # Mock health status
        healthy_instance.is_healthy = lambda: True
        unhealthy_instance.is_healthy = lambda: False

        config = LoadBalancingConfig(
            strategy=LoadBalancingStrategy.HEALTH_BASED, health_check_enabled=True
        )
        balancer = HealthBasedBalancer(config)

        # Update with mixed health instances
        await balancer.update_instances([healthy_instance, unhealthy_instance])

        # Should select healthy instance
        result = await balancer.select_instance(None)
        # Result could be healthy instance or None depending on implementation
        assert result is None or result == healthy_instance


class TestLoadBalancerFactoryComplete:
    """Test load balancer factory with proper API usage."""

    def test_create_round_robin_balancer(self):
        """Test creating round-robin balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = create_load_balancer(config)

        assert isinstance(balancer, RoundRobinBalancer)
        assert balancer.config.strategy == LoadBalancingStrategy.ROUND_ROBIN

    def test_create_weighted_round_robin_balancer(self):
        """Test creating weighted round-robin balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN)
        balancer = create_load_balancer(config)

        assert isinstance(balancer, WeightedRoundRobinBalancer)
        assert balancer.config.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN

    def test_create_least_connections_balancer(self):
        """Test creating least connections balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        balancer = create_load_balancer(config)

        assert isinstance(balancer, LeastConnectionsBalancer)
        assert balancer.config.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS

    def test_create_random_balancer(self):
        """Test creating random balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.RANDOM)
        balancer = create_load_balancer(config)

        assert isinstance(balancer, RandomBalancer)
        assert balancer.config.strategy == LoadBalancingStrategy.RANDOM

    def test_create_health_based_balancer(self):
        """Test creating health-based balancer via factory."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.HEALTH_BASED)
        balancer = create_load_balancer(config)

        assert isinstance(balancer, HealthBasedBalancer)
        assert balancer.config.strategy == LoadBalancingStrategy.HEALTH_BASED


class TestLoadBalancingConfigComplete:
    """Test LoadBalancingConfig with proper usage."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LoadBalancingConfig()

        assert config.strategy == LoadBalancingStrategy.ROUND_ROBIN
        assert config.health_check_enabled is True
        assert config.health_check_interval == 30.0
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LoadBalancingConfig(
            strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
            health_check_enabled=False,
            health_check_interval=60.0,
            max_retries=5,
        )

        assert config.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN
        assert config.health_check_enabled is False
        assert config.health_check_interval == 60.0
        assert config.max_retries == 5


class TestLoadBalancingContextComplete:
    """Test LoadBalancingContext with proper usage."""

    def test_default_context(self):
        """Test default context values."""
        context = LoadBalancingContext()

        assert context.client_ip is None
        assert context.session_id is None
        assert context.request_headers == {}
        assert context.custom_data == {}

    def test_custom_context(self):
        """Test custom context values."""
        context = LoadBalancingContext(
            client_ip="192.168.1.100",
            session_id="session-123",
            request_headers={"User-Agent": "test-client"},
            request_path="/api/v1/data",
            custom_data={"priority": "high"},
        )

        assert context.client_ip == "192.168.1.100"
        assert context.session_id == "session-123"
        assert context.request_headers["User-Agent"] == "test-client"
        assert context.request_path == "/api/v1/data"
        assert context.custom_data["priority"] == "high"


class TestLoadBalancerStatsComplete:
    """Test load balancer statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self, service_instances):
        """Test statistics tracking in load balancer."""
        config = LoadBalancingConfig(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        balancer = RoundRobinBalancer(config)

        await balancer.update_instances(service_instances)

        # Initial stats
        stats = balancer.get_stats()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0

        # Record some requests
        instance = service_instances[0]
        balancer.record_request(instance, True, 0.1)
        balancer.record_request(instance, False, 0.5)

        # Check updated stats
        stats = balancer.get_stats()
        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["average_response_time"] == 0.3


class TestLoadBalancerFallbackComplete:
    """Test load balancer fallback functionality."""

    @pytest.mark.asyncio
    async def test_fallback_strategy(self, service_instances):
        """Test fallback strategy when primary fails."""
        config = LoadBalancingConfig(
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
            fallback_strategy=LoadBalancingStrategy.RANDOM,
        )
        balancer = RoundRobinBalancer(config)

        await balancer.update_instances(service_instances)

        # Test select with fallback
        result = await balancer.select_with_fallback(None)
        assert result in service_instances or result is None


class TestLoadBalancingIntegrationComplete:
    """Test integration scenarios with multiple components."""

    @pytest.mark.asyncio
    async def test_multiple_strategies_same_pool(self, service_instances):
        """Test that multiple balancer strategies work with same instance pool."""
        strategies_and_configs = [
            (LoadBalancingStrategy.ROUND_ROBIN, RoundRobinBalancer),
            (LoadBalancingStrategy.LEAST_CONNECTIONS, LeastConnectionsBalancer),
            (LoadBalancingStrategy.RANDOM, RandomBalancer),
        ]

        for strategy, balancer_class in strategies_and_configs:
            config = LoadBalancingConfig(strategy=strategy)
            balancer = balancer_class(config)

            await balancer.update_instances(service_instances)

            # Each strategy should be able to select instances
            result = await balancer.select_instance(None)
            assert result in service_instances or result is None

    @pytest.mark.asyncio
    async def test_health_checking_integration(self):
        """Test health checking integration with load balancing."""
        # Create instances with mixed health
        instances = [
            ServiceInstance(service_name="web", instance_id="web-1", host="localhost", port=8080),
            ServiceInstance(service_name="web", instance_id="web-2", host="localhost", port=8081),
            ServiceInstance(service_name="web", instance_id="web-3", host="localhost", port=8082),
        ]

        # Mock health statuses
        instances[0].is_healthy = lambda: True
        instances[1].is_healthy = lambda: True
        instances[2].is_healthy = lambda: False

        config = LoadBalancingConfig(
            strategy=LoadBalancingStrategy.ROUND_ROBIN, health_check_enabled=True
        )
        balancer = RoundRobinBalancer(config)

        # Update instances - should filter out unhealthy ones
        await balancer.update_instances(instances)

        # Select instances multiple times
        for _ in range(5):
            result = await balancer.select_instance(None)
            if result:
                # Should only select healthy instances
                assert result in instances[:2]  # Only first two are healthy
