"""
Unit tests for Load Balancing strategies.
"""

import pytest

from mmf_new.discovery.domain.load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    TrafficPolicy,
)
from mmf_new.discovery.domain.models import (
    HealthStatus,
    ServiceInstance,
    ServiceMetadata,
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


class TestLoadBalancer:
    def test_round_robin(self, service_instances):
        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        # First selection
        inst1 = balancer.select_instance("test-service", service_instances)
        assert inst1.instance_id == "instance-1"

        # Second selection
        inst2 = balancer.select_instance("test-service", service_instances)
        assert inst2.instance_id == "instance-2"

        # Third selection
        inst3 = balancer.select_instance("test-service", service_instances)
        assert inst3.instance_id == "instance-3"

        # Fourth selection (wrap around)
        inst4 = balancer.select_instance("test-service", service_instances)
        assert inst4.instance_id == "instance-1"

    def test_least_connections(self, service_instances):
        # Setup connections
        service_instances[0].active_connections = 10
        service_instances[1].active_connections = 2  # Lowest
        service_instances[2].active_connections = 5

        config = LoadBalancingConfig(policy=TrafficPolicy.LEAST_CONN)
        balancer = LoadBalancer(config)

        inst = balancer.select_instance("test-service", service_instances)
        assert inst.instance_id == "instance-2"

    def test_consistent_hash(self, service_instances):
        config = LoadBalancingConfig(
            policy=TrafficPolicy.CONSISTENT_HASH, hash_policy={"hash_on": ["user_id"]}
        )
        balancer = LoadBalancer(config)

        # Same user_id should map to same instance
        ctx1 = {"user_id": "user-123"}
        inst1_a = balancer.select_instance("test-service", service_instances, ctx1)
        inst1_b = balancer.select_instance("test-service", service_instances, ctx1)

        assert inst1_a.instance_id == inst1_b.instance_id

        # Different user_id might map to different instance (not guaranteed but likely)
        # We just verify consistency here.

    def test_locality_aware(self):
        # Create instances in different zones
        inst1 = ServiceInstance(
            service_name="test-service",
            instance_id="inst-1",
            host="localhost",
            port=8080,
            metadata=ServiceMetadata(region="us-east", availability_zone="zone-a"),
        )
        inst2 = ServiceInstance(
            service_name="test-service",
            instance_id="inst-2",
            host="localhost",
            port=8081,
            metadata=ServiceMetadata(region="us-east", availability_zone="zone-b"),
        )

        instances = [inst1, inst2]
        config = LoadBalancingConfig(policy=TrafficPolicy.LOCALITY_AWARE)
        balancer = LoadBalancer(config)

        # Client in zone-a should prefer inst1
        ctx = {"region": "us-east", "zone": "zone-a"}
        selected = balancer.select_instance("test-service", instances, ctx)
        assert selected.instance_id == "inst-1"

        # Client in zone-b should prefer inst2
        ctx_b = {"region": "us-east", "zone": "zone-b"}
        selected_b = balancer.select_instance("test-service", instances, ctx_b)
        assert selected_b.instance_id == "inst-2"

    def test_empty_instances(self):
        config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        balancer = LoadBalancer(config)

        inst = balancer.select_instance("test-service", [])
        assert inst is None
