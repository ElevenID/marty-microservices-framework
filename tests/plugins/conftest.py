"""
Pytest Configuration for Plugin Tests

Configuration for running the plugin system test suite including:
- Test fixtures and setup
- Mock configurations
- Test environment setup
- Coverage configuration
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from marty_msf.framework.plugins import (
    MMFPlugin,
    PluginContext,
    PluginManager,
    PluginMetadata,
)
from plugins.marty.plugin_config import MartyTrustPKIConfig


# Mock classes for testing
class MockMetricsCollector:
    def increment_counter(self, name: str, labels=None):
        pass

    def start_timer(self, name: str, labels=None):
        return MockTimer()


class MockTimer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def stop(self):
        pass


class MockTracer:
    def start_span(self, name: str):
        return MockSpan()


class MockSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key: str, value):
        pass


# Test fixtures
@pytest.fixture
def mock_context():
    """Create mock plugin context with MMF services."""
    context = Mock(spec=PluginContext)
    context.database = AsyncMock()
    context.security = AsyncMock()
    context.observability = AsyncMock()
    context.cache = AsyncMock()
    context.message_bus = AsyncMock()
    context.config_manager = AsyncMock()

    # Mock database operations
    context.database.execute_ddl = AsyncMock()
    context.database.insert = AsyncMock()
    context.database.query_one = AsyncMock(return_value=None)

    # Mock security operations
    context.security.get_key_info = AsyncMock(return_value={"id": "test_key"})
    context.security.sign_data = AsyncMock(return_value=b"mock_signature")
    context.security.verify_signature = AsyncMock(return_value=True)

    # Mock observability
    context.observability.get_metrics_collector = Mock(return_value=MockMetricsCollector())
    context.observability.get_tracer = Mock(return_value=MockTracer())

    # Mock cache operations
    context.cache.get = AsyncMock(return_value=None)
    context.cache.set = AsyncMock()
    context.cache.delete_pattern = AsyncMock()

    # Mock message bus
    context.message_bus.publish = AsyncMock()

    return context


@pytest.fixture
def mock_plugin_manager():
    """Create mock plugin manager."""
    manager = Mock(spec=PluginManager)
    manager.get_plugin = Mock(return_value=None)
    return manager


@pytest.fixture
def marty_config():
    """Create test Marty configuration."""
    try:

        return MartyTrustPKIConfig(
            trust_anchor_url="https://test-trust.example.com",
            pkd_url="https://test-pkd.example.com",
            document_signer_url="https://test-signer.example.com",
            signing_algorithms=["RSA-SHA256", "ECDSA-SHA256"],
            certificate_validation_enabled=True,
            require_mutual_tls=True,
        )
    except ImportError:
        # Return mock config if MartyTrustPKIConfig isn't available
        return {
            "trust_anchor_url": "https://test-trust.example.com",
            "pkd_url": "https://test-pkd.example.com",
            "document_signer_url": "https://test-signer.example.com",
            "signing_algorithms": ["RSA-SHA256", "ECDSA-SHA256"],
            "certificate_validation_enabled": True,
            "require_mutual_tls": True,
        }


# Test Plugin Classes for Testing
class MockPlugin(MMFPlugin):
    """Mock plugin for unit tests."""

    def __init__(self):
        self.initialized = False
        self.started = False
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test-plugin", version="1.0.0", description="Test plugin for unit testing"
        )

    async def _initialize_plugin(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    async def get_health_status(self):
        return {"status": "healthy" if self.started else "stopped", "initialized": self.initialized}


class FailingPlugin(MMFPlugin):
    """Plugin that fails during operations for testing error handling."""

    def __init__(self):
        self.initialized = False
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="failing-plugin", version="1.0.0", description="Plugin that fails for testing"
        )

    async def _initialize_plugin(self):
        raise RuntimeError("Plugin initialization failed")

    async def start(self):
        raise RuntimeError("Plugin start failed")

    async def stop(self):
        raise RuntimeError("Plugin stop failed")

    async def get_health_status(self):
        return {"status": "error", "error": "Plugin in error state"}


class FailingStartPlugin(MMFPlugin):
    """Plugin that fails only during start for testing error handling."""

    def __init__(self):
        self.initialized = False
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="failing-start-plugin", version="1.0.0", description="Plugin that fails on start"
        )

    async def _initialize_plugin(self):
        self.initialized = True

    async def start(self):
        raise RuntimeError("Plugin start failed")

    async def stop(self):
        pass

    async def get_health_status(self):
        return {"status": "error", "error": "Start failed"}


# Keep TestPlugin for backward compatibility
TestPlugin = MockPlugin


# Configure pytest for async tests
def pytest_configure(config):
    """Configure pytest for the plugin test suite."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_mmf_services():
    """Create mock MMF services for testing."""
    services = Mock()

    # Database service mock
    services.database = AsyncMock()
    services.database.execute_ddl = AsyncMock()
    services.database.insert = AsyncMock()
    services.database.query_one = AsyncMock(return_value=None)
    services.database.query_many = AsyncMock(return_value=[])
    services.database.update = AsyncMock()
    services.database.delete = AsyncMock()

    # Security service mock
    services.security = AsyncMock()
    services.security.get_key_info = AsyncMock(return_value={"id": "test_key", "type": "RSA"})
    services.security.sign_data = AsyncMock(return_value=b"mock_signature")
    services.security.verify_signature = AsyncMock(return_value=True)
    services.security.encrypt_data = AsyncMock(return_value=b"encrypted_data")
    services.security.decrypt_data = AsyncMock(return_value=b"decrypted_data")

    # Cache service mock
    services.cache = AsyncMock()
    services.cache.get = AsyncMock(return_value=None)
    services.cache.set = AsyncMock()
    services.cache.delete = AsyncMock()
    services.cache.delete_pattern = AsyncMock()
    services.cache.exists = AsyncMock(return_value=False)

    # Message bus mock
    services.message_bus = AsyncMock()
    services.message_bus.publish = AsyncMock()
    services.message_bus.subscribe = AsyncMock()
    services.message_bus.unsubscribe = AsyncMock()

    # Observability service mock
    services.observability = Mock()

    # Metrics collector mock
    metrics_collector = Mock()
    metrics_collector.increment_counter = Mock()
    metrics_collector.record_gauge = Mock()
    metrics_collector.start_timer = Mock(return_value=Mock(stop=Mock()))
    services.observability.get_metrics_collector = Mock(return_value=metrics_collector)

    # Tracer mock
    tracer = Mock()
    span = Mock()
    span.__enter__ = Mock(return_value=span)
    span.__exit__ = Mock(return_value=None)
    span.set_attribute = Mock()
    tracer.start_span = Mock(return_value=span)
    services.observability.get_tracer = Mock(return_value=tracer)

    # Configuration manager mock
    services.config_manager = Mock()
    services.config_manager.get_plugin_config = Mock()
    services.config_manager.load_plugin_config = Mock()

    return services


@pytest.fixture
def test_plugin_directory(tmp_path):
    """Create a temporary directory structure for testing plugins."""
    plugin_dir = tmp_path / "test_plugins"
    plugin_dir.mkdir()

    # Create a sample plugin structure
    sample_plugin = plugin_dir / "sample-plugin"
    sample_plugin.mkdir()

    # Create manifest
    manifest_content = """{
    "name": "sample-plugin",
    "version": "1.0.0",
    "description": "Sample plugin for testing",
    "author": "Test Suite",
    "entry_point": "plugin.py",
    "dependencies": [],
    "optional_dependencies": []
}"""

    (sample_plugin / "manifest.json").write_text(manifest_content)

    # Create plugin module
    plugin_content = """
from typing import Dict, Any

class SamplePlugin:
    def __init__(self):
        self.context = None
        self.started = False

    async def initialize(self, context):
        self.context = context

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    async def get_health_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.started else "stopped",
            "plugin": "sample-plugin"
        }

def create_plugin():
    return SamplePlugin()
"""

    (sample_plugin / "plugin.py").write_text(plugin_content)

    return plugin_dir


@pytest.fixture
def test_config_directory(tmp_path):
    """Create a temporary configuration directory for testing."""
    config_dir = tmp_path / "test_config"
    config_dir.mkdir()

    # Create sample configurations
    configs = {
        "base.json": {"environment": "test", "debug": True, "plugins": {"enabled": True}},
        "marty.json": {
            "enabled": True,
            "trust_anchor_url": "https://test-trust.example.com",
            "pkd_url": "https://test-pkd.example.com",
            "document_signer_url": "https://test-signer.example.com",
            "signing_algorithms": ["RSA-SHA256", "ECDSA-SHA256"],
            "certificate_validation_enabled": True,
            "require_mutual_tls": False,
        },
        "test-plugin.yaml": """
enabled: true
test_setting: test_value
numeric_setting: 42
list_setting:
  - item1
  - item2
  - item3
""",
        "development.json": {
            "log_level": "DEBUG",
            "database": {"url": "sqlite:///test.db"},
            "cache": {"type": "memory"},
        },
    }



    for filename, config_data in configs.items():
        config_file = config_dir / filename

        if filename.endswith(".json"):
            with open(config_file, "w") as f:
                json.dump(config_data, f, indent=2)
        elif filename.endswith(".yaml") or filename.endswith(".yml"):
            with open(config_file, "w") as f:
                if isinstance(config_data, str):
                    f.write(config_data)
                else:
                    yaml.dump(config_data, f)

    return config_dir


@pytest.fixture
def plugin_test_data():
    """Provide test data for plugin tests."""
    return {
        "valid_plugin_metadata": {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "Test plugin for unit testing",
            "author": "Test Author",
            "dependencies": ["dependency1"],
            "optional_dependencies": ["optional1"],
        },
        "service_definition": {
            "name": "test-service",
            "version": "1.0.0",
            "description": "Test service",
            "routes": {
                "/api/test": {"methods": ["GET"], "handler": "test_handler"},
                "/api/status": {"methods": ["GET"], "handler": "status_handler"},
            },
            "dependencies": ["database"],
            "health_check_path": "/health",
        },
        "marty_config": {
            "trust_anchor_url": "https://test-trust.example.com",
            "pkd_url": "https://test-pkd.example.com",
            "document_signer_url": "https://test-signer.example.com",
            "signing_algorithms": ["RSA-SHA256", "ECDSA-SHA256"],
            "certificate_validation_enabled": True,
            "require_mutual_tls": True,
        },
        "test_certificates": {
            "valid_cert": "-----BEGIN CERTIFICATE-----\nMIICWjCCAcMCAg...\n-----END CERTIFICATE-----",
            "expired_cert": "-----BEGIN CERTIFICATE-----\nMIICWjCCAcMCAg...\n-----END CERTIFICATE-----",
            "invalid_cert": "invalid certificate data",
        },
        "pki_test_data": {
            "document_to_sign": b"test document content for signing",
            "trust_anchor": {
                "id": "test_anchor_1",
                "certificate": "-----BEGIN CERTIFICATE-----...",
                "issuer": "Test CA",
                "valid_from": "2024-01-01",
                "valid_to": "2025-01-01",
            },
            "pkd_entry": {
                "certificate_id": "cert_123",
                "issuer": "Test PKI",
                "subject": "Test Subject",
                "serial_number": "123456789",
                "valid_from": "2024-01-01",
                "valid_to": "2025-01-01",
            },
        },
    }


# Pytest markers for test categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.security = pytest.mark.security


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers and organize tests."""
    for item in items:
        # Add markers based on test file names
        if "test_core" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_services" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_discovery" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_config" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_marty_plugin" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Add performance marker for performance tests
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.performance)

        # Add security marker for security tests
        if "security" in item.name.lower() or "sensitive" in item.name.lower():
            item.add_marker(pytest.mark.security)
