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
        src_dir = os.path.join(test_dir, "..", "..", "..", "src")
        lb_path = os.path.join(src_dir, "framework", "discovery", "load_balancing.py")
        core_path = os.path.join(src_dir, "framework", "discovery", "core.py")

        # Verify files exist
        assert os.path.exists(lb_path), f"Load balancing file not found: {lb_path}"
        assert os.path.exists(core_path), f"Core file not found: {core_path}"

        # Load core module first (ServiceInstance dependency)
        core_module = load_module_direct(core_path, "test_core")

        # Load load balancing module
        lb_module = load_module_direct(lb_path, "test_load_balancing")

        # Verify key classes exist
        assert hasattr(lb_module, "LoadBalancingStrategy"), "LoadBalancingStrategy not found"
        assert hasattr(lb_module, "RoundRobinLoadBalancer"), "RoundRobinLoadBalancer not found"
        assert hasattr(core_module, "ServiceInstance"), "ServiceInstance not found"

        print("SUCCESS: Ultra-direct import worked!")
        print(f"Found LoadBalancingStrategy: {lb_module.LoadBalancingStrategy}")
        print(f"Found RoundRobinLoadBalancer: {lb_module.RoundRobinLoadBalancer}")
        print(f"Found ServiceInstance: {core_module.ServiceInstance}")

    except Exception as e:
        pytest.fail(f"Ultra-direct load balancing test failed: {e}")


@pytest.mark.asyncio
async def test_ultra_direct_service_instance():
    """Test ServiceInstance creation using ultra-direct loading."""
    try:
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..", "src")
        core_path = os.path.join(src_dir, "framework", "discovery", "core.py")

        # Load core module directly
        core_module = load_module_direct(core_path, "test_core_si")
        ServiceInstance = core_module.ServiceInstance

        # Test instantiation - determine the correct constructor signature
        try:
            # Try the expected signature
            instance = ServiceInstance(service_name="test-service", host="localhost", port=8080)
            print("SUCCESS: ServiceInstance created with service_name parameter")
        except Exception as e1:
            try:
                # Try alternative signature with 'name'
                instance = ServiceInstance(name="test-service", host="localhost", port=8080)
                print("SUCCESS: ServiceInstance created with name parameter")
            except Exception as e2:
                print("Constructor signatures failed:")
                print(f"  service_name attempt: {e1}")
                print(f"  name attempt: {e2}")
                pytest.fail("Could not create ServiceInstance with any known signature")

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
        src_dir = os.path.join(test_dir, "..", "..", "..", "src")
        lb_path = os.path.join(src_dir, "framework", "discovery", "load_balancing.py")
        core_path = os.path.join(src_dir, "framework", "discovery", "core.py")

        # Load modules directly
        core_module = load_module_direct(core_path, "test_core_rr")
        lb_module = load_module_direct(lb_path, "test_load_balancing_rr")

        ServiceInstance = core_module.ServiceInstance
        RoundRobinLoadBalancer = lb_module.RoundRobinLoadBalancer

        # Create balancer
        balancer = RoundRobinLoadBalancer()

        # Create service instances - try different constructor signatures
        instances = []
        for i, host in enumerate(["host1", "host2", "host3"]):
            try:
                instance = ServiceInstance(
                    service_name=f"test-service-{i}", host=host, port=8080 + i
                )
                instances.append(instance)
            except Exception:
                try:
                    instance = ServiceInstance(name=f"test-service-{i}", host=host, port=8080 + i)
                    instances.append(instance)
                except Exception as e:
                    pytest.fail(f"Could not create ServiceInstance for {host}: {e}")

        assert len(instances) == 3, "Should have created 3 service instances"

        # Test round-robin selection
        selections = []
        for _i in range(6):  # Go around twice
            selected = await balancer.select_instance(instances)
            if selected and hasattr(selected, "host"):
                selections.append(selected.host)
            else:
                selections.append(str(selected))

        print(f"Round-robin selections: {selections}")

        # Verify we got selections
        assert len(selections) == 6, "Should have 6 selections"
        assert all(s is not None for s in selections), "All selections should be non-None"

        # Check for cycling behavior (at least 2 different hosts selected)
        unique_selections = set(selections)
        assert len(unique_selections) >= 2, (
            f"Should select from multiple hosts, got: {unique_selections}"
        )

        print("SUCCESS: Round-robin load balancing worked!")

    except Exception as e:
        pytest.fail(f"Ultra-direct round-robin test failed: {e}")


def test_discover_load_balancing_classes():
    """Discover all load balancing classes using ultra-direct loading."""
    try:
        test_dir = os.path.dirname(__file__)
        src_dir = os.path.join(test_dir, "..", "..", "..", "src")
        lb_path = os.path.join(src_dir, "framework", "discovery", "load_balancing.py")

        # Load module directly
        lb_module = load_module_direct(lb_path, "test_load_balancing_discovery")

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
