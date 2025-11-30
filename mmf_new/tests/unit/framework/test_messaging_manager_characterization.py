from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf_new.framework.messaging.application.manager import MessagingManager
from mmf_new.framework.messaging.domain.models import (
    BackendConfig,
    BackendType,
    Message,
    MessagingConfig,
)
from mmf_new.framework.messaging.domain.ports import IMessageBackend


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagingManagerCharacterization:
    """
    Characterization tests for MessagingManager to pin behavior before refactoring.
    Focuses on internal component orchestration.
    """

    async def test_initialization_orchestration(self):
        """Verify that initialization sets up Router and DLQ Manager correctly."""
        # Arrange
        mock_backend = AsyncMock(spec=IMessageBackend)
        config = MessagingConfig(
            backend=BackendConfig(type=BackendType.MEMORY, connection_url="memory://")
        )
        manager = MessagingManager(config, mock_backend)

        # Act
        await manager.initialize()

        # Assert
        mock_backend.connect.assert_called_once()
        assert manager.router is not None
        assert manager.dlq_manager is not None
        assert manager._initialized is True

    async def test_double_initialization_guard(self):
        """Verify that calling initialize twice does not re-initialize components."""
        # Arrange
        mock_backend = AsyncMock(spec=IMessageBackend)
        config = MessagingConfig(
            backend=BackendConfig(type=BackendType.MEMORY, connection_url="memory://")
        )
        manager = MessagingManager(config, mock_backend)
        await manager.initialize()

        # Reset mock to check for subsequent calls
        mock_backend.connect.reset_mock()

        # Act
        await manager.initialize()

        # Assert
        mock_backend.connect.assert_not_called()

    async def test_shutdown_orchestration(self):
        """Verify that shutdown closes backend and clears state."""
        # Arrange
        mock_backend = AsyncMock(spec=IMessageBackend)
        config = MessagingConfig(
            backend=BackendConfig(type=BackendType.MEMORY, connection_url="memory://")
        )
        manager = MessagingManager(config, mock_backend)
        await manager.initialize()

        # Act
        await manager.shutdown()

        # Assert
        mock_backend.disconnect.assert_called_once()
        assert manager._initialized is False
