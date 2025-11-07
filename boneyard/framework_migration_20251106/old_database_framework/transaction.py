"""
Transaction management utilities for the enterprise database framework.
"""

import asyncio
import builtins
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .manager import DatabaseManager

logger = logging.getLogger(__name__)
T = TypeVar("T")


class IsolationLevel(Enum):
    """Database isolation levels."""

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class TransactionError(Exception):
    """Base transaction error."""


class DeadlockError(TransactionError):
    """Deadlock detected error."""


class RetryableError(TransactionError):
    """Error that can be retried."""


@dataclass
class TransactionConfig:
    """Transaction configuration."""

    isolation_level: IsolationLevel | None = None
    read_only: bool = False
    deferrable: bool = False
    max_retries: int = 3
    retry_delay: float = 0.1
    retry_backoff: float = 2.0
    timeout: float | None = None


class TransactionManager:
    """Manages database transactions with retry logic and error handling."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._active_transactions: builtins.dict[str, AsyncSession] = {}

    @asynccontextmanager
    async def transaction(
        self,
        config: TransactionConfig | None = None,
        session: AsyncSession | None = None,
    ):
        """Create a managed transaction context."""
        config = config or TransactionConfig()
        if session:
            # Use provided session
            async with self._managed_transaction(session, config):
                yield session
        else:
            # Create new session
            async with self.db_manager.get_session() as new_session:
                async with self._managed_transaction(new_session, config):
                    yield new_session

    @asynccontextmanager
    async def _managed_transaction(self, session: AsyncSession, config: TransactionConfig):
        """Internal managed transaction with configuration."""
        transaction_id = id(session)
        try:
            # Set transaction configuration
            if config.isolation_level:
                await session.execute(
                    text(f"SET TRANSACTION ISOLATION LEVEL {config.isolation_level.value}")
                )
            if config.read_only:
                await session.execute(text("SET TRANSACTION READ ONLY"))
            if config.deferrable:
                await session.execute(text("SET TRANSACTION DEFERRABLE"))
            # Set timeout if specified
            if config.timeout:
                await asyncio.wait_for(session.begin(), timeout=config.timeout)
            else:
                await session.begin()
            self._active_transactions[str(transaction_id)] = session
            yield session
            # Commit the transaction
            await session.commit()
            logger.debug("Transaction %s committed successfully", transaction_id)
        except Exception as e:
            # Rollback on any error
            try:
                await session.rollback()
                logger.debug("Transaction %s rolled back due to error: %s", transaction_id, e)
            except Exception as rollback_error:
                logger.error("Error during rollback: %s", rollback_error)
            raise
        finally:
            # Clean up
            self._active_transactions.pop(str(transaction_id), None)

    async def retry_transaction(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        config: TransactionConfig | None = None,
        **kwargs,
    ) -> T:
        """Execute a function in a transaction with retry logic."""
        config = config or TransactionConfig()
        last_exception = None
        for attempt in range(config.max_retries + 1):
            try:
                async with self.transaction(config) as session:
                    # Add session to kwargs if the function expects it
                    if "session" in func.__code__.co_varnames:
                        kwargs["session"] = session
                    result = await func(*args, **kwargs)
                    return result
            except (DeadlockError, RetryableError) as e:
                last_exception = e
                if attempt < config.max_retries:
                    delay = config.retry_delay * (config.retry_backoff**attempt)
                    logger.warning(
                        "Transaction attempt %d failed with retryable error: %s. "
                        "Retrying in %.2f seconds...",
                        attempt + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("Transaction failed after %d attempts", config.max_retries + 1)
                raise
            except Exception as e:
                # Non-retryable error
                logger.error("Transaction failed with non-retryable error: %s", e)
                raise
        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        raise TransactionError("Transaction failed for unknown reason")

    async def bulk_transaction(
        self,
        operations: builtins.list[Callable[..., Awaitable[Any]]],
        config: TransactionConfig | None = None,
    ) -> builtins.list[Any]:
        """Execute multiple operations in a single transaction."""
        config = config or TransactionConfig()
        results = []
        async with self.transaction(config) as session:
            for operation in operations:
                # Add session to the operation if it expects it
                if hasattr(operation, "__code__") and "session" in operation.__code__.co_varnames:
                    result = await operation(session=session)
                else:
                    result = await operation()
                results.append(result)
        return results

    async def savepoint_transaction(
        self,
        operations: builtins.list[Callable[..., Awaitable[Any]]],
        savepoint_names: builtins.list[str] | None = None,
    ) -> builtins.list[Any]:
        """Execute operations with savepoints for partial rollback."""
        if savepoint_names and len(savepoint_names) != len(operations):
            raise ValueError("Number of savepoint names must match number of operations")
        results = []
        async with self.db_manager.get_session() as session:
            async with session.begin():
                for i, operation in enumerate(operations):
                    savepoint_name = savepoint_names[i] if savepoint_names else f"sp_{i}"
                    # Create savepoint
                    savepoint = await session.begin_nested()
                    try:
                        # Execute operation
                        if (
                            hasattr(operation, "__code__")
                            and "session" in operation.__code__.co_varnames
                        ):
                            result = await operation(session=session)
                        else:
                            result = await operation()
                        results.append(result)
                        logger.debug("Savepoint %s completed successfully", savepoint_name)
                    except Exception as e:
                        # Rollback to savepoint
                        await savepoint.rollback()
                        logger.warning(
                            "Rolled back to savepoint %s due to error: %s",
                            savepoint_name,
                            e,
                        )
                        # Add None result to maintain order
                        results.append(None)
                        # Decide whether to continue or re-raise
                        # For now, we continue with other operations
                        continue
        return results

    def get_active_transactions(self) -> builtins.dict[str, str]:
        """Get information about active transactions."""
        return {
            transaction_id: f"Session {id(session)}"
            for transaction_id, session in self._active_transactions.items()
        }


def transactional(config: TransactionConfig | None = None, retry: bool = True):
    """Decorator for automatic transaction management."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Try to find database manager in args/kwargs
            db_manager = None
            # Look for db_manager in kwargs
            if "db_manager" in kwargs:
                db_manager = kwargs["db_manager"]
            # Look for self with db_manager attribute
            elif (args and hasattr(args[0], "db_manager")) or (
                args and hasattr(args[0], "db_manager")
            ):
                db_manager = args[0].db_manager
            if not db_manager:
                raise ValueError("No database manager found for transactional decorator")
            transaction_manager = TransactionManager(db_manager)
            if retry:
                return await transaction_manager.retry_transaction(
                    func, *args, config=config, **kwargs
                )
            async with transaction_manager.transaction(config) as session:
                # Add session to kwargs if not already present
                if "session" not in kwargs and "session" in func.__code__.co_varnames:
                    kwargs["session"] = session
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def handle_database_errors(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Decorator for handling common database errors."""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except IntegrityError as e:
            logger.error("Integrity constraint violation: %s", e)
            raise TransactionError(f"Data integrity violation: {e}") from e
        except DataError as e:
            logger.error("Data error: %s", e)
            raise TransactionError(f"Invalid data: {e}") from e
        except SQLAlchemyError as e:
            error_message = str(e).lower()
            # Check for deadlock
            if any(keyword in error_message for keyword in ["deadlock", "lock timeout"]):
                logger.warning("Deadlock detected: %s", e)
                raise DeadlockError(f"Database deadlock: {e}") from e
            # Check for connection issues
            if any(keyword in error_message for keyword in ["connection", "timeout", "network"]):
                logger.error("Connection error: %s", e)
                raise RetryableError(f"Database connection error: {e}") from e
            # Generic SQLAlchemy error
            logger.error("Database error: %s", e)
            raise TransactionError(f"Database error: {e}") from e
        except Exception as e:
            logger.error("Unexpected error in database operation: %s", e)
            raise

    return wrapper


# Utility functions
async def execute_in_transaction(
    db_manager: DatabaseManager,
    func: Callable[..., Awaitable[T]],
    *args,
    config: TransactionConfig | None = None,
    **kwargs,
) -> T:
    """Execute a function in a transaction."""
    transaction_manager = TransactionManager(db_manager)
    return await transaction_manager.retry_transaction(func, *args, config=config, **kwargs)


async def execute_bulk_operations(
    db_manager: DatabaseManager,
    operations: builtins.list[Callable[..., Awaitable[Any]]],
    config: TransactionConfig | None = None,
) -> builtins.list[Any]:
    """Execute multiple operations in a single transaction."""
    transaction_manager = TransactionManager(db_manager)
    return await transaction_manager.bulk_transaction(operations, config)


async def execute_with_savepoints(
    db_manager: DatabaseManager,
    operations: builtins.list[Callable[..., Awaitable[Any]]],
    savepoint_names: builtins.list[str] | None = None,
) -> builtins.list[Any]:
    """Execute operations with savepoints."""
    transaction_manager = TransactionManager(db_manager)
    return await transaction_manager.savepoint_transaction(operations, savepoint_names)
