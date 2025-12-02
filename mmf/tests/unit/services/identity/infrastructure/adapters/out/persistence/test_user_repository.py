"""Unit tests for AuthenticatedUserRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mmf.services.identity.domain.models.authenticated_user import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters.out.persistence.user_repository import (
    AuthenticatedUserRepository,
)


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    manager = MagicMock()
    manager.get_transaction = MagicMock(return_value=AsyncMock())
    return manager


@pytest.fixture
def repository(mock_db_manager):
    """Create a repository instance with mocked dependencies."""
    return AuthenticatedUserRepository(mock_db_manager)


@pytest.fixture
def sample_user():
    """Create a sample authenticated user for testing."""
    return AuthenticatedUser(
        user_id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        roles={"user"},
        permissions={"read"},
        auth_method="password",
        created_at=datetime.now(timezone.utc),
    )


class TestAuthenticatedUserRepository:
    """Tests for the AuthenticatedUserRepository class."""

    @pytest.mark.asyncio
    async def test_init(self, mock_db_manager):
        """Test repository initialization."""
        repo = AuthenticatedUserRepository(mock_db_manager)
        assert repo.db_manager is mock_db_manager

    @pytest.mark.asyncio
    async def test_save_returns_entity(self, repository, sample_user):
        """Test that save returns the entity."""
        # Setup mock transaction context manager
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=None)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        repository.db_manager.get_transaction.return_value = mock_context

        result = await repository.save(sample_user)

        assert result is sample_user
        repository.db_manager.get_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none(self, repository):
        """Test find_by_id returns None (placeholder implementation)."""
        user_id = uuid4()
        result = await repository.find_by_id(user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_find_all_returns_empty_list(self, repository):
        """Test find_all returns empty list (placeholder implementation)."""
        result = await repository.find_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_find_all_with_pagination(self, repository):
        """Test find_all accepts pagination parameters."""
        result = await repository.find_all(skip=10, limit=50)
        assert result == []

    @pytest.mark.asyncio
    async def test_update_returns_none(self, repository):
        """Test update returns None (placeholder implementation)."""
        user_id = uuid4()
        updates = {"username": "newname"}
        result = await repository.update(user_id, updates)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_returns_false(self, repository):
        """Test delete returns False (placeholder implementation)."""
        user_id = uuid4()
        result = await repository.delete(user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, repository):
        """Test exists returns False (placeholder implementation)."""
        user_id = uuid4()
        result = await repository.exists(user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_count_returns_zero(self, repository):
        """Test count returns 0 (placeholder implementation)."""
        result = await repository.count()
        assert result == 0

    @pytest.mark.asyncio
    async def test_find_by_username_returns_none(self, repository):
        """Test find_by_username returns None (placeholder implementation)."""
        result = await repository.find_by_username("testuser")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_session_id_returns_none(self, repository):
        """Test find_by_session_id returns None (placeholder implementation)."""
        result = await repository.find_by_session_id("session123")
        assert result is None


class TestAuthenticatedUserRepositoryInterface:
    """Tests to verify the repository implements the expected interface."""

    def test_implements_repository_interface(self, repository):
        """Test that all expected methods exist."""
        assert hasattr(repository, "save")
        assert hasattr(repository, "find_by_id")
        assert hasattr(repository, "find_all")
        assert hasattr(repository, "update")
        assert hasattr(repository, "delete")
        assert hasattr(repository, "exists")
        assert hasattr(repository, "count")
        assert hasattr(repository, "find_by_username")
        assert hasattr(repository, "find_by_session_id")

    def test_methods_are_async(self, repository):
        """Test that all main methods are coroutines."""
        import asyncio

        assert asyncio.iscoroutinefunction(repository.save)
        assert asyncio.iscoroutinefunction(repository.find_by_id)
        assert asyncio.iscoroutinefunction(repository.find_all)
        assert asyncio.iscoroutinefunction(repository.update)
        assert asyncio.iscoroutinefunction(repository.delete)
        assert asyncio.iscoroutinefunction(repository.exists)
        assert asyncio.iscoroutinefunction(repository.count)
        assert asyncio.iscoroutinefunction(repository.find_by_username)
        assert asyncio.iscoroutinefunction(repository.find_by_session_id)
