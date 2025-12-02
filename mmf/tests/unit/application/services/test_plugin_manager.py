"""
Tests for Plugin Manager Service
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from mmf.application.services.plugin_manager import (
    PluginEventSubscriptionManager,
    PluginManager,
    ServiceManager,
)
from mmf.framework.plugins.models import (
    PluginMetadata,
    PluginStatus,
    ServiceDefinition,
    ServiceStatus,
)
from mmf.framework.plugins.ports import (
    IPluginDiscovery,
    IPluginEventSubscriptionManager,
    IPluginLoader,
    IPluginRegistry,
    IServiceManager,
    PluginInterface,
)


@pytest.mark.asyncio
class TestServiceManager:
    @pytest.fixture
    def service_manager(self):
        return ServiceManager()

    @pytest.fixture
    def sample_service_def(self):
        return ServiceDefinition(
            name="test-service",
            version="1.0.0",
            description="Test Service",
        )

    async def test_register_service(self, service_manager, sample_service_def):
        result = await service_manager.register_service("plugin1", sample_service_def)
        assert result is True

        service = await service_manager.get_service("plugin1", "test-service")
        assert service == sample_service_def

        status = await service_manager.get_service_status("plugin1", "test-service")
        assert status == ServiceStatus.INACTIVE

    async def test_register_service_error(self, service_manager):
        # Mock internal dict to raise exception on setitem
        service_manager._services = MagicMock()
        service_manager._services.__setitem__.side_effect = Exception("Storage error")
        service_manager._services.__contains__.return_value = False  # Ensure it tries to set

        result = await service_manager.register_service("plugin1", Mock())
        assert result is False

    async def test_unregister_service(self, service_manager, sample_service_def):
        await service_manager.register_service("plugin1", sample_service_def)

        result = await service_manager.unregister_service("plugin1", "test-service")
        assert result is True

        service = await service_manager.get_service("plugin1", "test-service")
        assert service is None

    async def test_unregister_service_not_found(self, service_manager):
        result = await service_manager.unregister_service("plugin1", "non-existent")
        assert result is False

    async def test_list_services(self, service_manager, sample_service_def):
        await service_manager.register_service("plugin1", sample_service_def)

        # Test list all
        all_services = await service_manager.list_services()
        assert "plugin1" in all_services
        assert len(all_services["plugin1"]) == 1

        # Test filter by plugin
        plugin_services = await service_manager.list_services("plugin1")
        assert "plugin1" in plugin_services
        assert len(plugin_services["plugin1"]) == 1

        # Test filter by non-existent plugin
        empty_services = await service_manager.list_services("plugin2")
        assert "plugin2" in empty_services
        assert len(empty_services["plugin2"]) == 0


@pytest.mark.asyncio
class TestPluginEventSubscriptionManager:
    @pytest.fixture
    def event_manager(self):
        return PluginEventSubscriptionManager()

    async def test_subscribe_and_publish(self, event_manager):
        handler_mock = AsyncMock()
        event_type = "test_event"
        plugin_name = "plugin1"

        await event_manager.subscribe(plugin_name, event_type, handler_mock)

        event_data = {"key": "value"}
        await event_manager.publish_event(event_type, event_data)

        handler_mock.assert_called_once_with(event_data)

    async def test_unsubscribe(self, event_manager):
        handler_mock = AsyncMock()
        event_type = "test_event"
        plugin_name = "plugin1"

        await event_manager.subscribe(plugin_name, event_type, handler_mock)
        await event_manager.unsubscribe(plugin_name, event_type)

        await event_manager.publish_event(event_type, {})

        handler_mock.assert_not_called()

    async def test_publish_event_handler_error(self, event_manager):
        handler_mock = AsyncMock(side_effect=Exception("Handler failed"))
        event_type = "test_event"

        await event_manager.subscribe("plugin1", event_type, handler_mock)

        # Should not raise exception
        await event_manager.publish_event(event_type, {})

        handler_mock.assert_called_once()


@pytest.mark.asyncio
class TestPluginManager:
    @pytest.fixture
    def mock_discovery(self):
        return AsyncMock(spec=IPluginDiscovery)

    @pytest.fixture
    def mock_loader(self):
        return AsyncMock(spec=IPluginLoader)

    @pytest.fixture
    def mock_registry(self):
        return Mock(spec=IPluginRegistry)

    @pytest.fixture
    def mock_service_manager(self):
        return AsyncMock(spec=IServiceManager)

    @pytest.fixture
    def mock_event_manager(self):
        return AsyncMock(spec=IPluginEventSubscriptionManager)

    @pytest.fixture
    def plugin_manager(
        self, mock_discovery, mock_loader, mock_registry, mock_service_manager, mock_event_manager
    ):
        return PluginManager(
            discovery=mock_discovery,
            loader=mock_loader,
            registry=mock_registry,
            service_manager=mock_service_manager,
            event_manager=mock_event_manager,
        )

    async def test_discover_plugins(self, plugin_manager, mock_discovery):
        mock_discovery.discover.return_value = ["/path/to/plugin1", "/path/to/plugin2"]

        result = await plugin_manager.discover_plugins(["/path/to"])

        assert len(result) == 2
        assert "plugin1" in result
        assert "plugin2" in result
        assert plugin_manager._plugin_paths["plugin1"] == "/path/to/plugin1"

    async def test_load_plugin_success(
        self, plugin_manager, mock_loader, mock_registry, mock_service_manager
    ):
        plugin_name = "test_plugin"
        plugin_path = "/path/to/test_plugin"
        plugin_manager._plugin_paths[plugin_name] = plugin_path

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_metadata = PluginMetadata(name=plugin_name, version="1.0.0", description="Test")
        mock_plugin.get_metadata.return_value = mock_metadata
        mock_plugin.get_service_definitions.return_value = []

        mock_loader.load.return_value = mock_plugin
        mock_registry.register.return_value = True

        result = await plugin_manager.load_plugin(plugin_name)

        assert result is True
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.LOADED
        mock_loader.load.assert_called_with(plugin_name, plugin_path)
        mock_registry.register.assert_called_with(plugin_name, mock_plugin, mock_metadata)

    async def test_load_plugin_already_loaded(self, plugin_manager):
        plugin_manager._plugin_status["test_plugin"] = PluginStatus.LOADED
        result = await plugin_manager.load_plugin("test_plugin")
        assert result is False

    async def test_load_plugin_registry_failure(self, plugin_manager, mock_loader, mock_registry):
        plugin_name = "test_plugin"
        plugin_manager._plugin_paths[plugin_name] = "/path"

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_loader.load.return_value = mock_plugin
        mock_registry.register.return_value = False  # Registry fails

        result = await plugin_manager.load_plugin(plugin_name)

        assert result is False
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.ERROR

    async def test_load_plugin_exception(self, plugin_manager, mock_loader):
        plugin_name = "test_plugin"
        plugin_manager._plugin_paths[plugin_name] = "/path"
        mock_loader.load.side_effect = Exception("Load error")

        result = await plugin_manager.load_plugin(plugin_name)

        assert result is False
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.ERROR

    async def test_unload_plugin_success(
        self, plugin_manager, mock_loader, mock_registry, mock_service_manager
    ):
        plugin_name = "test_plugin"
        plugin_manager._plugin_status[plugin_name] = PluginStatus.LOADED

        # Mock services to unregister
        mock_service_def = Mock(spec=ServiceDefinition)
        mock_service_def.name = "service1"
        mock_service_manager.list_services.return_value = {plugin_name: [mock_service_def]}

        result = await plugin_manager.unload_plugin(plugin_name)

        assert result is True
        assert plugin_name not in plugin_manager._plugin_status
        mock_service_manager.unregister_service.assert_called_with(plugin_name, "service1")
        mock_loader.unload.assert_called_with(plugin_name)
        mock_registry.unregister.assert_called_with(plugin_name)

    async def test_unload_plugin_active(self, plugin_manager, mock_registry, mock_service_manager):
        plugin_name = "test_plugin"
        plugin_manager._plugin_status[plugin_name] = PluginStatus.ACTIVE

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_registry.get_plugin.return_value = mock_plugin

        # Ensure list_services returns an empty dict to avoid iteration error
        mock_service_manager.list_services.return_value = {}

        result = await plugin_manager.unload_plugin(plugin_name)

        assert result is True
        mock_plugin.stop.assert_called_once()  # Should stop before unloading

    async def test_unload_plugin_not_loaded(self, plugin_manager):
        result = await plugin_manager.unload_plugin("not_loaded")
        assert result is False

    async def test_start_plugin_not_loaded(self, plugin_manager):
        result = await plugin_manager.start_plugin("not_loaded")
        assert result is False

    async def test_start_plugin_not_in_registry(self, plugin_manager, mock_registry):
        plugin_manager._plugin_status["test_plugin"] = PluginStatus.LOADED
        mock_registry.get_plugin.return_value = None

        result = await plugin_manager.start_plugin("test_plugin")
        assert result is False

    async def test_start_plugin_exception(self, plugin_manager, mock_registry):
        plugin_name = "test_plugin"
        plugin_manager._plugin_status[plugin_name] = PluginStatus.LOADED

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_plugin.start.side_effect = Exception("Start error")
        mock_registry.get_plugin.return_value = mock_plugin

        result = await plugin_manager.start_plugin(plugin_name)

        assert result is False
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.ERROR

    async def test_stop_plugin_not_active(self, plugin_manager):
        plugin_manager._plugin_status["test_plugin"] = PluginStatus.LOADED
        result = await plugin_manager.stop_plugin("test_plugin")
        assert result is False

    async def test_list_plugins(self, plugin_manager):
        plugin_manager._plugin_status = {"p1": PluginStatus.LOADED, "p2": PluginStatus.ACTIVE}
        result = plugin_manager.list_plugins()
        assert result == {"p1": PluginStatus.LOADED, "p2": PluginStatus.ACTIVE}

    async def test_get_plugin_metadata(self, plugin_manager, mock_registry):
        plugin_manager.get_plugin_metadata("test_plugin")
        mock_registry.get_metadata.assert_called_with("test_plugin")

    async def test_add_plugin_path(self, plugin_manager):
        plugin_manager.add_plugin_path("test", "/path")
        assert plugin_manager._plugin_paths["test"] == "/path"
