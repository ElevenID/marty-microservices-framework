from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mmf.services.identity.infrastructure.adapters.out.config.config_integration import (
    BasicAuthConfig,
    ConfigurationError,
    IdentityConfigurationManager,
    JWTConfig,
)


class TestIdentityConfigurationManager:
    @pytest.fixture
    def mock_mmf_config(self):
        with patch(
            "mmf.services.identity.infrastructure.adapters.out.config.config_integration.MMFConfiguration"
        ) as mock:
            config_instance = MagicMock()
            mock.load.return_value = config_instance
            yield config_instance

    @pytest.fixture
    def manager(self, mock_mmf_config):
        # We need to mock Path to ensure it finds a "config" directory
        with patch(
            "mmf.services.identity.infrastructure.adapters.out.config.config_integration.Path"
        ) as mock_path:
            # Setup path structure to simulate finding config dir
            mock_file_path = MagicMock()
            mock_path.return_value = mock_file_path
            mock_file_path.parent = mock_file_path

            # Make parents return a list with one parent that has the config dir
            parent = MagicMock()
            mock_file_path.parents = [parent]

            config_path = MagicMock()
            parent.__truediv__.return_value = config_path  # parent / "mmf"
            config_path.__truediv__.return_value = config_path  # ... / "config"
            config_path.exists.return_value = True
            config_path.is_dir.return_value = True

            return IdentityConfigurationManager()

    def test_init(self, mock_mmf_config):
        # This test is implicitly covered by the fixture, but we can verify calls
        with patch(
            "mmf.services.identity.infrastructure.adapters.out.config.config_integration.Path"
        ) as mock_path:
            # Setup path structure to simulate finding config dir
            mock_file_path = MagicMock()
            mock_path.return_value = mock_file_path
            mock_file_path.parent = mock_file_path

            parent = MagicMock()
            mock_file_path.parents = [parent]

            config_path = MagicMock()
            parent.__truediv__.return_value = config_path
            config_path.__truediv__.return_value = config_path
            config_path.exists.return_value = True
            config_path.is_dir.return_value = True

            IdentityConfigurationManager(service_name="test-service", environment="test-env")

            # Verify MMFConfiguration.load was called
            from mmf.services.identity.infrastructure.adapters.out.config.config_integration import (
                MMFConfiguration,
            )

            MMFConfiguration.load.assert_called_with(
                config_dir=config_path, environment="test-env", service_name="test-service"
            )

    def test_get_jwt_config_success(self, manager, mock_mmf_config):
        mock_mmf_config.get.side_effect = lambda key, default=None: {
            "security.authentication.jwt": {
                "secret": "test-secret",  # pragma: allowlist secret
                "algorithm": "HS256",
                "expiration_minutes": 30,
                "issuer": "test-issuer",
                "audience": "test-audience",
            }
        }.get(key, default)

        jwt_config = manager.get_jwt_config()

        assert isinstance(jwt_config, JWTConfig)
        assert jwt_config.secret_key == "test-secret"  # pragma: allowlist secret
        assert jwt_config.algorithm == "HS256"
        assert jwt_config.access_token_expire_minutes == 30
        assert jwt_config.issuer == "test-issuer"
        assert jwt_config.audience == "test-audience"

    def test_get_jwt_config_missing_secret(self, manager, mock_mmf_config):
        mock_mmf_config.get.return_value = {}  # Empty config

        with pytest.raises(ConfigurationError, match="JWT secret is required"):
            manager.get_jwt_config()

    def test_get_basic_auth_config(self, manager, mock_mmf_config):
        mock_mmf_config.get.side_effect = lambda key, default=None: {
            "security.authentication.basic": {
                "password_min_length": 10,
                "password_require_uppercase": True,
                "password_require_lowercase": True,
                "password_require_digits": True,
                "password_require_special": True,
                "bcrypt_rounds": 14,
                "enable_user_registration": True,
            }
        }.get(key, default)

        basic_config = manager.get_basic_auth_config()

        assert isinstance(basic_config, BasicAuthConfig)
        assert basic_config.password_min_length == 10
        assert basic_config.password_require_uppercase is True
        assert basic_config.password_require_special is True
        assert basic_config.bcrypt_rounds == 14
        assert basic_config.enable_user_registration is True
