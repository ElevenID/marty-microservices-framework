"""
Tests for Mesh Manager Service
"""

from unittest.mock import AsyncMock, Mock

import pytest

from mmf.application.services.mesh_manager import MeshManager
from mmf.core.security.domain.models.service_mesh import (
    PolicySyncResult,
    ServiceMeshPolicy,
)
from mmf.core.security.ports.service_mesh import IServiceMeshManager
from mmf.framework.mesh.ports.lifecycle import MeshLifecyclePort


@pytest.mark.asyncio
class TestMeshManager:
    @pytest.fixture
    def mock_lifecycle(self):
        return AsyncMock(spec=MeshLifecyclePort)

    @pytest.fixture
    def mock_security(self):
        return AsyncMock(spec=IServiceMeshManager)

    @pytest.fixture
    def mesh_manager(self, mock_lifecycle, mock_security):
        return MeshManager(
            lifecycle_port=mock_lifecycle,
            security_port=mock_security,
        )

    async def test_deploy_mesh_success(self, mesh_manager, mock_lifecycle):
        mock_lifecycle.verify_prerequisites.return_value = True
        mock_lifecycle.check_installation.return_value = True
        mock_lifecycle.deploy.return_value = True

        result = await mesh_manager.deploy_mesh(namespace="test-ns", config={"key": "val"})

        assert result is True
        mock_lifecycle.verify_prerequisites.assert_called_once()
        mock_lifecycle.check_installation.assert_called_once()
        mock_lifecycle.deploy.assert_called_once_with("test-ns", {"key": "val"})

    async def test_deploy_mesh_prerequisites_failed(self, mesh_manager, mock_lifecycle):
        mock_lifecycle.verify_prerequisites.return_value = False

        result = await mesh_manager.deploy_mesh()

        assert result is False
        mock_lifecycle.verify_prerequisites.assert_called_once()
        mock_lifecycle.check_installation.assert_not_called()
        mock_lifecycle.deploy.assert_not_called()

    async def test_deploy_mesh_installation_check_failed(self, mesh_manager, mock_lifecycle):
        mock_lifecycle.verify_prerequisites.return_value = True
        mock_lifecycle.check_installation.return_value = False

        result = await mesh_manager.deploy_mesh()

        assert result is False
        mock_lifecycle.verify_prerequisites.assert_called_once()
        mock_lifecycle.check_installation.assert_called_once()
        mock_lifecycle.deploy.assert_not_called()

    async def test_get_mesh_status(self, mesh_manager, mock_lifecycle):
        expected_status = {"status": "active"}
        mock_lifecycle.get_status.return_value = expected_status

        result = await mesh_manager.get_mesh_status()

        assert result == expected_status
        mock_lifecycle.get_status.assert_called_once()

    async def test_apply_security_policy(self, mesh_manager, mock_security):
        mock_policy = Mock(spec=ServiceMeshPolicy)
        mock_policy.name = "test-policy"
        mock_security.apply_policy.return_value = True

        result = await mesh_manager.apply_security_policy(mock_policy)

        assert result is True
        mock_security.apply_policy.assert_called_once_with(mock_policy)

    async def test_apply_security_policies(self, mesh_manager, mock_security):
        mock_policies = [Mock(spec=ServiceMeshPolicy), Mock(spec=ServiceMeshPolicy)]
        expected_result = Mock(spec=PolicySyncResult)
        mock_security.apply_policies.return_value = expected_result

        result = await mesh_manager.apply_security_policies(mock_policies)

        assert result == expected_result
        mock_security.apply_policies.assert_called_once_with(mock_policies)

    async def test_remove_security_policy(self, mesh_manager, mock_security):
        mock_security.remove_policy.return_value = True

        result = await mesh_manager.remove_security_policy("test-policy", "test-ns")

        assert result is True
        mock_security.remove_policy.assert_called_once_with("test-policy", "test-ns")
