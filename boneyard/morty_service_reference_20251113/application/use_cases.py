"""
Use cases for the Morty service application layer.

Use cases implement the business workflows and orchestrate domain services.
They are the entry points from external adapters into the business logic.
"""

import builtins
from uuid import UUID

from ..domain.entities import Task, User
from ..domain.services import TaskManagementService
from .ports.input_ports import (
    AssignTaskCommand,
    CreateTaskCommand,
    TaskDTO,
    TaskManagementPort,
    UpdateTaskCommand,
)
from .ports.output_ports import (
    CachePort,
    EventPublisherPort,
    NotificationPort,
    TaskRepositoryPort,
    UnitOfWorkPort,
    UserRepositoryPort,
)


class TaskManagementUseCase(TaskManagementPort):
    """Use case implementation for task management operations."""

    def __init__(
        self,
        task_repository: TaskRepositoryPort,
        user_repository: UserRepositoryPort,
        event_publisher: EventPublisherPort,
        notification_service: NotificationPort,
        cache: CachePort,
        unit_of_work: UnitOfWorkPort,
    ):
        self._task_repository = task_repository
        self._user_repository = user_repository
        self._event_publisher = event_publisher
        self._notification_service = notification_service
        self._cache = cache
        self._unit_of_work = unit_of_work
        self._task_management_service = TaskManagementService()

    async def create_task(self, command: CreateTaskCommand) -> TaskDTO:
        """Create a new task."""
        assignee = None
        if command.assignee_id:
            assignee = await self._user_repository.find_by_id(command.assignee_id)
            if not assignee:
                raise ValueError(f"User with ID {command.assignee_id} not found")

        # Use domain service to create task
        task = self._task_management_service.create_task(
            title=command.title,
            description=command.description,
            priority=command.priority,
            assignee=assignee,
        )

        async with self._unit_of_work:
            # Save task
            await self._task_repository.save(task)

            # Update user if assigned
            if assignee:
                assignee.add_task(task)
                await self._user_repository.save(assignee)

            await self._unit_of_work.commit()

        # Publish events
        events = self._task_management_service.get_pending_events()
        for event in events:
            await self._event_publisher.publish(event)
        self._task_management_service.clear_events()

        # Send notification if assigned
        if assignee:
            await self._notification_service.send_task_assigned_notification(
                user_email=assignee.email.value, task_title=task.title, task_id=task.id
            )

        # Invalidate relevant cache
        await self._cache.invalidate_pattern("tasks:*")

        return self._task_to_dto(task, assignee)

    async def update_task(self, command: UpdateTaskCommand) -> TaskDTO:
        """Update an existing task."""
        task = await self._task_repository.find_by_id(command.task_id)
        if not task:
            raise ValueError(f"Task with ID {command.task_id} not found")

        # Update fields if provided
        if command.title:
            task._title = command.title
        if command.description:
            task._description = command.description
        if command.priority:
            task.update_priority(command.priority)

        async with self._unit_of_work:
            await self._task_repository.save(task)
            await self._unit_of_work.commit()

        # Invalidate cache
        await self._cache.invalidate_pattern(f"task:{command.task_id}")
        await self._cache.invalidate_pattern("tasks:*")

        assignee = task.assignee
        return self._task_to_dto(task, assignee)

    async def assign_task(self, command: AssignTaskCommand) -> TaskDTO:
        """Assign a task to a user."""
        task = await self._task_repository.find_by_id(command.task_id)
        if not task:
            raise ValueError(f"Task with ID {command.task_id} not found")

        assignee = await self._user_repository.find_by_id(command.assignee_id)
        if not assignee:
            raise ValueError(f"User with ID {command.assignee_id} not found")

        # Use domain service for assignment
        self._task_management_service.assign_task(task, assignee)

        async with self._unit_of_work:
            await self._task_repository.save(task)
            await self._user_repository.save(assignee)
            await self._unit_of_work.commit()

        # Publish events
        events = self._task_management_service.get_pending_events()
        for event in events:
            await self._event_publisher.publish(event)
        self._task_management_service.clear_events()

        # Send notification
        await self._notification_service.send_task_assigned_notification(
            user_email=assignee.email.value, task_title=task.title, task_id=task.id
        )

        # Invalidate cache
        await self._cache.invalidate_pattern(f"task:{command.task_id}")
        await self._cache.invalidate_pattern(f"user:{command.assignee_id}:*")

        return self._task_to_dto(task, assignee)

    async def complete_task(self, task_id: UUID) -> TaskDTO:
        """Mark a task as completed."""
        task = await self._task_repository.find_by_id(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        # Use domain service for completion
        self._task_management_service.complete_task(task)

        async with self._unit_of_work:
            await self._task_repository.save(task)
            await self._unit_of_work.commit()

        # Publish events
        events = self._task_management_service.get_pending_events()
        for event in events:
            await self._event_publisher.publish(event)
        self._task_management_service.clear_events()

        # Send notification
        if task.assignee:
            await self._notification_service.send_task_completed_notification(
                user_email=task.assignee.email.value,
                task_title=task.title,
                task_id=task.id,
            )

        # Invalidate cache
        await self._cache.invalidate_pattern(f"task:{task_id}")
        await self._cache.invalidate_pattern("tasks:*")

        return self._task_to_dto(task, task.assignee)

    async def get_task(self, task_id: UUID) -> TaskDTO | None:
        """Get a task by its ID."""
        # Try cache first

        task = await self._task_repository.find_by_id(task_id)
        if not task:
            return None

        assignee = task.assignee
        return self._task_to_dto(task, assignee)

    async def get_tasks_by_assignee(self, user_id: UUID) -> builtins.list[TaskDTO]:
        """Get all tasks assigned to a specific user."""
        tasks = await self._task_repository.find_by_assignee(user_id)
        assignee = await self._user_repository.find_by_id(user_id)

        return [self._task_to_dto(task, assignee) for task in tasks]

    async def get_tasks_by_status(self, status: str) -> builtins.list[TaskDTO]:
        """Get all tasks with a specific status."""
        tasks = await self._task_repository.find_by_status(status)
        result = []

        for task in tasks:
            assignee = task.assignee
            result.append(self._task_to_dto(task, assignee))

        return result

    async def get_all_tasks(
        self, limit: int | None = None, offset: int = 0
    ) -> builtins.list[TaskDTO]:
        """Get all tasks with optional pagination."""
        tasks = await self._task_repository.find_all(limit, offset)
        result = []

        for task in tasks:
            assignee = task.assignee
            result.append(self._task_to_dto(task, assignee))

        return result

    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task by its ID."""
        async with self._unit_of_work:
            deleted = await self._task_repository.delete(task_id)
            if deleted:
                await self._unit_of_work.commit()
                # Invalidate cache
                await self._cache.invalidate_pattern(f"task:{task_id}")
                await self._cache.invalidate_pattern("tasks:*")
            return deleted

    def _task_to_dto(self, task: Task, assignee: User | None = None) -> TaskDTO:
        """Convert a task entity to a DTO."""
        return TaskDTO(
            id=task.id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            status=task.status,
            assignee_id=assignee.id if assignee else None,
            assignee_name=assignee.name.full_name if assignee else None,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
        )
