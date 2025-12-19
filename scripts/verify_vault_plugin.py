"""
Verify Vault Plugin Loading

This script verifies that the PluginManager can discover and load the Vault plugin.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from mmf.application.services.plugin_manager import PluginManager
from mmf.core.plugins import PluginContext
from mmf.framework.infrastructure.plugins.discovery import PluginDiscovery
from mmf.framework.infrastructure.plugins.loader import PluginLoader
from mmf.framework.infrastructure.plugins.registry import PluginRegistry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_plugin")


async def verify_plugin_loading():
    """Verify that the Vault plugin can be loaded."""
    logger.info("Starting plugin verification...")

    # Initialize plugin system components
    registry = PluginRegistry()
    loader = PluginLoader()
    discovery = PluginDiscovery()

    # Create manager manually to inject dependencies if needed,
    # or use the service if it supports it.
    # For this test, we'll use the components directly to be explicit.

    plugin_dir = project_root / "platform_plugins"
    logger.info(f"Scanning for plugins in: {plugin_dir}")

    # 1. Discovery
    plugins = await discovery.discover([str(plugin_dir)])
    logger.info(f"Discovered plugins: {plugins}")

    # Check if the plugin file path is in the discovered plugins list
    expected_plugin_path = str(plugin_dir / "secrets.vault" / "plugin.py")
    if expected_plugin_path not in plugins:
        logger.error(
            f"❌ Failed to discover secrets.vault plugin. Expected: {expected_plugin_path}"
        )
        return False

    # 2. Loading
    plugin_path = str(plugin_dir / "secrets.vault" / "plugin.py")
    try:
        plugin = await loader.load("secrets.vault", plugin_path)
        logger.info(f"✅ Successfully loaded plugin: {plugin.get_metadata().name}")
    except Exception as e:
        logger.error(f"❌ Failed to load plugin: {e}")
        return False

    # 3. Registration
    registry.register("secrets.vault", plugin, plugin.get_metadata())

    # 4. Initialization
    context = PluginContext(
        plugin_id="secrets.vault",
        config={"vault": {"url": "http://mock-vault:8200", "token": "mock-token"}},
    )

    try:
        await plugin.initialize(context)
        logger.info("✅ Successfully initialized plugin")
    except Exception as e:
        # It might fail if it tries to connect to real Vault, which is expected
        logger.warning(f"⚠️ Initialization warning (expected if no Vault): {e}")

    return True


if __name__ == "__main__":
    success = asyncio.run(verify_plugin_loading())
    sys.exit(0 if success else 1)
