"""
Unit tests for discovery load balancing module.

Tests LoadBalancer class with various traffic policies.
"""

import pytest

from mmf.discovery.domain.load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    TrafficPolicy,
)
from mmf.discovery.domain.models import (
    HealthStatus,
    ServiceEndpoint,
    ServiceInstance,
    ServiceMetadata,
)


def create_service_instance(
    service_name: str = "test-service",
    instance_id: str = "instance-1",
    host: str = "localhost",
    port: int = 8080,
    weight: int = 1,
    region: str = "us-east-1",
    availability_zone: str = "us-east-1a",
    active_connections: int = 0,
) -> ServiceInstance:
    """Helper to create a service instance with proper metadata."""
    endpoint = ServiceEndpoint(host=host, port=port)
    metadata = ServiceMetadata(
        version="1.0.0",
        environment="test",
        region=region,
        availability_zone=availability_zone,
        weight=weight,
    )
    instance = ServiceInstance(
        service_name=service_name,
        instance_id=instance_id,
        endpoint=endpoint,
        metadata=metadata,
    )
    instance.active_connections = active_connections
    return instance


class TestTrafficPolicy:
    """Tests for TrafficPolicy enum."""

    def test_policy_values(self):
        """Test traffic policy string values."""
        assert TrafficPolicy.ROUND_ROBIN.value == "round_robin"
        assert TrafficPolicy.LEAST_CONN.value == "least_conn"
        assert TrafficPolicy.RANDOM.value == "random"
        assert TrafficPolicy.CONSISTENT_HASH.value == "consistent_hash"
        assert TrafficPolicy.WEIGHTED_ROUND_ROBIN.value == "weighted_round_robin"
        assert TrafficPolicy.LOCALITY_AWARE.value == "locality_aware"

    def test_all_policies_exist(self):
        """Test all expected policies are defined."""
        policies = list(TrafficPolicy)
        assert len(policies) == 6


class TestLoadBalancingConfig:
    """Tests for LoadBalancingConfig class."""

    def test_config_defaults(self):
        """Test config defaults."""
        config = LoadBalancingConfig()

        assert config.policy == TrafficPolicy.ROUND_ROBIN
        assert config.hash_policy is None
        assert config.locality_lb_setting is None

    def test_config_with_policy(self):
        """Test config with specific policy."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LEAST_CONN)
        assert config.policy == TrafficPolicy.LEAST_CONN

    def test_config_with_hash_policy(self):
        """Test config with hash policy."""
        config = LoadBalancingConfig(
            policy=TrafficPolicy.CONSISTENT_HASH,
            hash_policy={"hash_on": ["user_id", "session_id"]},
        )
        assert config.hash_policy == {"hash_on": ["user_id", "session_id"]}


class TestLoadBalancer:
    """Tests for LoadBalancer class."""

    def test_select_instance_empty_list(self):
        """Test selecting from empty list returns None."""
        config = LoadBalancingConfig()
        balancer = LoadBalancer(config)

        result = balancer.select_instance("test-service", [])
        assert result is None

    def test_select_instance_single_instance(self):
        """Test selecting from single instance returns that instance."""
        config = LoadBalancingConfig()
        balancer = LoadBalancer(config)
        instance = create_service_instance()

        result = balancer.select_instance("test-service", [instance])
        assert result == instance

    def test_round_robin_selection(self):
        """Test round robin cycles through instances."""
        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
            create_service_instance(instance_id="i3", host="host3"),
        ]

        # Select 6 times to verify cycling
        selections = []
        for _ in range(6):
            result = balancer.select_instance("test-service", instances)
            selections.append(result.endpoint.host)

        # Should cycle: host1, host2, host3, host1, host2, host3
        assert selections == ["host1", "host2", "host3", "host1", "host2", "host3"]

    def test_round_robin_independent_services(self):
        """Test round robin maintains separate counters per service."""
        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances_a = [
            create_service_instance(service_name="service-a", instance_id="a1", host="hostA1"),
            create_service_instance(service_name="service-a", instance_id="a2", host="hostA2"),
        ]
        instances_b = [
            create_service_instance(service_name="service-b", instance_id="b1", host="hostB1"),
            create_service_instance(service_name="service-b", instance_id="b2", host="hostB2"),
        ]

        # Select from service-a
        result_a1 = balancer.select_instance("service-a", instances_a)
        assert result_a1.endpoint.host == "hostA1"

        # Select from service-b (should start at beginning, not affected by service-a)
        result_b1 = balancer.select_instance("service-b", instances_b)
        assert result_b1.endpoint.host == "hostB1"

        # Select again from service-a (should continue where it left off)
        result_a2 = balancer.select_instance("service-a", instances_a)
        assert result_a2.endpoint.host == "hostA2"

    def test_random_selection(self):
        """Test random selection returns valid instance."""
        config = LoadBalancingConfig(policy=TrafficPolicy.RANDOM)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
            create_service_instance(instance_id="i3", host="host3"),
        ]

        # Select multiple times and verify all are valid
        for _ in range(10):
            result = balancer.select_instance("test-service", instances)
            assert result in instances

    def test_least_connections_selection(self):
        """Test least connections selects instance with fewest connections."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LEAST_CONN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1", active_connections=10),
            create_service_instance(instance_id="i2", host="host2", active_connections=5),
            create_service_instance(instance_id="i3", host="host3", active_connections=15),
        ]

        result = balancer.select_instance("test-service", instances)
        assert result.endpoint.host == "host2"  # Lowest connections

    def test_least_connections_ties(self):
        """Test least connections handles ties."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LEAST_CONN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1", active_connections=5),
            create_service_instance(instance_id="i2", host="host2", active_connections=5),
        ]

        result = balancer.select_instance("test-service", instances)
        # Should return first one with lowest (ties go to first found)
        assert result.endpoint.host == "host1"

    def test_weighted_round_robin_selection(self):
        """Test weighted round robin respects weights."""
        config = LoadBalancingConfig(policy=TrafficPolicy.WEIGHTED_ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1", weight=1),
            create_service_instance(instance_id="i2", host="host2", weight=9),
        ]

        # Select many times and count distribution
        host_counts = {"host1": 0, "host2": 0}
        for _ in range(100):
            result = balancer.select_instance("test-service", instances)
            host_counts[result.endpoint.host] += 1

        # host2 should be selected much more often due to higher weight
        # With weights 1:9, expect roughly 10:90 distribution
        assert host_counts["host2"] > host_counts["host1"]

    def test_weighted_round_robin_zero_weights(self):
        """Test weighted round robin handles zero weights."""
        config = LoadBalancingConfig(policy=TrafficPolicy.WEIGHTED_ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1", weight=0),
            create_service_instance(instance_id="i2", host="host2", weight=0),
        ]

        # Should still return a valid instance (falls back to random)
        result = balancer.select_instance("test-service", instances)
        assert result in instances

    def test_consistent_hash_same_context(self):
        """Test consistent hash returns same instance for same context."""
        config = LoadBalancingConfig(
            policy=TrafficPolicy.CONSISTENT_HASH,
            hash_policy={"hash_on": ["user_id"]},
        )
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
            create_service_instance(instance_id="i3", host="host3"),
        ]

        context = {"user_id": "user-123"}

        # Same context should always return same instance
        result1 = balancer.select_instance("test-service", instances, context)
        result2 = balancer.select_instance("test-service", instances, context)
        result3 = balancer.select_instance("test-service", instances, context)

        assert result1 == result2 == result3

    def test_consistent_hash_different_context(self):
        """Test consistent hash can return different instances for different contexts."""
        config = LoadBalancingConfig(
            policy=TrafficPolicy.CONSISTENT_HASH,
            hash_policy={"hash_on": ["user_id"]},
        )
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
            create_service_instance(instance_id="i3", host="host3"),
        ]

        # Different users may get different instances
        results = set()
        for i in range(10):
            context = {"user_id": f"user-{i}"}
            result = balancer.select_instance("test-service", instances, context)
            results.add(result.endpoint.host)

        # With 10 different users and 3 instances, should hit at least 2
        assert len(results) >= 2

    def test_consistent_hash_no_context(self):
        """Test consistent hash falls back to random without context."""
        config = LoadBalancingConfig(
            policy=TrafficPolicy.CONSISTENT_HASH,
            hash_policy={"hash_on": ["user_id"]},
        )
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
        ]

        result = balancer.select_instance("test-service", instances, None)
        assert result in instances

    def test_locality_aware_same_zone(self):
        """Test locality aware prefers same zone."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(
                instance_id="i1", host="host1", region="us-east-1", availability_zone="us-east-1a"
            ),
            create_service_instance(
                instance_id="i2", host="host2", region="us-east-1", availability_zone="us-east-1b"
            ),
            create_service_instance(
                instance_id="i3", host="host3", region="us-west-2", availability_zone="us-west-2a"
            ),
        ]

        context = {"region": "us-east-1", "zone": "us-east-1a"}

        result = balancer.select_instance("test-service", instances, context)
        assert result.endpoint.host == "host1"  # Same zone

    def test_locality_aware_same_region_fallback(self):
        """Test locality aware falls back to same region."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(
                instance_id="i1", host="host1", region="us-east-1", availability_zone="us-east-1b"
            ),
            create_service_instance(
                instance_id="i2", host="host2", region="us-west-2", availability_zone="us-west-2a"
            ),
        ]

        # Request from us-east-1a (no exact match, but same region as i1)
        context = {"region": "us-east-1", "zone": "us-east-1a"}

        result = balancer.select_instance("test-service", instances, context)
        assert result.endpoint.host == "host1"  # Same region

    def test_locality_aware_any_fallback(self):
        """Test locality aware falls back to any instance."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(
                instance_id="i1", host="host1", region="us-west-2", availability_zone="us-west-2a"
            ),
        ]

        # Request from different region
        context = {"region": "eu-west-1", "zone": "eu-west-1a"}

        result = balancer.select_instance("test-service", instances, context)
        assert result.endpoint.host == "host1"  # Only option

    def test_locality_aware_no_context(self):
        """Test locality aware without context uses round robin."""
        config = LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
        ]

        result = balancer.select_instance("test-service", instances, None)
        assert result in instances

    def test_unknown_policy_defaults_to_round_robin(self):
        """Test that unknown policies default to round robin behavior."""
        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id="i1", host="host1"),
            create_service_instance(instance_id="i2", host="host2"),
        ]

        # Should behave like round robin
        result1 = balancer.select_instance("test-service", instances)
        result2 = balancer.select_instance("test-service", instances)

        assert result1.endpoint.host == "host1"
        assert result2.endpoint.host == "host2"


class TestLoadBalancerThreadSafety:
    """Tests for LoadBalancer thread safety."""

    def test_round_robin_thread_safe(self):
        """Test that round robin is thread-safe."""
        import threading

        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        instances = [
            create_service_instance(instance_id=f"i{i}", host=f"host{i}") for i in range(3)
        ]

        results = []
        errors = []

        def select_many():
            try:
                for _ in range(100):
                    result = balancer.select_instance("test-service", instances)
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=select_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 500  # 5 threads * 100 selections
