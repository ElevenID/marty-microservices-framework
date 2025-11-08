"""Integration tests for the identity service."""

from datetime import datetime, timedelta

from mmf_new.services.identity.application.usecases import AuthenticatePrincipalUseCase
from mmf_new.services.identity.domain.models import (
    AuthenticationStatus,
    Credentials,
    UserId,
)
from mmf_new.services.identity.infrastructure.adapters import (
    InMemoryEventBus,
    InMemoryUserRepository,
)


class TestIdentityServiceIntegration:
    """Integration tests for the complete identity service flow."""

    def test_complete_authentication_flow(self):
        """Test the complete authentication flow from adapter to domain."""
        # Arrange - Set up infrastructure
        user_repository = InMemoryUserRepository()
        event_bus = InMemoryEventBus()

        # Add a test user
        test_user_id = user_repository.add_user("integration_user", "test_password")

        # Set up use case
        authentication_usecase = AuthenticatePrincipalUseCase(
            user_repository, event_bus
        )

        # Act - Execute authentication
        credentials = Credentials("integration_user", "test_password")
        result = authentication_usecase.execute(credentials)

        # Assert - Verify successful authentication
        assert result.status == AuthenticationStatus.SUCCESS
        assert result.authenticated_user is not None
        assert result.authenticated_user.user_id == test_user_id.value
        assert result.authenticated_user.username == "integration_user"
        assert result.error_message is None

        # Verify authenticated_user has reasonable expiration
        now = datetime.utcnow()
        expected_expiry = now + timedelta(hours=24)
        assert result.authenticated_user.expires_at is not None
        time_diff = abs(
            (result.authenticated_user.expires_at - expected_expiry).total_seconds()
        )
        assert time_diff < 60  # Within 1 minute

        # Verify event was published
        events = event_bus.get_published_events()
        assert len(events) == 1

        event = events[0]
        assert event["event_type"] == "user_authenticated"
        assert event["user_id"] == test_user_id.value
        assert "timestamp" in event

    def test_authentication_with_unknown_user(self):
        """Test authentication flow with unknown user."""
        # Arrange
        user_repository = InMemoryUserRepository()
        event_bus = InMemoryEventBus()
        authentication_usecase = AuthenticatePrincipalUseCase(
            user_repository, event_bus
        )

        # Act
        credentials = Credentials("unknown_user", "any_password")
        result = authentication_usecase.execute(credentials)

        # Assert
        assert result.status == AuthenticationStatus.FAILED
        assert result.authenticated_user is None
        assert result.error_message == "User not found"

        # Verify no event was published
        events = event_bus.get_published_events()
        assert len(events) == 0

    def test_authentication_with_wrong_password(self):
        """Test authentication flow with wrong password."""
        # Arrange
        user_repository = InMemoryUserRepository()
        event_bus = InMemoryEventBus()

        # Add a test user
        user_repository.add_user("test_user", "correct_password")

        # Set up use case
        authentication_usecase = AuthenticatePrincipalUseCase(
            user_repository, event_bus
        )

        # Act
        credentials = Credentials("test_user", "wrong_password")
        result = authentication_usecase.execute(credentials)

        # Assert
        assert result.status == AuthenticationStatus.FAILED
        assert result.authenticated_user is None
        assert result.error_message == "Invalid credentials"

        # Verify no event was published
        events = event_bus.get_published_events()
        assert len(events) == 0

    def test_multiple_authentication_attempts(self):
        """Test multiple authentication attempts to verify state isolation."""
        # Arrange
        user_repository = InMemoryUserRepository()
        event_bus = InMemoryEventBus()

        # Add test users
        user1_id = user_repository.add_user("user1", "password1")
        user2_id = user_repository.add_user("user2", "password2")

        authentication_usecase = AuthenticatePrincipalUseCase(
            user_repository, event_bus
        )

        # Act - Authenticate first user
        result1 = authentication_usecase.execute(Credentials("user1", "password1"))

        # Act - Authenticate second user
        result2 = authentication_usecase.execute(Credentials("user2", "password2"))

        # Assert - Both authentications successful
        assert result1.status == AuthenticationStatus.SUCCESS
        assert result1.authenticated_user is not None
        assert result1.authenticated_user.user_id == user1_id.value
        assert result1.authenticated_user.username == "user1"

        assert result2.status == AuthenticationStatus.SUCCESS
        assert result2.authenticated_user is not None
        assert result2.authenticated_user.user_id == user2_id.value
        assert result2.authenticated_user.username == "user2"

        # Verify both events were published
        events = event_bus.get_published_events()
        assert len(events) == 2

        assert events[0]["user_id"] == user1_id.value
        assert events[1]["user_id"] == user2_id.value
