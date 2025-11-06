"""Use case implementations for identity service."""

from datetime import datetime, timedelta

from mmf_new.services.identity.application.ports_in import AuthenticatePrincipal
from mmf_new.services.identity.application.ports_out import EventBus, UserRepository
from mmf_new.services.identity.domain.models import (
    AuthenticationResult,
    AuthenticationStatus,
    Credentials,
    Principal,
    UserId,
)


class AuthenticatePrincipalUseCase(AuthenticatePrincipal):
    """Implementation of the authenticate principal use case."""

    def __init__(self, user_repository: UserRepository, event_bus: EventBus):
        self._user_repository = user_repository
        self._event_bus = event_bus

    def execute(self, credentials: Credentials) -> AuthenticationResult:
        """Execute the authentication use case."""
        # Find user by username
        user_id = self._user_repository.find_by_username(credentials.username)
        if user_id is None:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                error_message="User not found"
            )

        # Verify credentials
        if not self._user_repository.verify_credentials(credentials):
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                error_message="Invalid credentials"
            )

        # Create principal
        now = datetime.utcnow()
        principal = Principal(
            user_id=user_id,
            username=credentials.username,
            authenticated_at=now,
            expires_at=now + timedelta(hours=24)
        )

        # Publish authentication event
        self._event_bus.publish({
            "event_type": "user_authenticated",
            "user_id": user_id.value,
            "timestamp": now.isoformat()
        })

        return AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            principal=principal
        )
