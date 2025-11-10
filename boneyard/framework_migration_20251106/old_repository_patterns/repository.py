"""
Repository pattern implementation for the enterprise database framework.
"""

import logging
from abc import ABC
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .manager import DatabaseManager
from .models import BaseModel

logger = logging.getLogger(__name__)

# Type variables
ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class RepositoryError(Exception):
    """Base repository error."""


class NotFoundError(RepositoryError):
    """Entity not found error."""


class ConflictError(RepositoryError):
    """Entity conflict error (e.g., duplicate key)."""


class ValidationError(RepositoryError):
    """Validation error."""


class BaseRepository(Generic[ModelType], ABC):
    """Abstract base repository with common CRUD operations."""

    def __init__(self, db_manager: DatabaseManager, model_class: type[ModelType]):
        self.db_manager = db_manager
        self.model_class = model_class
        self.table_name = model_class.__tablename__

    @asynccontextmanager
    async def get_session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get a database session."""
        async with self.db_manager.get_session() as session:
            yield session

    @asynccontextmanager
    async def get_transaction(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get a database session with transaction."""
        async with self.db_manager.get_transaction() as session:
            yield session

    async def create(self, obj_in: CreateSchemaType | dict[str, Any], **kwargs) -> ModelType:
        """Create a new entity."""
        async with self.get_transaction() as session:
            try:
                # Convert input to dict if needed
                if hasattr(obj_in, "dict"):
                    create_data = obj_in.dict(exclude_unset=True)
                elif hasattr(obj_in, "model_dump"):
                    create_data = obj_in.model_dump(exclude_unset=True)
                elif isinstance(obj_in, dict):
                    create_data = obj_in.copy()
                else:
                    create_data = obj_in

                # Add any additional kwargs
                create_data.update(kwargs)

                # Create instance
                db_obj = self.model_class(**create_data)

                # Set audit fields if model supports them
                if hasattr(db_obj, "created_by") and "created_by" in create_data:
                    db_obj.created_by = create_data["created_by"]

                session.add(db_obj)
                await session.flush()
                await session.refresh(db_obj)

                logger.debug("Created %s with id: %s", self.model_class.__name__, db_obj.id)
                return db_obj

            except IntegrityError as e:
                logger.error("Integrity error creating %s: %s", self.model_class.__name__, e)
                raise ConflictError(f"Entity already exists or violates constraints: {e}") from e
            except Exception as e:
                logger.error("Error creating %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error creating entity: {e}") from e

    async def get_by_id(self, entity_id: int | str | UUID) -> ModelType | None:
        """Get entity by ID."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class).where(self.model_class.id == entity_id)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                result = await session.execute(query)
                return result.scalar_one_or_none()

            except Exception as e:
                logger.error(
                    "Error getting %s by id %s: %s",
                    self.model_class.__name__,
                    entity_id,
                    e,
                )
                raise RepositoryError(f"Error getting entity: {e}") from e

    async def get_by_id_or_404(self, entity_id: int | str | UUID) -> ModelType:
        """Get entity by ID or raise NotFoundError."""
        entity = await self.get_by_id(entity_id)
        if not entity:
            raise NotFoundError(f"{self.model_class.__name__} with id {entity_id} not found")
        return entity

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[ModelType]:
        """Get all entities with pagination."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply ordering
                if order_by and hasattr(self.model_class, order_by):
                    order_column = getattr(self.model_class, order_by)
                    if order_desc:
                        query = query.order_by(desc(order_column))
                    else:
                        query = query.order_by(asc(order_column))
                elif hasattr(self.model_class, "created_at"):
                    query = query.order_by(desc(self.model_class.created_at))

                # Apply pagination
                query = query.offset(skip).limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error("Error getting all %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error getting entities: {e}") from e

    async def update(
        self,
        entity_id: int | str | UUID,
        obj_in: UpdateSchemaType | dict[str, Any],
        **kwargs,
    ) -> ModelType | None:
        """Update an entity."""
        async with self.get_transaction() as session:
            try:
                # Get existing entity
                db_obj = await self.get_by_id_or_404(entity_id)

                # Convert input to dict if needed
                if hasattr(obj_in, "dict"):
                    update_data = obj_in.dict(exclude_unset=True)
                elif hasattr(obj_in, "model_dump"):
                    update_data = obj_in.model_dump(exclude_unset=True)
                elif isinstance(obj_in, dict):
                    update_data = obj_in.copy()
                else:
                    update_data = obj_in

                # Add any additional kwargs
                update_data.update(kwargs)

                # Remove None values
                update_data = {k: v for k, v in update_data.items() if v is not None}

                if not update_data:
                    return db_obj

                # Update audit fields if model supports them
                if hasattr(db_obj, "updated_by") and "updated_by" in update_data:
                    update_data["updated_by"] = update_data["updated_by"]

                # Update the entity
                for field, value in update_data.items():
                    if hasattr(db_obj, field):
                        setattr(db_obj, field, value)

                await session.flush()
                await session.refresh(db_obj)

                logger.debug("Updated %s with id: %s", self.model_class.__name__, entity_id)
                return db_obj

            except NotFoundError:
                raise
            except IntegrityError as e:
                logger.error("Integrity error updating %s: %s", self.model_class.__name__, e)
                raise ConflictError(f"Update violates constraints: {e}") from e
            except Exception as e:
                logger.error("Error updating %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error updating entity: {e}") from e

    async def delete(self, entity_id: int | str | UUID, hard_delete: bool = False) -> bool:
        """Delete an entity (soft delete by default if supported)."""
        async with self.get_transaction() as session:
            try:
                db_obj = await self.get_by_id_or_404(entity_id)

                if not hard_delete and hasattr(db_obj, "deleted_at"):
                    # Soft delete
                    db_obj.deleted_at = datetime.utcnow()
                    await session.flush()
                    logger.debug(
                        "Soft deleted %s with id: %s",
                        self.model_class.__name__,
                        entity_id,
                    )
                else:
                    # Hard delete
                    await session.delete(db_obj)
                    logger.debug(
                        "Hard deleted %s with id: %s",
                        self.model_class.__name__,
                        entity_id,
                    )

                return True

            except NotFoundError:
                return False
            except Exception as e:
                logger.error("Error deleting %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error deleting entity: {e}") from e

    async def count(self, **filters) -> int:
        """Count entities with optional filters."""
        async with self.get_session() as session:
            try:
                query = select(func.count(self.model_class.id))

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply filters
                for field, value in filters.items():
                    if hasattr(self.model_class, field):
                        query = query.where(getattr(self.model_class, field) == value)

                result = await session.execute(query)
                return result.scalar() or 0

            except Exception as e:
                logger.error("Error counting %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error counting entities: {e}") from e

    async def exists(self, entity_id: int | str | UUID) -> bool:
        """Check if entity exists."""
        entity = await self.get_by_id(entity_id)
        return entity is not None

    async def find_by_field(self, field_name: str, value: Any) -> list[ModelType]:
        """Find entities by a specific field value."""
        async with self.get_session() as session:
            try:
                if not hasattr(self.model_class, field_name):
                    raise ValueError(
                        f"Field {field_name} does not exist on {self.model_class.__name__}"
                    )

                query = select(self.model_class).where(
                    getattr(self.model_class, field_name) == value
                )

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error(
                    "Error finding %s by %s: %s",
                    self.model_class.__name__,
                    field_name,
                    e,
                )
                raise RepositoryError(f"Error finding entities: {e}") from e

    async def find_one_by_field(self, field_name: str, value: Any) -> ModelType | None:
        """Find one entity by a specific field value."""
        results = await self.find_by_field(field_name, value)
        return results[0] if results else None

    async def bulk_create(
        self, objects_in: list[CreateSchemaType | dict[str, Any]]
    ) -> list[ModelType]:
        """Create multiple entities in bulk."""
        async with self.get_transaction() as session:
            try:
                db_objects = []
                for obj_in in objects_in:
                    # Convert input to dict if needed
                    if hasattr(obj_in, "dict"):
                        create_data = obj_in.dict(exclude_unset=True)
                    elif hasattr(obj_in, "model_dump"):
                        create_data = obj_in.model_dump(exclude_unset=True)
                    elif isinstance(obj_in, dict):
                        create_data = obj_in.copy()
                    else:
                        create_data = obj_in

                    db_obj = self.model_class(**create_data)
                    db_objects.append(db_obj)

                session.add_all(db_objects)
                await session.flush()

                # Refresh all objects
                for db_obj in db_objects:
                    await session.refresh(db_obj)

                logger.debug(
                    "Bulk created %d %s objects",
                    len(db_objects),
                    self.model_class.__name__,
                )
                return db_objects

            except IntegrityError as e:
                logger.error(
                    "Integrity error in bulk create %s: %s",
                    self.model_class.__name__,
                    e,
                )
                raise ConflictError(f"Bulk create violates constraints: {e}") from e
            except Exception as e:
                logger.error("Error in bulk create %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error in bulk create: {e}") from e

    async def search(
        self,
        filters: dict[str, Any] | None = None,
        search_term: str | None = None,
        search_fields: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[ModelType]:
        """Advanced search with filters and text search."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply filters
                if filters:
                    for field, value in filters.items():
                        if hasattr(self.model_class, field):
                            column = getattr(self.model_class, field)
                            if isinstance(value, list):
                                query = query.where(column.in_(value))
                            elif isinstance(value, dict) and "op" in value:
                                # Advanced operators: {'op': 'like', 'value': '%search%'}
                                op = value["op"]
                                val = value["value"]
                                if op == "like":
                                    query = query.where(column.like(val))
                                elif op == "ilike":
                                    query = query.where(column.ilike(val))
                                elif op == "gt":
                                    query = query.where(column > val)
                                elif op == "gte":
                                    query = query.where(column >= val)
                                elif op == "lt":
                                    query = query.where(column < val)
                                elif op == "lte":
                                    query = query.where(column <= val)
                                elif op == "ne":
                                    query = query.where(column != val)
                            else:
                                query = query.where(column == value)

                # Apply text search
                if search_term and search_fields:
                    search_conditions = []
                    for field in search_fields:
                        if hasattr(self.model_class, field):
                            column = getattr(self.model_class, field)
                            search_conditions.append(column.ilike(f"%{search_term}%"))

                    if search_conditions:
                        query = query.where(or_(*search_conditions))

                # Apply ordering
                if order_by and hasattr(self.model_class, order_by):
                    order_column = getattr(self.model_class, order_by)
                    if order_desc:
                        query = query.order_by(desc(order_column))
                    else:
                        query = query.order_by(asc(order_column))
                elif hasattr(self.model_class, "created_at"):
                    query = query.order_by(desc(self.model_class.created_at))

                # Apply pagination
                query = query.offset(skip).limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error("Error searching %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error searching entities: {e}") from e


class Repository(BaseRepository[ModelType]):
    """Concrete repository implementation."""


# Repository factory
def create_repository(
    model_class: type[ModelType], db_manager: DatabaseManager
) -> Repository[ModelType]:
    """Create a repository for a model class."""
    return Repository(db_manager, model_class)
