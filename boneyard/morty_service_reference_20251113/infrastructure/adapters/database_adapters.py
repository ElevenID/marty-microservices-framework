"""
Database adapters for the Morty service.

These adapters implement the repository ports defined in the application layer,
providing concrete persistence implementations using SQLAlchemy.
"""

import builtins
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...application.ports.output_ports import (
    TaskRepositoryPort,
    UnitOfWorkPort,
    UserRepositoryPort,
)
from ...domain.entities import Task, User
from ...domain.value_objects import Email, PersonName, PhoneNumber
from .models import TaskModel, UserModel


class SQLAlchemyTaskRepository(TaskRepositoryPort):
    """SQLAlchemy implementation of the task repository port."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, task: Task) -> None:
        """Save a task to the database."""
        # Check if task already exists
        stmt = sa.select(TaskModel).where(TaskModel.id == task.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.title = task.title
            existing.description = task.description
            existing.priority = task.priority
            existing.status = task.status
            existing.assignee_id = task.assignee.id if task.assignee else None
            existing.completed_at = task.completed_at
            existing.updated_at = task.updated_at
            existing.version = task.version
        else:
            # Create new
            task_model = TaskModel(
                id=task.id,
                title=task.title,
                description=task.description,
                priority=task.priority,
                status=task.status,
                assignee_id=task.assignee.id if task.assignee else None,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at,
                version=task.version,
            )
            self._session.add(task_model)

    async def find_by_id(self, task_id: UUID) -> Task | None:
        """Find a task by its ID."""
        stmt = (
            sa.select(TaskModel)
            .options(selectinload(TaskModel.assignee))
            .where(TaskModel.id == task_id)
        )
        result = await self._session.execute(stmt)
        task_model = result.scalar_one_or_none()

        if not task_model:
            return None

        return self._model_to_entity(task_model)

    async def find_by_assignee(self, user_id: UUID) -> builtins.list[Task]:
        """Find all tasks assigned to a specific user."""
        stmt = (
            sa.select(TaskModel)
            .options(selectinload(TaskModel.assignee))
            .where(TaskModel.assignee_id == user_id)
            .order_by(TaskModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        task_models = result.scalars().all()

        return [self._model_to_entity(model) for model in task_models]

    async def find_by_status(self, status: str) -> builtins.list[Task]:
        """Find all tasks with a specific status."""
        stmt = (
            sa.select(TaskModel)
            .options(selectinload(TaskModel.assignee))
            .where(TaskModel.status == status)
            .order_by(TaskModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        task_models = result.scalars().all()

        return [self._model_to_entity(model) for model in task_models]

    async def find_all(self, limit: int | None = None, offset: int = 0) -> builtins.list[Task]:
        """Find all tasks with optional pagination."""
        stmt = (
            sa.select(TaskModel)
            .options(selectinload(TaskModel.assignee))
            .order_by(TaskModel.created_at.desc())
            .offset(offset)
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        task_models = result.scalars().all()

        return [self._model_to_entity(model) for model in task_models]

    async def delete(self, task_id: UUID) -> bool:
        """Delete a task by its ID."""
        stmt = sa.delete(TaskModel).where(TaskModel.id == task_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def count_by_user_and_status(self, user_id: UUID, status: str) -> int:
        """Count tasks for a user with a specific status."""
        stmt = (
            sa.select(sa.func.count(TaskModel.id))
            .where(TaskModel.assignee_id == user_id)
            .where(TaskModel.status == status)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    def _model_to_entity(self, model: TaskModel) -> Task:
        """Convert a database model to a domain entity."""
        # Create assignee if present
        assignee = None
        if model.assignee:
            assignee = User(
                name=PersonName(model.assignee.first_name, model.assignee.last_name),
                email=Email(model.assignee.email),
                phone=PhoneNumber(model.assignee.phone) if model.assignee.phone else None,
                entity_id=model.assignee.id,
            )
            assignee._active = model.assignee.active
            assignee._created_at = model.assignee.created_at
            assignee._updated_at = model.assignee.updated_at
            assignee._version = model.assignee.version

        # Create task
        task = Task(
            title=model.title,
            description=model.description,
            assignee=assignee,
            priority=model.priority,
            entity_id=model.id,
        )

        # Set internal state
        task._status = model.status
        task._completed_at = model.completed_at
        task._created_at = model.created_at
        task._updated_at = model.updated_at
        task._version = model.version

        return task


class SQLAlchemyUserRepository(UserRepositoryPort):
    """SQLAlchemy implementation of the user repository port."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User) -> None:
        """Save a user to the database."""
        # Check if user already exists
        stmt = sa.select(UserModel).where(UserModel.id == user.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.first_name = user.name.first_name
            existing.last_name = user.name.last_name
            existing.email = user.email.value
            existing.phone = user.phone.value if user.phone else None
            existing.active = user.active
            existing.updated_at = user.updated_at
            existing.version = user.version
        else:
            # Create new
            user_model = UserModel(
                id=user.id,
                first_name=user.name.first_name,
                last_name=user.name.last_name,
                email=user.email.value,
                phone=user.phone.value if user.phone else None,
                active=user.active,
                created_at=user.created_at,
                updated_at=user.updated_at,
                version=user.version,
            )
            self._session.add(user_model)

    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find a user by their ID."""
        stmt = sa.select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        user_model = result.scalar_one_or_none()

        if not user_model:
            return None

        return self._model_to_entity(user_model)

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by their email address."""
        stmt = sa.select(UserModel).where(UserModel.email == email.lower())
        result = await self._session.execute(stmt)
        user_model = result.scalar_one_or_none()

        if not user_model:
            return None

        return self._model_to_entity(user_model)

    async def find_active_users(self) -> builtins.list[User]:
        """Find all active users."""
        stmt = sa.select(UserModel).where(UserModel.active).order_by(UserModel.created_at.desc())
        result = await self._session.execute(stmt)
        user_models = result.scalars().all()

        return [self._model_to_entity(model) for model in user_models]

    async def find_all(self, limit: int | None = None, offset: int = 0) -> builtins.list[User]:
        """Find all users with optional pagination."""
        stmt = sa.select(UserModel).order_by(UserModel.created_at.desc()).offset(offset)

        if limit:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        user_models = result.scalars().all()

        return [self._model_to_entity(model) for model in user_models]

    async def delete(self, user_id: UUID) -> bool:
        """Delete a user by their ID."""
        stmt = sa.delete(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _model_to_entity(self, model: UserModel) -> User:
        """Convert a database model to a domain entity."""
        user = User(
            name=PersonName(model.first_name, model.last_name),
            email=Email(model.email),
            phone=PhoneNumber(model.phone) if model.phone else None,
            entity_id=model.id,
        )

        # Set internal state
        user._active = model.active
        user._created_at = model.created_at
        user._updated_at = model.updated_at
        user._version = model.version

        return user


class SQLAlchemyUnitOfWork(UnitOfWorkPort):
    """SQLAlchemy implementation of the unit of work port."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self):
        """Enter the transaction context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the transaction context, rolling back on error."""
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self._session.rollback()
