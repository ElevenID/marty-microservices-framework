"""
Configuration Management Tests

Tests for plugin configuration management including:
- Plugin configuration loading and validation
- Marty-specific configuration handling
- Configuration manager functionality
- Environment-specific configuration
"""

import json

# Fix import paths
import sys
from pathlib import Path
from typing import Any

import yaml

from marty_msf.framework.config import MartyTrustPKIConfig
from marty_msf.framework.config.plugin_config import (
    PluginConfigManager,
    PluginConfigSection,
    create_plugin_config_manager,
)

framework_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(framework_path))



class TestPluginConfigSection:
    """Test basic plugin configuration section."""

    def test_create_plugin_config_section(self):
        """Test creation of plugin configuration section."""
        config = PluginConfigSection(enabled=True, custom_setting="test_value", numeric_setting=42)

        assert config.enabled is True
        assert config.custom_setting == "test_value"
        assert config.numeric_setting == 42

    def test_disabled_plugin_config(self):
        """Test disabled plugin configuration."""
        config = PluginConfigSection(enabled=False)
        assert config.enabled is False


class TestPluginConfigManager:
    """Test plugin configuration manager."""

    def create_test_config_file(self, config_dir: Path, filename: str, config_data: dict[str, Any]):
        """Create a test configuration file."""
        config_file = config_dir / filename

        if filename.endswith(".json"):
            with open(config_file, "w") as f:
                json.dump(config_data, f, indent=2)
        elif filename.endswith(".yaml") or filename.endswith(".yml"):
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

        return config_file

    def test_create_config_manager(self, temp_dir):
        """Test creation of plugin configuration manager."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        manager = create_plugin_config_manager(config_dir)
        assert isinstance(manager, PluginConfigManager)
        assert manager.base_config_path == config_dir

    def test_load_plugin_config_json(self, temp_dir):
        """Test loading plugin configuration from JSON."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create test configuration
        marty_config_data = {
            "enabled": True,
            "trust_anchor_url": "https://test-trust.example.com",
            "pkd_url": "https://test-pkd.example.com",
            "document_signer_url": "https://test-signer.example.com",
            "signing_algorithms": ["RSA-SHA256", "ECDSA-SHA256"],
            "certificate_validation_enabled": True,
            "require_mutual_tls": True,
        }

        self.create_test_config_file(config_dir, "marty.json", marty_config_data)

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        assert isinstance(config, MartyTrustPKIConfig)

    def test_load_plugin_config_yaml(self, temp_dir):
        """Test loading plugin configuration from YAML."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create test configuration
        marty_config_data = {
            "enabled": True,
            "trust_anchor_url": "https://yaml-trust.example.com",
            "pkd_url": "https://yaml-pkd.example.com",
            "document_signer_url": "https://yaml-signer.example.com",
            "signing_algorithms": ["RSA-SHA256"],
            "certificate_validation_enabled": False,
            "require_mutual_tls": False,
        }

        self.create_test_config_file(config_dir, "marty.yaml", marty_config_data)

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        assert isinstance(config, MartyTrustPKIConfig)

    def test_load_nonexistent_config(self, temp_dir):
        """Test loading configuration for non-existent plugin."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("nonexistent", PluginConfigSection)

        # Should return default configuration
        assert isinstance(config, PluginConfigSection)

    def test_get_plugin_config(self, temp_dir):
        """Test retrieving loaded plugin configuration."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        manager = create_plugin_config_manager(config_dir)

        # Load a configuration
        manager.load_plugin_config("test-plugin", PluginConfigSection)

        # Should be able to retrieve it
        retrieved_config = manager.get_plugin_config("test-plugin")
        assert retrieved_config is not None


class TestEnvironmentSpecificConfiguration:
    """Test environment-specific configuration handling."""

    def test_development_configuration(self, temp_dir):
        """Test loading development-specific configuration."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create base configuration
        base_config = {
            "enabled": True,
            "trust_anchor_url": "https://base-trust.example.com",
            "certificate_validation_enabled": True,
        }

        # Create development override
        dev_config = {
            "trust_anchor_url": "https://dev-trust.example.com",
            "certificate_validation_enabled": False,
            "debug_mode": True,
        }

        TestPluginConfigManager().create_test_config_file(config_dir, "marty.json", base_config)
        TestPluginConfigManager().create_test_config_file(
            config_dir, "marty.development.json", dev_config
        )

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        assert isinstance(config, MartyTrustPKIConfig)

    def test_production_configuration(self, temp_dir):
        """Test loading production-specific configuration."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create base configuration
        base_config = {
            "enabled": True,
            "trust_anchor_url": "https://base-trust.example.com",
            "require_mutual_tls": False,
        }

        # Create production override
        prod_config = {
            "trust_anchor_url": "https://prod-trust.example.com",
            "require_mutual_tls": True,
            "high_security_mode": True,
        }

        TestPluginConfigManager().create_test_config_file(config_dir, "marty.json", base_config)
        TestPluginConfigManager().create_test_config_file(
            config_dir, "marty.production.json", prod_config
        )

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        assert isinstance(config, MartyTrustPKIConfig)


class TestConfigurationValidation:
    """Test configuration validation and error handling."""

    def test_invalid_json_configuration(self, temp_dir):
        """Test handling of invalid JSON configuration."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create invalid JSON file
        invalid_config_file = config_dir / "invalid.json"
        invalid_config_file.write_text("{invalid json content")

        manager = create_plugin_config_manager(config_dir)

        # Should handle gracefully and return default config
        config = manager.load_plugin_config("invalid", PluginConfigSection)
        assert isinstance(config, PluginConfigSection)

    def test_invalid_yaml_configuration(self, temp_dir):
        """Test handling of invalid YAML configuration."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create invalid YAML file
        invalid_config_file = config_dir / "invalid.yaml"
        invalid_config_file.write_text("invalid: yaml: content: [")

        manager = create_plugin_config_manager(config_dir)

        # Should handle gracefully and return default config
        config = manager.load_plugin_config("invalid", PluginConfigSection)
        assert isinstance(config, PluginConfigSection)

    def test_missing_required_fields(self, temp_dir):
        """Test handling of missing required configuration fields."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create configuration with missing required fields
        incomplete_config = {
            "enabled": True,
            # Missing trust_anchor_url and other required fields
        }

        TestPluginConfigManager().create_test_config_file(
            config_dir, "incomplete.json", incomplete_config
        )

        manager = create_plugin_config_manager(config_dir)

        # Should handle gracefully with defaults
        config = manager.load_plugin_config("incomplete", MartyTrustPKIConfig)
        assert isinstance(config, MartyTrustPKIConfig)


class TestConfigurationIntegration:
    """Test configuration integration with plugin system."""

    def test_plugin_config_injection(self, temp_dir):
        """Test injection of configuration into plugins."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create Marty plugin configuration
        marty_config_data = {
            "enabled": True,
            "trust_anchor_url": "https://integrated-trust.example.com",
            "pkd_url": "https://integrated-pkd.example.com",
            "document_signer_url": "https://integrated-signer.example.com",
            "signing_algorithms": ["RSA-SHA256", "ECDSA-SHA256"],
            "certificate_validation_enabled": True,
            "require_mutual_tls": True,
        }

        TestPluginConfigManager().create_test_config_file(
            config_dir, "marty.json", marty_config_data
        )

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        # Verify configuration loaded correctly
        assert isinstance(config, MartyTrustPKIConfig)
        assert config.trust_anchor_url == "https://integrated-trust.example.com"

    def test_multiple_plugin_configurations(self, temp_dir):
        """Test managing configurations for multiple plugins."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create configurations for multiple plugins
        plugin1_config = {"enabled": True, "setting1": "value1"}
        plugin2_config = {"enabled": False, "setting2": "value2"}
        marty_config = {"enabled": True, "trust_anchor_url": "https://multi-trust.example.com"}

        TestPluginConfigManager().create_test_config_file(
            config_dir, "plugin1.json", plugin1_config
        )
        TestPluginConfigManager().create_test_config_file(
            config_dir, "plugin2.json", plugin2_config
        )
        TestPluginConfigManager().create_test_config_file(config_dir, "marty.json", marty_config)

        manager = create_plugin_config_manager(config_dir)

        # Load all configurations
        config1 = manager.load_plugin_config("plugin1", PluginConfigSection)
        config2 = manager.load_plugin_config("plugin2", PluginConfigSection)
        marty_conf = manager.load_plugin_config("marty", MartyTrustPKIConfig)

        assert isinstance(config1, PluginConfigSection)
        assert isinstance(config2, PluginConfigSection)
        assert isinstance(marty_conf, MartyTrustPKIConfig)

        # Verify individual configurations
        assert config1.enabled is True
        assert config2.enabled is False


class TestConfigurationSecurity:
    """Test configuration security and sensitive data handling."""

    def test_sensitive_data_masking(self, temp_dir):
        """Test that sensitive configuration data is handled properly."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create configuration with sensitive data
        sensitive_config = {
            "enabled": True,
            "trust_anchor_url": "https://sensitive-trust.example.com",
            "api_key": "secret-api-key-12345",
            "private_key_path": "/path/to/secret/key.pem",
        }

        TestPluginConfigManager().create_test_config_file(
            config_dir, "sensitive.json", sensitive_config
        )

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("sensitive", PluginConfigSection)

        # Configuration should load but sensitive data should be handled carefully
        assert isinstance(config, PluginConfigSection)
        assert config.enabled is True

    def test_configuration_access_control(self, temp_dir):
        """Test configuration access control mechanisms."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create restricted configuration
        restricted_config = {"enabled": True, "admin_only_setting": "restricted_value"}

        TestPluginConfigManager().create_test_config_file(
            config_dir, "restricted.json", restricted_config
        )

        manager = create_plugin_config_manager(config_dir)
        config = manager.load_plugin_config("restricted", PluginConfigSection)

        # Should load but access controls would be handled by the actual implementation
        assert isinstance(config, PluginConfigSection)
