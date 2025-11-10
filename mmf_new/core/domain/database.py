"""
Domain layer database interfaces and types.
Contains pure business logic interfaces without implementation details.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseType(Enum):
    """Supported database types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    ORACLE = "oracle"
    MSSQL = "mssql"


class IsolationLevel(Enum):
    """Database isolation levels."""

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class DatabaseError(Exception):
    """Base database error."""


class ConnectionError(DatabaseError):
    """Database connection error."""


class TransactionError(DatabaseError):
    """Database transaction error."""


class DeadlockError(TransactionError):
    """Deadlock detected error."""


class RetryableError(TransactionError):
    """Error that can be retried."""


class TransactionManager(ABC):
    """Abstract transaction manager interface."""

    @abstractmethod
    async def transaction(self, **kwargs) -> AbstractAsyncContextManager[AsyncSession]:
        """Create a managed transaction context."""
        raise NotImplementedError

    @abstractmethod
    async def retry_transaction(self, operation, max_retries: int = 3):
        """Execute an operation with retry logic."""
        raise NotImplementedError


class DatabaseManager(ABC):
    """Abstract database manager interface for domain layer."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database manager."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the database manager and clean up resources."""
        ...

    @abstractmethod
    def get_session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get a database session."""
        ...

    @abstractmethod
    def get_transaction(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Get a database session with transaction management."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database is healthy and accessible."""
        ...
