"""SQLAlchemy repository implementations for the infrastructure layer."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mmf.core.domain.ports.repository import (
    DomainRepository,
    EntityConflictError,
    EntityNotFoundError,
    Repository,
    RepositoryError,
)

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")


class SQLAlchemyRepository(Repository[ModelType], Generic[ModelType]):
    """SQLAlchemy implementation of the Repository interface."""

    def __init__(self, session_factory, model_class: type[ModelType]):
        """Initialize repository with session factory and model class.

        Args:
            session_factory: Factory function that returns AsyncSession
            model_class: SQLAlchemy model class
        """
        self.session_factory = session_factory
        self.model_class = model_class

    @asynccontextmanager
    async def get_session(self):
        """Get a database session."""
        async with self.session_factory() as session:
            yield session

    @asynccontextmanager
    async def get_transaction(self):
        """Get a database session with transaction."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def save(self, entity: ModelType) -> ModelType:
        """Save an entity to the repository."""
        async with self.get_transaction() as session:
            try:
                session.add(entity)
                await session.flush()
                await session.refresh(entity)
                return entity
            except IntegrityError as e:
                logger.error("Integrity error saving %s: %s", self.model_class.__name__, e)
                raise EntityConflictError(f"Entity conflicts with existing data: {e}") from e
            except Exception as e:
                logger.error("Error saving %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error saving entity: {e}") from e

    async def find_by_id(self, entity_id: UUID | str | int) -> ModelType | None:
        """Find entity by its unique identifier."""
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
                    "Error finding %s by id %s: %s",
                    self.model_class.__name__,
                    entity_id,
                    e,
                )
                raise RepositoryError(f"Error finding entity: {e}") from e

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Find all entities with pagination."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply ordering - prefer created_at if available
                if hasattr(self.model_class, "created_at"):
                    query = query.order_by(desc(self.model_class.created_at))

                # Apply pagination
                query = query.offset(skip).limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error("Error finding all %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error finding entities: {e}") from e

    async def update(
        self, entity_id: UUID | str | int, updates: dict[str, Any]
    ) -> ModelType | None:
        """Update an entity."""
        async with self.get_transaction() as session:
            try:
                # Fetch entity within the transaction's session to avoid detached instances
                query = select(self.model_class).where(self.model_class.id == entity_id)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                result = await session.execute(query)
                entity = result.scalar_one_or_none()

                if not entity:
                    raise EntityNotFoundError(
                        f"{self.model_class.__name__} with id {entity_id} not found"
                    )

                # Apply updates
                for key, value in updates.items():
                    if hasattr(entity, key):
                        setattr(entity, key, value)

                # No need to call session.add() since entity is already attached to session
                await session.flush()
                await session.refresh(entity)
                return entity

            except EntityNotFoundError:
                raise
            except Exception as e:
                logger.error(
                    "Error updating %s with id %s: %s",
                    self.model_class.__name__,
                    entity_id,
                    e,
                )
                raise RepositoryError(f"Error updating entity: {e}") from e

    async def delete(self, entity_id: UUID | str | int) -> bool:
        """Delete an entity."""
        async with self.get_transaction() as session:
            try:
                # Fetch entity within the transaction's session to avoid detached instances
                query = select(self.model_class).where(self.model_class.id == entity_id)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                result = await session.execute(query)
                entity = result.scalar_one_or_none()

                if not entity:
                    return False

                # Soft delete if model supports it
                if hasattr(entity, "deleted_at"):
                    entity.deleted_at = datetime.now(timezone.utc)
                    # No need to call session.add() since entity is already attached to session
                else:
                    await session.delete(entity)

                return True

            except Exception as e:
                logger.error(
                    "Error deleting %s with id %s: %s",
                    self.model_class.__name__,
                    entity_id,
                    e,
                )
                raise RepositoryError(f"Error deleting entity: {e}") from e

    async def exists(self, entity_id: UUID | str | int) -> bool:
        """Check if entity exists."""
        entity = await self.find_by_id(entity_id)
        return entity is not None

    async def count(self) -> int:
        """Count total entities."""
        async with self.get_session() as session:
            try:
                query = select(func.count()).select_from(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                result = await session.execute(query)
                return result.scalar_one()

            except Exception as e:
                logger.error("Error counting %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error counting entities: {e}") from e


class SQLAlchemyDomainRepository(SQLAlchemyRepository[ModelType], DomainRepository[ModelType]):
    """SQLAlchemy implementation with domain-specific methods."""

    async def create(self, data: dict[str, Any]) -> ModelType:
        """Create a new entity."""
        async with self.get_transaction() as session:
            try:
                # Create instance
                entity = self.model_class(**data)

                session.add(entity)
                await session.flush()
                await session.refresh(entity)

                logger.debug(
                    "Created %s with id: %s",
                    self.model_class.__name__,
                    getattr(entity, "id", "unknown"),
                )
                return entity

            except IntegrityError as e:
                logger.error("Integrity error creating %s: %s", self.model_class.__name__, e)
                raise EntityConflictError(
                    f"Entity already exists or violates constraints: {e}"
                ) from e
            except Exception as e:
                logger.error("Error creating %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error creating entity: {e}") from e

    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[ModelType]:
        """Find entities by criteria."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply criteria filters
                for key, value in criteria.items():
                    if hasattr(self.model_class, key):
                        column = getattr(self.model_class, key)
                        if isinstance(value, dict):
                            # Handle complex filters
                            for op, op_value in value.items():
                                if op == "$eq":
                                    query = query.where(column == op_value)
                                elif op == "$ne":
                                    query = query.where(column != op_value)
                                elif op == "$gt":
                                    query = query.where(column > op_value)
                                elif op == "$gte":
                                    query = query.where(column >= op_value)
                                elif op == "$lt":
                                    query = query.where(column < op_value)
                                elif op == "$lte":
                                    query = query.where(column <= op_value)
                                elif op == "$in":
                                    query = query.where(column.in_(op_value))
                                elif op == "$nin":
                                    query = query.where(~column.in_(op_value))
                        else:
                            query = query.where(column == value)

                result = await session.execute(query)
                return list(result.scalars().all())

            except Exception as e:
                logger.error("Error finding %s by criteria: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error finding entities by criteria: {e}") from e

    async def find_one_by_criteria(self, criteria: dict[str, Any]) -> ModelType | None:
        """Find single entity by criteria."""
        entities = await self.find_by_criteria(criteria)
        return entities[0] if entities else None

    async def find_with_pagination(
        self,
        criteria: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[ModelType]:
        """Find entities with advanced pagination and sorting."""
        async with self.get_session() as session:
            try:
                query = select(self.model_class)

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply criteria filters
                if criteria:
                    for key, value in criteria.items():
                        if hasattr(self.model_class, key):
                            column = getattr(self.model_class, key)
                            if isinstance(value, dict):
                                # Handle complex filters
                                for op, op_value in value.items():
                                    if op == "$eq":
                                        query = query.where(column == op_value)
                                    elif op == "$ne":
                                        query = query.where(column != op_value)
                                    elif op == "$gt":
                                        query = query.where(column > op_value)
                                    elif op == "$gte":
                                        query = query.where(column >= op_value)
                                    elif op == "$lt":
                                        query = query.where(column < op_value)
                                    elif op == "$lte":
                                        query = query.where(column <= op_value)
                                    elif op == "$in":
                                        query = query.where(column.in_(op_value))
                                    elif op == "$nin":
                                        query = query.where(~column.in_(op_value))
                            else:
                                query = query.where(column == value)

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
                logger.error("Error finding %s with pagination: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error finding entities with pagination: {e}") from e

    async def count_by_criteria(self, criteria: dict[str, Any] | None = None) -> int:
        """Count entities matching criteria."""
        async with self.get_session() as session:
            try:
                query = select(func.count(self.model_class.id))

                # Apply soft delete filter if model supports it
                if hasattr(self.model_class, "deleted_at"):
                    query = query.where(self.model_class.deleted_at.is_(None))

                # Apply criteria filters
                if criteria:
                    for key, value in criteria.items():
                        if hasattr(self.model_class, key):
                            column = getattr(self.model_class, key)
                            if isinstance(value, dict):
                                # Handle complex filters
                                for op, op_value in value.items():
                                    if op == "$eq":
                                        query = query.where(column == op_value)
                                    elif op == "$ne":
                                        query = query.where(column != op_value)
                                    elif op == "$gt":
                                        query = query.where(column > op_value)
                                    elif op == "$gte":
                                        query = query.where(column >= op_value)
                                    elif op == "$lt":
                                        query = query.where(column < op_value)
                                    elif op == "$lte":
                                        query = query.where(column <= op_value)
                                    elif op == "$in":
                                        query = query.where(column.in_(op_value))
                                    elif op == "$nin":
                                        query = query.where(~column.in_(op_value))
                            else:
                                query = query.where(column == value)

                result = await session.execute(query)
                return result.scalar_one()

            except Exception as e:
                logger.error("Error counting %s by criteria: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error counting entities by criteria: {e}") from e

    async def bulk_create(self, entities_data: list[dict[str, Any]]) -> list[ModelType]:
        """Create multiple entities in bulk."""
        async with self.get_transaction() as session:
            try:
                entities = [self.model_class(**data) for data in entities_data]
                session.add_all(entities)
                await session.flush()

                for entity in entities:
                    await session.refresh(entity)

                logger.debug(
                    "Bulk created %d %s entities",
                    len(entities),
                    self.model_class.__name__,
                )
                return entities

            except IntegrityError as e:
                logger.error("Integrity error bulk creating %s: %s", self.model_class.__name__, e)
                raise EntityConflictError(f"Bulk create violates constraints: {e}") from e
            except Exception as e:
                logger.error("Error bulk creating %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error bulk creating entities: {e}") from e

    async def bulk_update(
        self, updates: list[tuple[UUID | str | int, dict[str, Any]]]
    ) -> list[ModelType]:
        """Update multiple entities in bulk."""
        async with self.get_transaction() as session:
            try:
                updated_entities = []

                for entity_id, update_data in updates:
                    entity = await self.find_by_id(entity_id)
                    if entity:
                        for key, value in update_data.items():
                            if hasattr(entity, key):
                                setattr(entity, key, value)
                        session.add(entity)
                        updated_entities.append(entity)

                await session.flush()

                for entity in updated_entities:
                    await session.refresh(entity)

                logger.debug(
                    "Bulk updated %d %s entities",
                    len(updated_entities),
                    self.model_class.__name__,
                )
                return updated_entities

            except Exception as e:
                logger.error("Error bulk updating %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error bulk updating entities: {e}") from e

    async def bulk_delete(self, entity_ids: list[UUID | str | int]) -> int:
        """Delete multiple entities in bulk."""
        async with self.get_transaction() as session:
            try:
                deleted_count = 0

                for entity_id in entity_ids:
                    # Load entity within the transaction's session to avoid detached instances
                    entity = await session.get(self.model_class, entity_id)

                    # Skip if entity doesn't exist or is already soft-deleted
                    if entity is None:
                        continue

                    # Additional check for soft-deleted entities
                    if hasattr(entity, "deleted_at") and entity.deleted_at is not None:
                        continue

                    # Soft delete if model supports it
                    if hasattr(entity, "deleted_at"):
                        entity.deleted_at = datetime.now(timezone.utc)
                        # No need to add to session as entity is already attached
                    else:
                        await session.delete(entity)

                    deleted_count += 1

                logger.debug(
                    "Bulk deleted %d %s entities",
                    deleted_count,
                    self.model_class.__name__,
                )
                return deleted_count

            except Exception as e:
                logger.error("Error bulk deleting %s: %s", self.model_class.__name__, e)
                raise RepositoryError(f"Error bulk deleting entities: {e}") from e
