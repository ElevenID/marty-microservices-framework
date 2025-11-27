from typing import Any, Optional
from uuid import UUID, uuid4

from mmf_new.core.domain.ports.repository import Repository
from mmf_new.services.identity.application.ports_out import UserRepository
from mmf_new.services.identity.domain.models import (
    AuthenticatedUser,
    Credentials,
    UserId,
)


class InMemoryEventBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def get_published_events(self):
        return self.events


class InMemoryUserRepository(UserRepository, Repository[AuthenticatedUser]):
    def __init__(self):
        self.users = {}
        self.credentials = {}

    def add_user(self, username, password):
        user_id = UserId(str(uuid4()))
        self.users[username] = user_id
        self.credentials[username] = password
        return user_id

    def find_by_username(self, username: str) -> UserId | None:
        return self.users.get(username)

    def verify_credentials(self, credentials: Credentials) -> bool:
        if credentials.username in self.credentials:
            return self.credentials[credentials.username] == credentials.password
        return False

    async def save(self, entity: AuthenticatedUser) -> AuthenticatedUser:
        return entity

    async def find_by_id(self, entity_id: UUID | str | int) -> AuthenticatedUser | None:
        return None

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[AuthenticatedUser]:
        return []

    async def delete(self, entity_id: UUID | str | int) -> bool:
        return True

    async def count(self) -> int:
        return len(self.users)

    async def exists(self, entity_id: UUID | str | int) -> bool:
        return False

    async def update(
        self, entity_id: UUID | str | int, updates: dict[str, Any]
    ) -> AuthenticatedUser | None:
        return None
