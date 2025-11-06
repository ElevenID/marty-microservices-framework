"""Unit tests for authentication use cases."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from mmf_new.services.identity.application.ports_in import AuthenticatePrincipal
from mmf_new.services.identity.application.ports_out import EventBus, UserRepository
from mmf_new.services.identity.application.usecases import AuthenticatePrincipalUseCase
from mmf_new.services.identity.domain.models import (
    AuthenticationResult,
    AuthenticationStatus,
    Credentials,
    Principal,
    UserId,
)


class TestAuthenticatePrincipalUseCase:
    """Tests for the authenticate principal use case."""

    def test_successful_authentication(self):
        """Test successful authentication flow."""
        # Arrange
        user_id = UserId("user123")
        credentials = Credentials("testuser", "password123")

        mock_repository = Mock(spec=UserRepository)
        mock_repository.find_by_username.return_value = user_id
        mock_repository.verify_credentials.return_value = True

        mock_event_bus = Mock(spec=EventBus)

        use_case = AuthenticatePrincipalUseCase(mock_repository, mock_event_bus)

        # Act
        result = use_case.execute(credentials)

        # Assert
        assert result.status == AuthenticationStatus.SUCCESS
        assert result.principal is not None
        assert result.principal.user_id == user_id
        assert result.principal.username == "testuser"
        assert result.error_message is None

        # Verify repository calls
        mock_repository.find_by_username.assert_called_once_with("testuser")
        mock_repository.verify_credentials.assert_called_once_with(credentials)

        # Verify event published
        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event["event_type"] == "user_authenticated"
        assert published_event["user_id"] == "user123"

    def test_user_not_found(self):
        """Test authentication when user is not found."""
        # Arrange
        credentials = Credentials("nonexistent", "password123")

        mock_repository = Mock(spec=UserRepository)
        mock_repository.find_by_username.return_value = None

        mock_event_bus = Mock(spec=EventBus)

        use_case = AuthenticatePrincipalUseCase(mock_repository, mock_event_bus)

        # Act
        result = use_case.execute(credentials)

        # Assert
        assert result.status == AuthenticationStatus.FAILED
        assert result.principal is None
        assert result.error_message == "User not found"

        # Verify repository calls
        mock_repository.find_by_username.assert_called_once_with("nonexistent")
        mock_repository.verify_credentials.assert_not_called()

        # Verify no event published
        mock_event_bus.publish.assert_not_called()

    def test_invalid_credentials(self):
        """Test authentication with invalid credentials."""
        # Arrange
        user_id = UserId("user123")
        credentials = Credentials("testuser", "wrongpassword")

        mock_repository = Mock(spec=UserRepository)
        mock_repository.find_by_username.return_value = user_id
        mock_repository.verify_credentials.return_value = False

        mock_event_bus = Mock(spec=EventBus)

        use_case = AuthenticatePrincipalUseCase(mock_repository, mock_event_bus)

        # Act
        result = use_case.execute(credentials)

        # Assert
        assert result.status == AuthenticationStatus.FAILED
        assert result.principal is None
        assert result.error_message == "Invalid credentials"

        # Verify repository calls
        mock_repository.find_by_username.assert_called_once_with("testuser")
        mock_repository.verify_credentials.assert_called_once_with(credentials)

        # Verify no event published
        mock_event_bus.publish.assert_not_called()

    def test_principal_expiration_set(self):
        """Test that created principal has proper expiration."""
        # Arrange
        user_id = UserId("user123")
        credentials = Credentials("testuser", "password123")

        mock_repository = Mock(spec=UserRepository)
        mock_repository.find_by_username.return_value = user_id
        mock_repository.verify_credentials.return_value = True

        mock_event_bus = Mock(spec=EventBus)

        use_case = AuthenticatePrincipalUseCase(mock_repository, mock_event_bus)

        # Act
        before_auth = datetime.utcnow()
        result = use_case.execute(credentials)
        after_auth = datetime.utcnow()

        # Assert
        assert result.status == AuthenticationStatus.SUCCESS
        principal = result.principal
        assert principal is not None

        # Check that authentication time is reasonable
        assert before_auth <= principal.authenticated_at <= after_auth

        # Check that expiration is set to 24 hours from authentication
        expected_expiry_min = principal.authenticated_at + timedelta(hours=24, minutes=-1)
        expected_expiry_max = principal.authenticated_at + timedelta(hours=24, minutes=1)
        assert expected_expiry_min <= principal.expires_at <= expected_expiry_max
