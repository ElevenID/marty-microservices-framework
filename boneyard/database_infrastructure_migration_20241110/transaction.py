"""Transaction management implementation for the infrastructure layer."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.database import TransactionConfig
from ..domain.database import (
    DeadlockError,
    RetryableError,
    TransactionError,
)
from ..domain.database import TransactionManager as AbstractTransactionManager

logger = logging.getLogger(__name__)
T = TypeVar("T")


class SQLAlchemyTransactionManager(AbstractTransactionManager):
    """SQLAlchemy implementation of transaction manager."""

    def __init__(self, session_factory):
        """Initialize transaction manager with session factory."""
        self.session_factory = session_factory
        self._active_transactions: dict[int, AsyncSession] = {}

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
            async with self.session_factory() as new_session:
                async with self._managed_transaction(new_session, config):
                    yield new_session

    @asynccontextmanager
    async def _managed_transaction(
        self, session: AsyncSession, config: TransactionConfig
    ):
        """Internal managed transaction with configuration."""
        transaction_id = id(session)
        self._active_transactions[transaction_id] = session

        try:
            # Begin transaction
            if config.timeout:
                await asyncio.wait_for(session.begin(), timeout=config.timeout)
            else:
                await session.begin()

            # Set transaction configuration
            if config.isolation_level:
                await session.execute(
                    text(
                        f"SET TRANSACTION ISOLATION LEVEL {config.isolation_level.value}"
                    )
                )
            if config.read_only:
                await session.execute(text("SET TRANSACTION READ ONLY"))
            if config.deferrable:
                await session.execute(text("SET TRANSACTION DEFERRABLE"))

            yield session
            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error("Transaction rolled back: %s", e)

            # Classify errors for retry logic
            if isinstance(e, IntegrityError):
                raise TransactionError(f"Integrity constraint violation: {e}") from e
            elif isinstance(e, DataError):
                raise TransactionError(f"Data error: {e}") from e
            elif "deadlock" in str(e).lower():
                raise DeadlockError(f"Deadlock detected: {e}") from e
            elif isinstance(e, SQLAlchemyError):
                if _is_retryable_error(e):
                    raise RetryableError(f"Retryable database error: {e}") from e
                else:
                    raise TransactionError(f"Database error: {e}") from e
            else:
                raise TransactionError(f"Transaction failed: {e}") from e

        finally:
            self._active_transactions.pop(transaction_id, None)

    async def retry_transaction(
        self,
        operation: Callable[..., Any],
        config: TransactionConfig | None = None,
        *args,
        **kwargs,
    ) -> Any:
        """Execute an operation with retry logic."""
        config = config or TransactionConfig()
        last_error = None

        for attempt in range(config.max_retries + 1):
            try:
                async with self.transaction(config) as session:
                    return await operation(session, *args, **kwargs)

            except RetryableError as e:
                last_error = e
                if attempt < config.max_retries:
                    delay = config.retry_delay * (config.retry_backoff**attempt)
                    logger.warning(
                        "Transaction attempt %d failed, retrying in %fs: %s",
                        attempt + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        "Transaction failed after %d attempts: %s",
                        config.max_retries + 1,
                        e,
                    )
                    break

            except (TransactionError, DeadlockError) as e:
                # These errors should not be retried
                logger.error("Non-retryable transaction error: %s", e)
                raise

        # If we get here, all retries were exhausted
        raise TransactionError(
            f"Transaction failed after {config.max_retries + 1} attempts"
        ) from last_error


def _is_retryable_error(error: SQLAlchemyError) -> bool:
    """Determine if a SQLAlchemy error is retryable."""
    error_msg = str(error).lower()

    # Common retryable error patterns
    retryable_patterns = [
        "connection lost",
        "connection closed",
        "connection timed out",
        "server has gone away",
        "connection reset",
        "connection aborted",
        "temporary failure",
        "timeout",
    ]

    return any(pattern in error_msg for pattern in retryable_patterns)


# Factory function for easy instantiation
def create_transaction_manager(session_factory) -> SQLAlchemyTransactionManager:
    """Create a transaction manager with the given session factory."""
    return SQLAlchemyTransactionManager(session_factory)
