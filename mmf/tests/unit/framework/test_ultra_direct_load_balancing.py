"""Ultra-direct load balancing strategy tests - using importlib to bypass all package init."""

import importlib.util
import os
import sys
from types import ModuleType

import pytest


def load_module_direct(module_path: str, module_name: str) -> ModuleType:
    """Load a module directly from file path without triggering package init."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_ultra_direct_load_balancing():
    """Test loading load balancing module without any package imports."""
    try:
        # Get the absolute path to the load_balancing.py file
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..")

        ports_lb_path = os.path.join(src_dir, "discovery", "ports", "load_balancer.py")
        adapters_rr_path = os.path.join(src_dir, "discovery", "adapters", "round_robin.py")
        core_path = os.path.join(src_dir, "discovery", "domain", "models.py")

        # Verify files exist
        assert os.path.exists(ports_lb_path), f"Ports LB file not found: {ports_lb_path}"
        assert os.path.exists(adapters_rr_path), f"Adapters RR file not found: {adapters_rr_path}"
        assert os.path.exists(core_path), f"Core file not found: {core_path}"

        # Load modules
        core_module = load_module_direct(core_path, "test_core")
        ports_lb_module = load_module_direct(ports_lb_path, "test_ports_lb")
        adapters_rr_module = load_module_direct(adapters_rr_path, "test_adapters_rr")

        # Verify key classes exist
        assert hasattr(ports_lb_module, "LoadBalancingStrategy"), "LoadBalancingStrategy not found"
        assert hasattr(adapters_rr_module, "RoundRobinBalancer"), "RoundRobinBalancer not found"
        assert hasattr(core_module, "ServiceInstance"), "ServiceInstance not found"

        print("SUCCESS: Ultra-direct import worked!")
        print(f"Found LoadBalancingStrategy: {ports_lb_module.LoadBalancingStrategy}")
        print(f"Found RoundRobinBalancer: {adapters_rr_module.RoundRobinBalancer}")
        print(f"Found ServiceInstance: {core_module.ServiceInstance}")

    except Exception as e:
        pytest.fail(f"Ultra-direct load balancing test failed: {e}")


@pytest.mark.asyncio
async def test_ultra_direct_service_instance():
    """Test ServiceInstance creation using ultra-direct loading."""
    try:
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..")
        core_path = os.path.join(src_dir, "discovery", "domain", "models.py")

        # Load core module directly
        core_module = load_module_direct(core_path, "test_core_si")
        ServiceInstance = core_module.ServiceInstance

        # Test instantiation
        try:
            instance = ServiceInstance(service_name="test-service", host="localhost", port=8080)
            print("SUCCESS: ServiceInstance created with service_name parameter")
        except Exception as e:
            pytest.fail(f"Could not create ServiceInstance: {e}")

        # Basic validation
        assert instance is not None
        print(f"ServiceInstance created successfully: {instance}")

    except Exception as e:
        pytest.fail(f"Ultra-direct ServiceInstance test failed: {e}")


@pytest.mark.asyncio
async def test_ultra_direct_round_robin():
    """Test RoundRobin load balancing using ultra-direct loading."""
    try:
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..")

        ports_lb_path = os.path.join(src_dir, "discovery", "ports", "load_balancer.py")
        adapters_rr_path = os.path.join(src_dir, "discovery", "adapters", "round_robin.py")
        core_path = os.path.join(src_dir, "discovery", "domain", "models.py")

        # Load modules directly
        core_module = load_module_direct(core_path, "test_core_rr")
        ports_lb_module = load_module_direct(ports_lb_path, "test_ports_lb_rr")
        adapters_rr_module = load_module_direct(adapters_rr_path, "test_adapters_rr_rr")

        ServiceInstance = core_module.ServiceInstance
        RoundRobinBalancer = adapters_rr_module.RoundRobinBalancer
        LoadBalancingConfig = ports_lb_module.LoadBalancingConfig

        # Create balancer
        config = LoadBalancingConfig(health_check_enabled=False)
        balancer = RoundRobinBalancer(config)

        # Create service instances
        instances = []
        for i, host in enumerate(["host1", "host2", "host3"]):
            instance = ServiceInstance(service_name=f"test-service-{i}", host=host, port=8080 + i)
            instances.append(instance)

        assert len(instances) == 3, "Should have created 3 service instances"

        # Update instances in balancer
        await balancer.update_instances(instances)

        # Test round-robin selection
        selections = []
        for _i in range(6):  # Go around twice
            selected = await balancer.select_instance()
            if selected and hasattr(selected, "endpoint") and hasattr(selected.endpoint, "host"):
                selections.append(selected.endpoint.host)
            else:
                selections.append(str(selected))

        print(f"Round-robin selections: {selections}")

        # Verify we got selections
        assert len(selections) == 6, "Should have 6 selections"
        assert all(s is not None for s in selections), "All selections should be non-None"

        # Check for cycling behavior (at least 2 different hosts selected)
        unique_selections = set(selections)
        assert (
            len(unique_selections) >= 2
        ), f"Should select from multiple hosts, got: {unique_selections}"

        print("SUCCESS: Round-robin load balancing worked!")

    except Exception as e:
        pytest.fail(f"Ultra-direct round-robin test failed: {e}")


def test_discover_load_balancing_classes():
    """Discover all load balancing classes using ultra-direct loading."""
    try:
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..")
        ports_lb_path = os.path.join(src_dir, "discovery", "ports", "load_balancer.py")

        # Load module directly
        lb_module = load_module_direct(ports_lb_path, "test_load_balancing_discovery")

        # Find all classes
        classes = []
        for name in dir(lb_module):
            if not name.startswith("_"):
                obj = getattr(lb_module, name)
                if isinstance(obj, type):
                    classes.append(name)

        print(f"All classes in load_balancing module: {classes}")

        # Find load balancing specific classes
        lb_classes = [
            name for name in classes if "Load" in name or "Balancer" in name or "Strategy" in name
        ]
        print(f"Load balancing classes: {lb_classes}")

        assert len(lb_classes) > 0, "Should find at least some load balancing classes"

    except Exception as e:
        pytest.fail(f"Class discovery test failed: {e}")
