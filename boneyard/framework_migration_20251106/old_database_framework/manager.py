"""
Dfrom contextlib import AbstractAsyncContextManager, AsyncContextManager, asynccontextmanager
from typing import Any, Dict, Optional, Setabase manager for the enterprise database framework.
"""

import asyncio
import builtins
import logging
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from mmf_new.core.infrastructure.database import BaseModel
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base database error."""


class ConnectionError(DatabaseError):
    """Database connection error."""


class DatabaseManager:
    """Manages database connections and sessions for a service."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.config.validate()
        self._async_engine: AsyncEngine | None = None
        self._sync_engine = None
        self._async_session_factory: async_sessionmaker | None = None
        self._sync_session_factory = None
        self._initialized = False
        self._health_check_query = self._get_health_check_query()

    async def initialize(self) -> None:
        """Initialize the database manager."""
        if self._initialized:
            return
        try:
            # Create async engine
            self._async_engine = create_async_engine(
                self.config.connection_url,
                pool_size=self.config.pool_config.max_size,
                max_overflow=self.config.pool_config.max_overflow,
                pool_timeout=self.config.pool_config.pool_timeout,
                pool_recycle=self.config.pool_config.pool_recycle,
                pool_pre_ping=self.config.pool_config.pool_pre_ping,
                echo=self.config.pool_config.echo,
                echo_pool=self.config.pool_config.echo_pool,
                poolclass=QueuePool,
            )
            # Create sync engine for migrations and admin tasks
            self._sync_engine = create_engine(
                self.config.sync_connection_url,
                pool_size=self.config.pool_config.max_size,
                max_overflow=self.config.pool_config.max_overflow,
                pool_timeout=self.config.pool_config.pool_timeout,
                pool_recycle=self.config.pool_config.pool_recycle,
                pool_pre_ping=self.config.pool_config.pool_pre_ping,
                echo=self.config.pool_config.echo,
                echo_pool=self.config.pool_config.echo_pool,
                poolclass=QueuePool,
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
            # Set up event listeners
            self._setup_event_listeners()
            # Test connection
            await self.health_check()
            self._initialized = True
            logger.info("Database manager initialized for service: %s", self.config.service_name)
        except Exception as e:
            logger.error("Failed to initialize database manager: %s", e)
            raise ConnectionError(f"Failed to initialize database: {e}") from e

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners."""

        @event.listens_for(self._async_engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for performance and integrity."""
            if "sqlite" in self.config.connection_url:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        @event.listens_for(self._async_engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Handle connection checkout."""
            logger.debug("Database connection checked out for %s", self.config.service_name)

        @event.listens_for(self._async_engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Handle connection checkin."""
            logger.debug("Database connection checked in for %s", self.config.service_name)

    async def close(self) -> None:
        """Close all database connections."""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                self._async_engine = None
            if self._sync_engine:
                self._sync_engine.dispose()
                self._sync_engine = None
            self._async_session_factory = None
            self._sync_session_factory = None
            self._initialized = False
            logger.info("Database manager closed for service: %s", self.config.service_name)
        except Exception as e:
            logger.error("Error closing database manager: %s", e)
            raise

    @asynccontextmanager
    async def get_session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get an async database session."""
        if not self._initialized:
            await self.initialize()
        if not self._async_session_factory:
            raise DatabaseError("Database not initialized")
        session = self._async_session_factory()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error: %s", e)
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def get_transaction(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get an async database session with automatic transaction management."""
        async with self.get_session() as session:
            async with session.begin():
                yield session

    def get_sync_session(self) -> Session:
        """Get a synchronous database session (for migrations, admin tasks)."""
        if not self._sync_session_factory:
            raise DatabaseError("Database not initialized")
        return self._sync_session_factory()

    async def health_check(self) -> builtins.dict[str, Any]:
        """Perform a database health check."""
        try:
            start_time = asyncio.get_event_loop().time()
            async with self.get_session() as session:
                result = await session.execute(text(self._health_check_query))
                await result.fetchone()
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            return {
                "status": "healthy",
                "service": self.config.service_name,
                "database": self.config.database,
                "response_time_ms": round(response_time, 2),
                "connection_url": self._mask_connection_url(),
            }
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return {
                "status": "unhealthy",
                "service": self.config.service_name,
                "database": self.config.database,
                "error": str(e),
                "connection_url": self._mask_connection_url(),
            }

    async def create_tables(self, metadata=None) -> None:
        """Create all tables defined in the metadata."""
        if not self._initialized:
            await self.initialize()
        target_metadata = metadata or BaseModel.metadata
        try:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(target_metadata.create_all)
            logger.info("Database tables created for service: %s", self.config.service_name)
        except Exception as e:
            logger.error("Failed to create tables: %s", e)
            raise DatabaseError(f"Failed to create tables: {e}") from e

    async def drop_tables(self, metadata=None) -> None:
        """Drop all tables defined in the metadata."""
        if not self._initialized:
            await self.initialize()
        target_metadata = metadata or BaseModel.metadata
        try:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(target_metadata.drop_all)
            logger.info("Database tables dropped for service: %s", self.config.service_name)
        except Exception as e:
            logger.error("Failed to drop tables: %s", e)
            raise DatabaseError(f"Failed to drop tables: {e}") from e

    async def execute_raw_sql(self, sql: str, params: builtins.dict[str, Any] | None = None) -> Any:
        """Execute raw SQL."""
        async with self.get_session() as session:
            result = await session.execute(text(sql), params or {})
            await session.commit()
            return result

    def _get_health_check_query(self) -> str:
        """Get appropriate health check query for the database type."""
        query_map = {
            "postgresql": "SELECT 1",
            "mysql": "SELECT 1",
            "sqlite": "SELECT 1",
            "oracle": "SELECT 1 FROM DUAL",
            "mssql": "SELECT 1",
        }
        return query_map.get(self.config.db_type.value, "SELECT 1")

    def _mask_connection_url(self) -> str:
        """Get connection URL with masked password."""
        url = self.config.connection_url
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                auth, host_part = rest.split("@", 1)
                if ":" in auth:
                    user, _ = auth.split(":", 1)
                    masked_auth = f"{user}:***"
                else:
                    masked_auth = auth
                return f"{scheme}://{masked_auth}@{host_part}"
        return url

    @property
    def is_initialized(self) -> bool:
        """Check if the database manager is initialized."""
        return self._initialized

    @property
    def engine(self) -> AsyncEngine:
        """Get the async engine."""
        if not self._async_engine:
            raise DatabaseError("Database not initialized")
        return self._async_engine

    @property
    def sync_engine(self):
        """Get the sync engine."""
        if not self._sync_engine:
            raise DatabaseError("Database not initialized")
        return self._sync_engine


# Global database managers registry
_database_managers: builtins.dict[str, DatabaseManager] = {}


def get_database_manager(service_name: str) -> DatabaseManager:
    """Get or create a database manager for a service."""
    if service_name not in _database_managers:
        # Try to create from environment
        config = DatabaseConfig.from_environment(service_name)
        _database_managers[service_name] = DatabaseManager(config)
    return _database_managers[service_name]


def create_database_manager(config: DatabaseConfig) -> DatabaseManager:
    """Create and register a database manager."""
    manager = DatabaseManager(config)
    _database_managers[config.service_name] = manager
    return manager


def register_database_manager(service_name: str, manager: DatabaseManager) -> None:
    """Register a database manager."""
    _database_managers[service_name] = manager


async def close_all_database_managers() -> None:
    """Close all registered database managers."""
    for manager in _database_managers.values():
        await manager.close()
    _database_managers.clear()


async def health_check_all_databases() -> builtins.dict[str, builtins.dict[str, Any]]:
    """Perform health checks on all registered databases."""
    results = {}
    for service_name, manager in _database_managers.items():
        results[service_name] = await manager.health_check()
    return results
