"""
Domain events for Morty service.

Domain events represent something that happened in the domain that domain experts care about.
They are used for loose coupling between bounded contexts and eventual consistency.
"""

from datetime import datetime
from uuid import UUID

from .value_objects import ValueObject


class DomainEvent(ValueObject):
    """Base class for all domain events."""

    def __init__(self, occurred_at: datetime | None = None):
        self._occurred_at = occurred_at or datetime.utcnow()
        self._event_id = str(UUID())

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at

    @property
    def event_id(self) -> str:
        return self._event_id

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


class TaskCreated(DomainEvent):
    """Event raised when a new task is created."""

    def __init__(
        self,
        task_id: UUID,
        title: str,
        priority: str,
        assignee_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ):
        super().__init__(occurred_at)
        self._task_id = task_id
        self._title = title
        self._priority = priority
        self._assignee_id = assignee_id

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def priority(self) -> str:
        return self._priority

    @property
    def assignee_id(self) -> UUID | None:
        return self._assignee_id


class TaskAssigned(DomainEvent):
    """Event raised when a task is assigned to a user."""

    def __init__(
        self,
        task_id: UUID,
        assignee_id: UUID,
        previous_assignee_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ):
        super().__init__(occurred_at)
        self._task_id = task_id
        self._assignee_id = assignee_id
        self._previous_assignee_id = previous_assignee_id

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @property
    def assignee_id(self) -> UUID:
        return self._assignee_id

    @property
    def previous_assignee_id(self) -> UUID | None:
        return self._previous_assignee_id


class TaskCompleted(DomainEvent):
    """Event raised when a task is completed."""

    def __init__(
        self,
        task_id: UUID,
        assignee_id: UUID,
        completed_at: datetime,
        occurred_at: datetime | None = None,
    ):
        super().__init__(occurred_at)
        self._task_id = task_id
        self._assignee_id = assignee_id
        self._completed_at = completed_at

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @property
    def assignee_id(self) -> UUID:
        return self._assignee_id

    @property
    def completed_at(self) -> datetime:
        return self._completed_at


class TaskStatusChanged(DomainEvent):
    """Event raised when a task status changes."""

    def __init__(
        self,
        task_id: UUID,
        old_status: str,
        new_status: str,
        changed_by: UUID,
        occurred_at: datetime | None = None,
    ):
        super().__init__(occurred_at)
        self._task_id = task_id
        self._old_status = old_status
        self._new_status = new_status
        self._changed_by = changed_by

    @property
    def task_id(self) -> UUID:
        return self._task_id

    @property
    def old_status(self) -> str:
        return self._old_status

    @property
    def new_status(self) -> str:
        return self._new_status

    @property
    def changed_by(self) -> UUID:
        return self._changed_by


class UserActivated(DomainEvent):
    """Event raised when a user is activated."""

    def __init__(self, user_id: UUID, activated_by: UUID, occurred_at: datetime | None = None):
        super().__init__(occurred_at)
        self._user_id = user_id
        self._activated_by = activated_by

    @property
    def user_id(self) -> UUID:
        return self._user_id

    @property
    def activated_by(self) -> UUID:
        return self._activated_by


class UserDeactivated(DomainEvent):
    """Event raised when a user is deactivated."""

    def __init__(
        self,
        user_id: UUID,
        deactivated_by: UUID,
        occurred_at: datetime | None = None,
    ):
        super().__init__(occurred_at)
        self._user_id = user_id
        self._deactivated_by = deactivated_by

    @property
    def user_id(self) -> UUID:
        return self._user_id

    @property
    def deactivated_by(self) -> UUID:
        return self._deactivated_by
