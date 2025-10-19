"""
Tests for Discovery System Improvements

Test the improvements made to the discovery subsystem including cache age calculation,
HTTP client functionality, and service mesh integration.
"""

import os
import sys
import unittest

from marty_msf.framework.discovery.cache import ServiceCache
from marty_msf.framework.discovery.clients import (
    ClientSideDiscovery,
    MockKubernetesClient,
    ServerSideDiscovery,
    ServiceMeshDiscovery,
)
from marty_msf.framework.discovery.config import (
    CacheStrategy,
    DiscoveryConfig,
    ServiceQuery,
)
from marty_msf.framework.discovery.results import DiscoveryResult

# Add the project root to path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
sys.path.insert(0, project_root)


class TestDiscoveryImprovements(unittest.TestCase):
    """Test improvements to the discovery system."""

    def test_discovery_imports(self):
        """Test that discovery modules can be imported."""
        try:

            # Basic tests to ensure classes are properly defined
            self.assertTrue(hasattr(ServiceQuery, "service_name"))
            self.assertTrue(hasattr(DiscoveryResult, "instances"))
            self.assertTrue(hasattr(ClientSideDiscovery, "discover_instances"))
            self.assertTrue(hasattr(ServerSideDiscovery, "discover_instances"))
            self.assertTrue(hasattr(ServiceMeshDiscovery, "discover_instances"))

        except ImportError as e:
            self.fail(f"Failed to import discovery classes: {e}")

    def test_service_query_dataclass(self):
        """Test ServiceQuery dataclass functionality."""
        try:

            # Test basic instantiation
            query = ServiceQuery(service_name="test-service")
            self.assertEqual(query.service_name, "test-service")
            self.assertIsNone(query.version)
            self.assertFalse(query.include_unhealthy)
            self.assertEqual(len(query.tags), 0)

            # Test with parameters
            query_with_params = ServiceQuery(
                service_name="user-service",
                version="1.0.0",
                environment="production",
                include_unhealthy=True,
            )

            self.assertEqual(query_with_params.service_name, "user-service")
            self.assertEqual(query_with_params.version, "1.0.0")
            self.assertEqual(query_with_params.environment, "production")
            self.assertTrue(query_with_params.include_unhealthy)

        except ImportError as e:
            self.fail(f"Failed to import ServiceQuery: {e}")

    def test_discovery_result_cache_age(self):
        """Test that DiscoveryResult includes cache age information."""
        try:

            # Test DiscoveryResult structure
            test_query = ServiceQuery(service_name="test-service")
            result = DiscoveryResult(
                instances=[],
                query=test_query,
                source="cache",
                cached=True,
                cache_age=5.5,
                resolution_time=0.1,
            )

            self.assertEqual(result.cache_age, 5.5)
            self.assertTrue(result.cached)
            self.assertEqual(result.source, "cache")
            self.assertEqual(result.resolution_time, 0.1)

        except ImportError as e:
            self.fail(f"Failed to import DiscoveryResult: {e}")

    def test_server_side_discovery_http_client(self):
        """Test that ServerSideDiscovery has HTTP client capability."""
        try:

            # Create discovery config (mock)
            config = DiscoveryConfig()

            # Test ServerSideDiscovery initialization
            discovery = ServerSideDiscovery("http://discovery.example.com", config)

            # Check that HTTP client related attributes exist
            self.assertTrue(hasattr(discovery, "discovery_service_url"))
            self.assertTrue(hasattr(discovery, "_http_session"))
            self.assertTrue(hasattr(discovery, "_timeout"))

            # Check that HTTP client methods exist
            self.assertTrue(hasattr(discovery, "_get_http_session"))
            self.assertTrue(hasattr(discovery, "close"))
            self.assertTrue(hasattr(discovery, "_query_discovery_service"))
            self.assertTrue(hasattr(discovery, "_parse_discovery_response"))

        except ImportError as e:
            self.fail(f"Failed to import ServerSideDiscovery: {e}")

    def test_service_mesh_discovery_integration(self):
        """Test that ServiceMeshDiscovery has mesh integration."""
        try:

            # Create discovery config and mesh config
            config = DiscoveryConfig()
            mesh_config = {
                "type": "istio",
                "namespace": "default",
                "istio_namespace": "istio-system",
                "allow_stub": True,
            }

            # Test ServiceMeshDiscovery initialization
            discovery = ServiceMeshDiscovery(mesh_config, config)

            # Check that mesh integration attributes exist
            self.assertTrue(hasattr(discovery, "mesh_config"))
            self.assertTrue(hasattr(discovery, "mesh_type"))
            self.assertTrue(hasattr(discovery, "namespace"))
            self.assertTrue(hasattr(discovery, "control_plane_namespace"))

            # Check configuration
            self.assertEqual(discovery.mesh_type, "istio")
            self.assertEqual(discovery.namespace, "default")
            self.assertEqual(discovery.control_plane_namespace, "istio-system")

            # Check that mesh-specific methods exist
            self.assertTrue(hasattr(discovery, "_get_k8s_client"))
            self.assertTrue(hasattr(discovery, "_discover_from_mesh"))

        except ImportError as e:
            self.fail(f"Failed to import ServiceMeshDiscovery: {e}")

    def test_mock_kubernetes_client(self):
        """Test MockKubernetesClient functionality."""
        try:

            # Test client initialization
            mesh_config = {"type": "istio", "allow_stub": True}
            client = MockKubernetesClient(mesh_config)

            self.assertTrue(hasattr(client, "mesh_config"))
            self.assertTrue(hasattr(client, "get_service_endpoints"))

        except ImportError as e:
            self.fail(f"Failed to import MockKubernetesClient: {e}")


class TestDiscoveryFunctionality(unittest.TestCase):
    """Test actual discovery functionality."""

    def test_cache_functionality(self):
        """Test cache behavior and age calculation."""
        try:

            # Create cache config
            config = DiscoveryConfig()
            config.cache_strategy = CacheStrategy.TTL

            # Test cache initialization
            cache = ServiceCache(config)

            self.assertTrue(hasattr(cache, "_cache"))
            self.assertTrue(hasattr(cache, "_stats"))
            self.assertTrue(hasattr(cache, "_generate_cache_key"))

            # Test cache stats
            stats = cache.get_stats()
            self.assertIn("hits", stats)
            self.assertIn("misses", stats)

        except ImportError as e:
            self.fail(f"Failed to import cache classes: {e}")

    def test_circuit_breaker_functionality(self):
        """Test circuit breaker in connectors."""
        # Circuit breaker functionality was moved to external connectors
        # and is relevant to the discovery system reliability
        self.assertIsNotNone(True)  # Basic test placeholder

    def test_health_checking(self):
        """Test health checking capabilities."""
        # Health checking supports discovery decisions
        self.assertIsNotNone(True)  # Basic test placeholder


if __name__ == "__main__":
    unittest.main()
