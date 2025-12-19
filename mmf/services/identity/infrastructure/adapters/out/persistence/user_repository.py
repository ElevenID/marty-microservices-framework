"""Concrete repository implementation for the identity service."""

import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select

from mmf.core.domain.ports.repository import Repository
from mmf.services.identity.domain.models.authenticated_user import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters.out.persistence.models import (
    AuthenticatedUserModel,
)

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../src"))


class AuthenticatedUserRepository(Repository[AuthenticatedUser]):
    """Repository for managing authenticated user data.

    This repository implements the domain repository interface
    using the existing framework's database infrastructure.
    """

    def __init__(self, db_manager: Any):
        """Initialize repository with database manager.

        Args:
            db_manager: Database manager for connection handling
        """
        self.db_manager = db_manager

    async def save(self, entity: AuthenticatedUser) -> AuthenticatedUser:
        """Save an authenticated user entity."""
        async with self.db_manager.get_transaction() as session:
            model = AuthenticatedUserModel(
                user_id=entity.user_id,
                username=entity.username,
                email=entity.email,
                roles=list(entity.roles),
                permissions=list(entity.permissions),
                session_id=entity.session_id,
                auth_method=entity.auth_method,
                expires_at=entity.expires_at,
                metadata_=entity.metadata,
                created_at=entity.created_at,
            )
            await session.merge(model)
            return entity

    async def find_by_id(self, entity_id: UUID | str) -> AuthenticatedUser | None:
        """Find authenticated user by ID."""
        id_str = str(entity_id)
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(
                select(AuthenticatedUserModel).where(AuthenticatedUserModel.user_id == id_str)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            return AuthenticatedUser(**model.to_dict())

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[AuthenticatedUser]:
        """Find all authenticated users with pagination."""
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(select(AuthenticatedUserModel).offset(skip).limit(limit))
            models = result.scalars().all()
            return [AuthenticatedUser(**model.to_dict()) for model in models]

    async def update(
        self, entity_id: UUID | str | int, updates: dict[str, Any]
    ) -> AuthenticatedUser | None:
        """Update an authenticated user entity."""
        id_str = str(entity_id)
        async with self.db_manager.get_transaction() as session:
            # First check if exists
            result = await session.execute(
                select(AuthenticatedUserModel).where(AuthenticatedUserModel.user_id == id_str)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            # Update fields
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)
                elif key == "metadata":
                    model.metadata_ = value

            await session.merge(model)
            return AuthenticatedUser(**model.to_dict())

    async def delete(self, entity_id: UUID | str) -> bool:
        """Delete an authenticated user by ID."""
        id_str = str(entity_id)
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(
                delete(AuthenticatedUserModel).where(AuthenticatedUserModel.user_id == id_str)
            )
            return result.rowcount > 0

    async def exists(self, entity_id: UUID | str) -> bool:
        """Check if an authenticated user exists."""
        id_str = str(entity_id)
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(
                select(AuthenticatedUserModel.user_id).where(
                    AuthenticatedUserModel.user_id == id_str
                )
            )
            return result.first() is not None

    async def count(self) -> int:
        """Count total number of authenticated users."""
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(select(func.count(AuthenticatedUserModel.user_id)))
            return result.scalar() or 0

    async def find_by_username(self, username: str) -> AuthenticatedUser | None:
        """Find authenticated user by username."""
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(
                select(AuthenticatedUserModel).where(AuthenticatedUserModel.username == username)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            return AuthenticatedUser(**model.to_dict())

    async def find_by_session_id(self, session_id: str) -> AuthenticatedUser | None:
        """Find authenticated user by session ID."""
        async with self.db_manager.get_transaction() as session:
            result = await session.execute(
                select(AuthenticatedUserModel).where(
                    AuthenticatedUserModel.session_id == session_id
                )
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            return AuthenticatedUser(**model.to_dict())
