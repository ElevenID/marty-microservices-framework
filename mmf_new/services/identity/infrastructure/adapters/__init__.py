"""In-memory implementations of outbound ports for testing."""

from mmf_new.services.identity.application.ports_out import EventBus, UserRepository
from mmf_new.services.identity.domain.models import Credentials, UserId

from .jwt_adapter import JWTConfig, JWTTokenProvider


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of UserRepository for testing."""

    def __init__(self):
        # Simple user store: username -> (user_id, password_hash)
        self._users = {
            "testuser": (UserId("user123"), "hashed_password123"),
            "admin": (UserId("admin456"), "hashed_admin_password"),
        }

    def find_by_username(self, username: str) -> UserId | None:
        """Find a user by username."""
        user_data = self._users.get(username)
        if user_data is None:
            return None
        return user_data[0]

    def verify_credentials(self, credentials: Credentials) -> bool:
        """Verify user credentials."""
        user_data = self._users.get(credentials.username)
        if user_data is None:
            return False

        # Simple password verification (in reality, would use proper hashing)
        stored_password_hash = user_data[1]
        return self._verify_password(credentials.password, stored_password_hash)

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Simple password verification for testing."""
        # In a real implementation, this would use bcrypt or similar
        return f"hashed_{password}" == stored_hash

    def add_user(
        self, username: str, password: str, user_id: UserId | None = None
    ) -> UserId:
        """Add a user for testing purposes."""
        if user_id is None:
            user_id = UserId(f"user_{len(self._users)}")

        password_hash = f"hashed_{password}"
        self._users[username] = (user_id, password_hash)
        return user_id


class InMemoryEventBus(EventBus):
    """In-memory implementation of EventBus for testing."""

    def __init__(self):
        self._published_events = []

    def publish(self, event: dict[str, any]) -> None:
        """Publish an event."""
        self._published_events.append(event.copy())

    def get_published_events(self) -> list[dict[str, any]]:
        """Get all published events for testing."""
        return self._published_events.copy()

    def clear_events(self) -> None:
        """Clear all events for testing."""
        self._published_events.clear()


__all__ = [
    "InMemoryUserRepository",
    "InMemoryEventBus",
    "JWTTokenProvider",
    "JWTConfig",
]
