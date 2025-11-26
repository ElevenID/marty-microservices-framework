"""
Unit tests for framework configuration management.

Tests the FrameworkConfig class and configuration loading/validation
without external dependencies.
"""

import os
from unittest.mock import mock_open, patch

import pytest

from marty_msf.framework.config import BaseServiceConfig, FrameworkConfig


@pytest.mark.unit
class TestFrameworkConfig:
    """Test suite for BaseServiceConfig."""

    def test_config_creation_with_defaults(self):
        """Test configuration creation with default values."""
        config = BaseServiceConfig()

        assert hasattr(config, "service_name")
        # Check for actual properties that exist in BaseServiceConfig

    def test_config_creation_with_custom_values(self):
        """Test configuration creation with custom values."""
        config = FrameworkConfig(
            service_name="test-service",
            environment="test",
            debug=True,
            log_level="DEBUG",
            port=9000,
        )

        assert config.service_name == "test-service"
        assert config.environment == "test"
        assert config.debug is True
        assert config.log_level == "DEBUG"
        assert config.port == 9000

    def test_config_from_dict(self):
        """Test configuration creation from dictionary."""
        config_dict = {
            "service_name": "dict-service",
            "environment": "production",
            "debug": False,
            "log_level": "WARNING",
            "port": 8443,
        }

        config = FrameworkConfig.from_dict(config_dict)

        assert config.service_name == "dict-service"
        assert config.environment == "production"
        assert config.debug is False
        assert config.log_level == "WARNING"
        assert config.port == 8443

    def test_config_from_dict_partial(self):
        """Test configuration from dictionary with partial values."""
        config_dict = {"service_name": "partial-service", "debug": True}

        config = FrameworkConfig.from_dict(config_dict)

        # Provided values
        assert config.service_name == "partial-service"
        assert config.debug is True

        # Default values for missing keys
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert config.port == 8080

    @patch.dict(
        os.environ,
        {
            "SERVICE_NAME": "env-service",
            "ENVIRONMENT": "staging",
            "DEBUG": "true",
            "LOG_LEVEL": "ERROR",
            "PORT": "8081",
        },
    )
    def test_config_from_environment(self):
        """Test configuration loading from environment variables."""
        config = FrameworkConfig.from_environment()

        assert config.service_name == "env-service"
        assert config.environment == "staging"
        assert config.debug is True
        assert config.log_level == "ERROR"
        assert config.port == 8081

    @patch.dict(os.environ, {"SERVICE_NAME": "env-service", "DEBUG": "false", "PORT": "invalid"})
    def test_config_from_environment_with_invalid_values(self):
        """Test configuration handling of invalid environment values."""
        config = FrameworkConfig.from_environment()

        assert config.service_name == "env-service"
        assert config.debug is False
        # Port should fall back to default due to invalid value
        assert config.port == 8080

    def test_config_validation_valid(self):
        """Test configuration validation with valid values."""
        config = FrameworkConfig(service_name="valid-service", environment="production", port=8080)

        # Should not raise any exceptions
        config.validate()

    def test_config_validation_invalid_service_name(self):
        """Test configuration validation with invalid service name."""
        with pytest.raises(ValueError, match="Service name cannot be empty"):
            FrameworkConfig(service_name="").validate()

    def test_config_validation_invalid_port(self):
        """Test configuration validation with invalid port."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            FrameworkConfig(port=0).validate()

        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            FrameworkConfig(port=70000).validate()

    def test_config_validation_invalid_log_level(self):
        """Test configuration validation with invalid log level."""
        with pytest.raises(ValueError, match="Invalid log level"):
            FrameworkConfig(log_level="INVALID").validate()

    def test_config_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = FrameworkConfig(
            service_name="serialize-service",
            environment="test",
            debug=True,
            log_level="DEBUG",
            port=9000,
        )

        config_dict = config.to_dict()

        expected = {
            "service_name": "serialize-service",
            "environment": "test",
            "debug": True,
            "log_level": "DEBUG",
            "port": 9000,
        }

        assert config_dict == expected

    def test_config_update(self):
        """Test configuration update with new values."""
        config = FrameworkConfig(service_name="original")

        config.update({"service_name": "updated", "debug": True, "port": 9000})

        assert config.service_name == "updated"
        assert config.debug is True
        assert config.port == 9000

    def test_config_merge(self):
        """Test configuration merging with another config."""
        config1 = FrameworkConfig(service_name="service1", debug=True)

        config2 = FrameworkConfig(service_name="service2", environment="production", port=9000)

        merged = config1.merge(config2)

        # config2 values should override config1
        assert merged.service_name == "service2"
        assert merged.environment == "production"
        assert merged.port == 9000
        assert merged.debug is True  # From config1, not overridden

    @patch("builtins.open", mock_open(read_data='{"service_name": "file-service", "debug": true}'))
    def test_config_from_file_json(self, temp_dir):
        """Test configuration loading from JSON file."""
        config_file = temp_dir / "config.json"

        config = FrameworkConfig.from_file(str(config_file))

        assert config.service_name == "file-service"
        assert config.debug is True

    @patch("builtins.open", mock_open(read_data="service_name: yaml-service\ndebug: true"))
    def test_config_from_file_yaml(self, temp_dir):
        """Test configuration loading from YAML file."""
        config_file = temp_dir / "config.yaml"

        with patch("yaml.safe_load") as mock_yaml:
            mock_yaml.return_value = {"service_name": "yaml-service", "debug": True}

            config = FrameworkConfig.from_file(str(config_file))

            assert config.service_name == "yaml-service"
            assert config.debug is True

    def test_config_equality(self):
        """Test configuration equality comparison."""
        config1 = FrameworkConfig(service_name="test", debug=True)
        config2 = FrameworkConfig(service_name="test", debug=True)
        config3 = FrameworkConfig(service_name="different", debug=True)

        assert config1 == config2
        assert config1 != config3

    def test_config_repr(self):
        """Test configuration string representation."""
        config = FrameworkConfig(service_name="test-service")
        repr_str = repr(config)

        assert "FrameworkConfig" in repr_str
        assert "test-service" in repr_str

    def test_config_contains_sensitive_data_handling(self):
        """Test that sensitive configuration data is handled properly."""
        config = FrameworkConfig(database_password="secret123", api_key="key456")

        # Ensure sensitive data is not exposed in string representation
        repr_str = repr(config)
        assert "secret123" not in repr_str
        assert "key456" not in repr_str
        assert "***" in repr_str or "[REDACTED]" in repr_str

    def test_config_immutability_after_validation(self):
        """Test that configuration becomes immutable after validation."""
        config = FrameworkConfig(service_name="test")
        config.validate()

        # Depending on implementation, this might raise an exception
        # or simply be ignored
        with pytest.raises((AttributeError, ValueError)):
            config.service_name = "changed"

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("", False),
            ("invalid", False),
        ],
    )
    def test_boolean_environment_parsing(self, env_value, expected):
        """Test boolean parsing from environment variables."""
        with patch.dict(os.environ, {"DEBUG": env_value}):
            config = FrameworkConfig.from_environment()
            assert config.debug == expected


@pytest.mark.unit
class TestConfigurationLoader:
    """Test suite for configuration loading utilities."""

    def test_load_config_precedence(self):
        """Test configuration loading precedence: CLI > ENV > FILE > DEFAULTS."""
        # This test would verify that configuration sources are applied
        # in the correct order of precedence
        pass

    def test_config_schema_validation(self):
        """Test configuration schema validation."""
        # This test would verify that configuration matches expected schema
        pass

    def test_config_hot_reload(self):
        """Test configuration hot reloading capabilities."""
        # This test would verify that configuration can be reloaded at runtime
        pass
