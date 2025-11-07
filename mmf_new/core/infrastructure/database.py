"""Database infrastructure components for the new core architecture."""

import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..application.database import DatabaseConfig
from ..domain.database import ConnectionError, DatabaseError
from ..domain.database import DatabaseManager as AbstractDatabaseManager

logger = logging.getLogger(__name__)


# Create a proper declarative base
class _DeclarativeBase(DeclarativeBase):
    """Internal declarative base class."""

    pass


class BaseModel(_DeclarativeBase):
    """Base model class for all database models (new structure)."""

    __abstract__ = (
        True  # This makes it abstract so SQLAlchemy won't try to create a table
    )

    def to_dict(self, include_relationships: bool = False) -> dict[str, Any]:
        """Convert model instance to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            result[column.name] = value
        return result


class DatabaseManager(AbstractDatabaseManager):
    """Concrete database manager implementation using SQLAlchemy."""

    def __init__(self, config: DatabaseConfig):
        """Initialize database manager with configuration."""
        self.config = config
        self._async_engine: AsyncEngine | None = None
        self._sync_engine = None
        self._async_session_factory = None
        self._sync_session_factory = None

    async def initialize(self) -> None:
        """Initialize the database manager."""
        try:
            # Create async engine
            self._async_engine = create_async_engine(
                self.config.connection_url,
                echo=self.config.pool_config.echo,
                pool_size=self.config.pool_config.min_size,
                max_overflow=self.config.pool_config.max_overflow,
                pool_timeout=self.config.pool_config.pool_timeout,
                pool_recycle=self.config.pool_config.pool_recycle,
                pool_pre_ping=self.config.pool_config.pool_pre_ping,
            )

            # Create sync engine for utilities
            self._sync_engine = create_engine(
                self.config.sync_connection_url,
                echo=self.config.pool_config.echo,
                pool_size=self.config.pool_config.min_size,
                max_overflow=self.config.pool_config.max_overflow,
                pool_timeout=self.config.pool_config.pool_timeout,
                pool_recycle=self.config.pool_config.pool_recycle,
                pool_pre_ping=self.config.pool_config.pool_pre_ping,
            )

            # Create session factories
            self._async_session_factory = async_sessionmaker(
                self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            self._sync_session_factory = sessionmaker(
                self._sync_engine,
                class_=Session,
                expire_on_commit=False,
            )

            logger.info(
                "Database manager initialized for service: %s", self.config.service_name
            )

        except Exception as e:
            logger.error("Failed to initialize database manager: %s", e)
            raise ConnectionError(f"Database initialization failed: {e}") from e

    async def close(self) -> None:
        """Close the database manager and clean up resources."""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                self._async_engine = None

            if self._sync_engine:
                self._sync_engine.dispose()
                self._sync_engine = None

            self._async_session_factory = None
            self._sync_session_factory = None

            logger.info(
                "Database manager closed for service: %s", self.config.service_name
            )

        except Exception as e:
            logger.error("Error closing database manager: %s", e)
            raise DatabaseError(f"Database cleanup failed: {e}") from e

    @asynccontextmanager
    async def get_session(self):
        """Get a database session."""
        if not self._async_session_factory:
            raise DatabaseError("Database manager not initialized")

        async with self._async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_transaction(self):
        """Get a database session with transaction management."""
        async with self.get_session() as session:
            async with session.begin():
                yield session

    async def health_check(self) -> bool:
        """Check if database is healthy and accessible."""
        if not self._async_engine:
            return False

        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.warning("Database health check failed: %s", e)
            return False

    @classmethod
    def from_url(
        cls, service_name: str, database_url: str, **kwargs
    ) -> "DatabaseManager":
        """Create database manager from URL string."""
        parsed = urlparse(database_url)

        # Create config from URL components
        config = DatabaseConfig(
            service_name=service_name,
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "postgres",
            username=parsed.username or "postgres",
            password=parsed.password or "",
            **kwargs,
        )

        return cls(config)

    @property
    def sync_engine(self):
        """Get the synchronous engine for utilities."""
        return self._sync_engine

    @property
    def engine(self):
        """Get the async engine."""
        return self._async_engine


# Backwards compatibility aliases
CoreDatabaseManager = DatabaseManager


# Re-export database errors
class TransactionError(DatabaseError):
    """Database transaction error."""


class QueryError(DatabaseError):
    """Database query error."""
