"""
Domain entities for Morty service.

Entities represent business objects with identity that persists through their lifecycle.
They encapsulate business logic and maintain their invariants.
"""

import builtins
from abc import ABC
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from .value_objects import Email, PersonName, PhoneNumber


class DomainEntity(ABC):
    """Base class for all domain entities."""

    def __init__(self, entity_id: UUID | None = None):
        self._id = entity_id or uuid4()
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._version = 1

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def version(self) -> int:
        return self._version

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)


class Task(DomainEntity):
    """Task entity representing a work item in the Morty service."""

    def __init__(
        self,
        title: str,
        description: str,
        assignee: Optional["User"] = None,
        priority: str = "medium",
        entity_id: UUID | None = None,
    ):
        super().__init__(entity_id)
        self._title = title
        self._description = description
        self._assignee = assignee
        self._priority = priority
        self._status = "pending"
        self._completed_at: datetime | None = None

        self._validate()

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def assignee(self) -> Optional["User"]:
        return self._assignee

    @property
    def priority(self) -> str:
        return self._priority

    @property
    def status(self) -> str:
        return self._status

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    def assign_to(self, user: "User") -> None:
        """Assign this task to a user."""
        if self._status == "completed":
            raise ValueError("Cannot assign completed task")

        self._assignee = user
        self._updated_at = datetime.utcnow()
        self._version += 1

    def update_priority(self, priority: str) -> None:
        """Update task priority."""
        valid_priorities = ["low", "medium", "high", "urgent"]
        if priority not in valid_priorities:
            raise ValueError(f"Priority must be one of: {valid_priorities}")

        self._priority = priority
        self._updated_at = datetime.utcnow()
        self._version += 1

    def mark_completed(self) -> None:
        """Mark the task as completed."""
        if self._status == "completed":
            raise ValueError("Task is already completed")

        self._status = "completed"
        self._completed_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._version += 1

    def mark_in_progress(self) -> None:
        """Mark the task as in progress."""
        if self._status == "completed":
            raise ValueError("Cannot move completed task to in progress")

        self._status = "in_progress"
        self._updated_at = datetime.utcnow()
        self._version += 1

    def _validate(self) -> None:
        """Validate entity invariants."""
        if not self._title or not self._title.strip():
            raise ValueError("Task title cannot be empty")

        if not self._description or not self._description.strip():
            raise ValueError("Task description cannot be empty")

        valid_priorities = ["low", "medium", "high", "urgent"]
        if self._priority not in valid_priorities:
            raise ValueError(f"Priority must be one of: {valid_priorities}")


class User(DomainEntity):
    """User entity representing a person who can be assigned tasks."""

    def __init__(
        self,
        name: PersonName,
        email: Email,
        phone: PhoneNumber | None = None,
        entity_id: UUID | None = None,
    ):
        super().__init__(entity_id)
        self._name = name
        self._email = email
        self._phone = phone
        self._active = True
        self._assigned_tasks: builtins.list[Task] = []

    @property
    def name(self) -> PersonName:
        return self._name

    @property
    def email(self) -> Email:
        return self._email

    @property
    def phone(self) -> PhoneNumber | None:
        return self._phone

    @property
    def active(self) -> bool:
        return self._active

    @property
    def assigned_tasks(self) -> builtins.list[Task]:
        return self._assigned_tasks.copy()

    def deactivate(self) -> None:
        """Deactivate the user."""
        if not self._active:
            raise ValueError("User is already inactive")

        self._active = False
        self._updated_at = datetime.utcnow()
        self._version += 1

    def activate(self) -> None:
        """Activate the user."""
        if self._active:
            raise ValueError("User is already active")

        self._active = True
        self._updated_at = datetime.utcnow()
        self._version += 1

    def add_task(self, task: Task) -> None:
        """Add a task to the user's assigned tasks."""
        if not self._active:
            raise ValueError("Cannot assign tasks to inactive user")

        if task not in self._assigned_tasks:
            self._assigned_tasks.append(task)
            self._updated_at = datetime.utcnow()
            self._version += 1

    def remove_task(self, task: Task) -> None:
        """Remove a task from the user's assigned tasks."""
        if task in self._assigned_tasks:
            self._assigned_tasks.remove(task)
            self._updated_at = datetime.utcnow()
            self._version += 1

    def get_pending_tasks(self) -> builtins.list[Task]:
        """Get all pending tasks assigned to this user."""
        return [task for task in self._assigned_tasks if task.status == "pending"]

    def get_completed_tasks(self) -> builtins.list[Task]:
        """Get all completed tasks assigned to this user."""
        return [task for task in self._assigned_tasks if task.status == "completed"]
