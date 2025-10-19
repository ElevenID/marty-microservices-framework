"""
Plugin discovery mechanisms for MMF.

This module provides different strategies for discovering and loading plugins:
- DirectoryPluginDiscoverer: Discover plugins from filesystem directories
- PackagePluginDiscoverer: Discover plugins from installed Python packages
"""

import importlib
import importlib.util
import logging
import pkgutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

import pkg_resources

from .core import MMFPlugin

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""

    name: str
    version: str
    path: Path
    module_name: str
    plugin_class: type[MMFPlugin] | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


class PluginDiscoverer(ABC):
    """Abstract base class for plugin discovery strategies."""

    @abstractmethod
    async def discover(self) -> list[PluginInfo]:
        """Discover available plugins.

        Returns:
            List of discovered plugin information
        """
        pass


class DirectoryPluginDiscoverer(PluginDiscoverer):
    """Discover plugins from filesystem directories.

    This discoverer looks for Python modules in specified directories
    that contain MMF plugin implementations.
    """

    def __init__(self, directories: list[Path], pattern: str = "*_plugin.py"):
        """Initialize directory-based plugin discovery.

        Args:
            directories: List of directories to search for plugins
            pattern: File pattern to match plugin files
        """
        self.directories = [Path(d) for d in directories]
        self.pattern = pattern
        self.logger = logging.getLogger("plugin.discovery.directory")

    async def discover(self) -> list[PluginInfo]:
        """Discover plugins from directories.

        Returns:
            List of discovered plugin information
        """
        discovered = []

        for directory in self.directories:
            if not directory.exists():
                self.logger.warning(f"Plugin directory does not exist: {directory}")
                continue

            if not directory.is_dir():
                self.logger.warning(f"Plugin path is not a directory: {directory}")
                continue

            self.logger.debug(f"Scanning directory for plugins: {directory}")
            directory_plugins = await self._scan_directory(directory)
            discovered.extend(directory_plugins)

        self.logger.info(f"Discovered {len(discovered)} plugins from directories")
        return discovered

    async def _scan_directory(self, directory: Path) -> list[PluginInfo]:
        """Scan a single directory for plugins.

        Args:
            directory: Directory to scan

        Returns:
            List of plugin info from this directory
        """
        plugins = []

        for plugin_file in directory.glob(self.pattern):
            if plugin_file.is_file() and plugin_file.suffix == ".py":
                plugin_info = await self._load_plugin_from_file(plugin_file)
                if plugin_info:
                    plugins.append(plugin_info)

        return plugins

    async def _load_plugin_from_file(self, plugin_file: Path) -> PluginInfo | None:
        """Load plugin information from a Python file.

        Args:
            plugin_file: Path to plugin file

        Returns:
            Plugin info or None if loading failed
        """
        try:
            # Generate module name
            module_name = f"plugin.{plugin_file.stem}"

            # Load module spec
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if not spec or not spec.loader:
                self.logger.error(f"Could not load spec for {plugin_file}")
                return None

            # Load module
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find plugin class
            plugin_class = self._find_plugin_class(module)
            if not plugin_class:
                self.logger.warning(f"No plugin class found in {plugin_file}")
                return None

            # Create plugin instance to get metadata
            plugin_instance = plugin_class()
            metadata = plugin_instance.metadata

            return PluginInfo(
                name=metadata.name,
                version=metadata.version,
                path=plugin_file,
                module_name=module_name,
                plugin_class=plugin_class,
                metadata={
                    "description": metadata.description,
                    "author": metadata.author,
                    "dependencies": metadata.dependencies,
                    "tags": metadata.tags,
                },
            )

        except Exception as e:
            self.logger.error(f"Error loading plugin from {plugin_file}: {e}")
            return PluginInfo(
                name=plugin_file.stem,
                version="unknown",
                path=plugin_file,
                module_name="",
                error=str(e),
            )

    def _find_plugin_class(self, module) -> type[MMFPlugin] | None:
        """Find the plugin class in a module.

        Args:
            module: Loaded Python module

        Returns:
            Plugin class or None if not found
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            # Check if it's a class that inherits from MMFPlugin
            if isinstance(attr, type) and issubclass(attr, MMFPlugin) and attr is not MMFPlugin:
                return attr

        return None


class PackagePluginDiscoverer(PluginDiscoverer):
    """Discover plugins from installed Python packages.

    This discoverer looks for plugins in installed packages using
    entry points or package naming conventions.
    """

    def __init__(self, entry_point_group: str = "mmf.plugins", package_prefix: str = "mmf_plugin_"):
        """Initialize package-based plugin discovery.

        Args:
            entry_point_group: Entry point group name for plugins
            package_prefix: Package name prefix for plugins
        """
        self.entry_point_group = entry_point_group
        self.package_prefix = package_prefix
        self.logger = logging.getLogger("plugin.discovery.package")

    async def discover(self) -> list[PluginInfo]:
        """Discover plugins from installed packages.

        Returns:
            List of discovered plugin information
        """
        discovered = []

        # Discover from entry points
        entry_point_plugins = await self._discover_from_entry_points()
        discovered.extend(entry_point_plugins)

        # Discover from package naming convention
        package_plugins = await self._discover_from_packages()
        discovered.extend(package_plugins)

        self.logger.info(f"Discovered {len(discovered)} plugins from packages")
        return discovered

    async def _discover_from_entry_points(self) -> list[PluginInfo]:
        """Discover plugins using entry points.

        Returns:
            List of plugin info from entry points
        """
        plugins = []

        try:
            # Try new importlib.metadata first (Python 3.8+)
            try:

                eps = entry_points(group=self.entry_point_group)
            except ImportError:
                # Fallback to pkg_resources

                eps = pkg_resources.iter_entry_points(self.entry_point_group)

            for entry_point in eps:
                try:
                    plugin_class = entry_point.load()

                    if not issubclass(plugin_class, MMFPlugin):
                        self.logger.warning(f"Entry point {entry_point.name} is not an MMFPlugin")
                        continue

                    # Get metadata
                    plugin_instance = plugin_class()
                    metadata = plugin_instance.metadata

                    plugins.append(
                        PluginInfo(
                            name=metadata.name,
                            version=metadata.version,
                            path=Path(entry_point.dist.location),
                            module_name=entry_point.module_name,
                            plugin_class=plugin_class,
                            metadata={
                                "description": metadata.description,
                                "author": metadata.author,
                                "dependencies": metadata.dependencies,
                                "tags": metadata.tags,
                            },
                        )
                    )

                except Exception as e:
                    self.logger.error(f"Error loading entry point {entry_point.name}: {e}")

        except Exception as e:
            self.logger.error(f"Error discovering plugins from entry points: {e}")

        return plugins

    async def _discover_from_packages(self) -> list[PluginInfo]:
        """Discover plugins from package naming convention.

        Returns:
            List of plugin info from packages
        """
        plugins = []

        try:

            # Find packages with the specified prefix
            for _importer, modname, _ispkg in pkgutil.iter_modules():
                if modname.startswith(self.package_prefix):
                    try:
                        # Import the package
                        module = importlib.import_module(modname)

                        # Look for plugin class
                        plugin_class = self._find_plugin_class_in_package(module)
                        if plugin_class:
                            # Get metadata
                            plugin_instance = plugin_class()
                            metadata = plugin_instance.metadata

                            plugins.append(
                                PluginInfo(
                                    name=metadata.name,
                                    version=metadata.version,
                                    path=Path(module.__file__).parent,
                                    module_name=modname,
                                    plugin_class=plugin_class,
                                    metadata={
                                        "description": metadata.description,
                                        "author": metadata.author,
                                        "dependencies": metadata.dependencies,
                                        "tags": metadata.tags,
                                    },
                                )
                            )

                    except Exception as e:
                        self.logger.error(f"Error loading package {modname}: {e}")

        except Exception as e:
            self.logger.error(f"Error discovering plugins from packages: {e}")

        return plugins

    def _find_plugin_class_in_package(self, module) -> type[MMFPlugin] | None:
        """Find plugin class in a package module.

        Args:
            module: Package module

        Returns:
            Plugin class or None if not found
        """
        # Check for 'plugin' attribute first (convention)
        if hasattr(module, "plugin"):
            plugin_attr = module.plugin
            if isinstance(plugin_attr, type) and issubclass(plugin_attr, MMFPlugin):
                return plugin_attr

        # Otherwise scan all attributes
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, MMFPlugin) and attr is not MMFPlugin:
                return attr

        return None


class CompositePluginDiscoverer(PluginDiscoverer):
    """Composite discoverer that combines multiple discovery strategies."""

    def __init__(self, discoverers: list[PluginDiscoverer]):
        """Initialize composite discoverer.

        Args:
            discoverers: List of plugin discoverers to combine
        """
        self.discoverers = discoverers
        self.logger = logging.getLogger("plugin.discovery.composite")

    async def discover(self) -> list[PluginInfo]:
        """Discover plugins using all configured discoverers.

        Returns:
            Combined list of discovered plugin information
        """
        all_plugins = []
        seen_plugins = set()

        for discoverer in self.discoverers:
            try:
                plugins = await discoverer.discover()

                for plugin in plugins:
                    # Deduplicate by name
                    if plugin.name not in seen_plugins:
                        all_plugins.append(plugin)
                        seen_plugins.add(plugin.name)
                    else:
                        self.logger.debug(f"Duplicate plugin {plugin.name} found, skipping")

            except Exception as e:
                self.logger.error(f"Error with discoverer {discoverer.__class__.__name__}: {e}")

        self.logger.info(f"Discovered {len(all_plugins)} unique plugins")
        return all_plugins
