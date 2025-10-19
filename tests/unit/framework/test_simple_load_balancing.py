"""
Simple test to verify load balancing imports work.
"""

import pytest

from marty_msf.framework.discovery.load_balancing import (
    LoadBalancingStrategy,
    ServiceInstance,
)


def test_import_load_balancing():
    """Test that we can import the load balancing module."""
    try:

        assert LoadBalancingStrategy is not None
    except ImportError as e:
        pytest.fail(f"Could not import LoadBalancingStrategy: {e}")


def test_import_service_instance():
    """Test that we can import ServiceInstance."""
    try:

        # Create a simple instance
        instance = ServiceInstance(service_name="test-service", host="localhost", port=8080)
        assert instance.service_name == "test-service"
        assert instance.endpoint.host == "localhost"
        assert instance.endpoint.port == 8080

    except ImportError as e:
        pytest.fail(f"Could not import ServiceInstance: {e}")
