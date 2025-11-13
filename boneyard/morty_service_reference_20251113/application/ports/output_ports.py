"""
Output ports (interfaces) for external dependencies.

These interfaces define the contracts that infrastructure adapters must implement.
The application layer depends on these abstractions, not on concrete implementations.
"""

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from ...domain.entities import Task, User
from ...domain.events import DomainEvent


class TaskRepositoryPort(ABC):
    """Port for task persistence operations."""

    @abstractmethod
    async def save(self, task: Task) -> None:
        """Save a task to the repository."""

    @abstractmethod
    async def find_by_id(self, task_id: UUID) -> Task | None:
        """Find a task by its ID."""

    @abstractmethod
    async def find_by_assignee(self, user_id: UUID) -> builtins.list[Task]:
        """Find all tasks assigned to a specific user."""

    @abstractmethod
    async def find_by_status(self, status: str) -> builtins.list[Task]:
        """Find all tasks with a specific status."""

    @abstractmethod
    async def find_all(self, limit: int | None = None, offset: int = 0) -> builtins.list[Task]:
        """Find all tasks with optional pagination."""

    @abstractmethod
    async def delete(self, task_id: UUID) -> bool:
        """Delete a task by its ID. Returns True if deleted."""

    @abstractmethod
    async def count_by_user_and_status(self, user_id: UUID, status: str) -> int:
        """Count tasks for a user with a specific status."""


class UserRepositoryPort(ABC):
    """Port for user persistence operations."""

    @abstractmethod
    async def save(self, user: User) -> None:
        """Save a user to the repository."""

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find a user by their ID."""

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        """Find a user by their email address."""

    @abstractmethod
    async def find_active_users(self) -> builtins.list[User]:
        """Find all active users."""

    @abstractmethod
    async def find_all(self, limit: int | None = None, offset: int = 0) -> builtins.list[User]:
        """Find all users with optional pagination."""

    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        """Delete a user by their ID. Returns True if deleted."""


class EventPublisherPort(ABC):
    """Port for publishing domain events."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""

    @abstractmethod
    async def publish_batch(self, events: builtins.list[DomainEvent]) -> None:
        """Publish multiple domain events as a batch."""


class NotificationPort(ABC):
    """Port for sending notifications."""

    @abstractmethod
    async def send_task_assigned_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is assigned."""

    @abstractmethod
    async def send_task_completed_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is completed."""

    @abstractmethod
    async def send_user_workload_alert(self, user_email: str, pending_task_count: int) -> None:
        """Send alert when user workload is high."""


class CachePort(ABC):
    """Port for caching operations."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get a value from cache."""

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a value in cache with optional TTL."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from cache."""

    @abstractmethod
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all cache keys matching a pattern."""


class UnitOfWorkPort(ABC):
    """Port for managing database transactions."""

    @abstractmethod
    async def __aenter__(self):
        """Enter the transaction context."""

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context, rolling back on error."""

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
