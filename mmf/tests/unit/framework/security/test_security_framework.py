from unittest.mock import MagicMock, Mock, patch

import pytest

from mmf.core.security.domain.config import SecurityConfig
from mmf.framework.security.adapters.security_framework import (
    SecurityHardeningFramework,
)


class TestSecurityHardeningFramework:
    @pytest.fixture
    def mock_config(self):
        config = Mock(spec=SecurityConfig)
        config.service_mesh_config = Mock()
        config.enable_threat_detection = True
        return config

    @pytest.fixture
    def mock_register_instance(self):
        with patch("mmf.framework.security.adapters.security_framework.register_instance") as mock:
            yield mock

    @pytest.fixture
    def mock_factories(self):
        with (
            patch(
                "mmf.framework.security.adapters.security_framework.AuthenticationFactory"
            ) as auth,
            patch(
                "mmf.framework.security.adapters.security_framework.AuthorizationFactory"
            ) as authz,
            patch("mmf.framework.security.adapters.security_framework.AuditFactory") as audit,
            patch("mmf.framework.security.adapters.security_framework.SecretsFactory") as secrets,
            patch("mmf.framework.security.adapters.security_framework.ServiceMeshFactory") as mesh,
            patch(
                "mmf.framework.security.adapters.security_framework.ThreatDetectionFactory"
            ) as threat,
        ):
            # Setup default returns
            auth.create_registrations.return_value = []
            authz.create_registrations.return_value = []
            audit.create_registrations.return_value = []
            secrets.create_registrations.return_value = []
            mesh.create_manager.return_value = Mock()
            threat.create_registrations.return_value = []

            yield {
                "auth": auth,
                "authz": authz,
                "audit": audit,
                "secrets": secrets,
                "mesh": mesh,
                "threat": threat,
            }

    def test_initialization(self, mock_config, mock_register_instance, mock_factories):
        framework = SecurityHardeningFramework(mock_config)
        framework.initialize()

        # Verify all factories were called
        mock_factories["auth"].create_registrations.assert_called_once()
        mock_factories["authz"].create_registrations.assert_called_once()
        mock_factories["audit"].create_registrations.assert_called_once()
        mock_factories["secrets"].create_registrations.assert_called_once_with(mock_config)
        mock_factories["mesh"].create_manager.assert_called_once_with(
            mock_config.service_mesh_config
        )
        mock_factories["threat"].create_registrations.assert_called_once_with(mock_config)

    def test_idempotent_initialization(self, mock_config, mock_factories):
        framework = SecurityHardeningFramework(mock_config)
        framework.initialize()
        framework.initialize()

        # Factories should still only be called once
        mock_factories["auth"].create_registrations.assert_called_once()

    def test_registration(self, mock_config, mock_register_instance, mock_factories):
        # Setup a mock registration entry
        mock_entry = Mock()
        mock_entry.interface = "ISomeInterface"
        mock_entry.instance = "SomeInstance"

        mock_factories["auth"].create_registrations.return_value = [mock_entry]

        framework = SecurityHardeningFramework(mock_config)
        framework.initialize()

        mock_register_instance.assert_any_call("ISomeInterface", "SomeInstance")
