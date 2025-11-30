"""
Tests for Plugin Manager Service
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from mmf_new.application.services.plugin_manager import PluginManager
from mmf_new.framework.plugins.models import (
    PluginMetadata,
    PluginStatus,
    ServiceDefinition,
)
from mmf_new.framework.plugins.ports import (
    IPluginDiscovery,
    IPluginEventSubscriptionManager,
    IPluginLoader,
    IPluginRegistry,
    IServiceManager,
    PluginInterface,
)


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

    async def test_load_plugin_not_found(self, plugin_manager):
        result = await plugin_manager.load_plugin("non_existent")
        assert result is False

    async def test_start_plugin_success(self, plugin_manager, mock_registry):
        plugin_name = "test_plugin"
        plugin_manager._plugin_status[plugin_name] = PluginStatus.LOADED

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_registry.get_plugin.return_value = mock_plugin

        result = await plugin_manager.start_plugin(plugin_name)

        assert result is True
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.ACTIVE
        mock_plugin.initialize.assert_called_once()
        mock_plugin.start.assert_called_once()

    async def test_stop_plugin_success(self, plugin_manager, mock_registry):
        plugin_name = "test_plugin"
        plugin_manager._plugin_status[plugin_name] = PluginStatus.ACTIVE

        mock_plugin = AsyncMock(spec=PluginInterface)
        mock_registry.get_plugin.return_value = mock_plugin

        result = await plugin_manager.stop_plugin(plugin_name)

        assert result is True
        assert plugin_manager.get_plugin_status(plugin_name) == PluginStatus.STOPPED
        mock_plugin.stop.assert_called_once()
