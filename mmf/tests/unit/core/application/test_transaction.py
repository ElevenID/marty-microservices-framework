from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mmf.core.application.transaction import (
    TransactionConfig,
    TransactionManager,
    execute_bulk_operations,
    execute_in_transaction,
    execute_with_savepoints,
    handle_database_errors,
    transactional,
)
from mmf.core.domain.database import (
    DatabaseManager,
    DeadlockError,
    RetryableError,
    TransactionError,
)


class AwaitableAsyncContextManager:
    """Helper for mocking objects that are both awaitable and async context managers."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def __await__(self):
        async def _ret():
            return self

        return _ret().__await__()

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)

    # Configure begin()
    tx = AwaitableAsyncContextManager(return_value=session)
    session.begin = MagicMock(return_value=tx)

    # Configure begin_nested()
    nested_tx = AwaitableAsyncContextManager(return_value=None)
    session.begin_nested = MagicMock(return_value=nested_tx)

    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def mock_db_manager(mock_session):
    manager = AsyncMock(spec=DatabaseManager)
    manager.get_session.return_value.__aenter__.return_value = mock_session
    return manager


class TestTransactionConfig:
    def test_defaults(self):
        config = TransactionConfig()
        assert config.isolation_level is None
        assert config.read_only is False
        assert config.deferrable is False
        assert config.max_retries == 3
        assert config.retry_delay == 0.1
        assert config.retry_backoff == 2.0
        assert config.timeout is None


class TestTransactionManager:
    @pytest.mark.asyncio
    async def test_transaction_success(self, mock_db_manager, mock_session):
        manager = TransactionManager(mock_db_manager)

        async with manager.transaction() as session:
            assert session == mock_session

        mock_session.begin.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, mock_db_manager, mock_session):
        manager = TransactionManager(mock_db_manager)

        with pytest.raises(ValueError):
            async with manager.transaction():
                raise ValueError("Test error")

        mock_session.begin.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_with_provided_session(self, mock_db_manager, mock_session):
        manager = TransactionManager(mock_db_manager)
        provided_session = AsyncMock(spec=AsyncSession)
        provided_session.begin = AsyncMock()
        provided_session.commit = AsyncMock()
        provided_session.rollback = AsyncMock()

        async with manager.transaction(session=provided_session) as session:
            assert session == provided_session

        provided_session.begin.assert_called_once()
        provided_session.commit.assert_called_once()
        mock_db_manager.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_managed_transaction_config(self, mock_db_manager, mock_session):
        manager = TransactionManager(mock_db_manager)
        config = TransactionConfig(isolation_level="SERIALIZABLE", read_only=True, deferrable=True)

        async with manager.transaction(config=config):
            pass

        assert mock_session.execute.call_count == 3
        # Check calls arguments
        calls = mock_session.execute.call_args_list
        # calls[0][0][0] is the first positional argument of the first call, which is the TextClause
        assert "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE" in str(calls[0][0][0])
        assert "SET TRANSACTION READ ONLY" in str(calls[1][0][0])
        assert "SET TRANSACTION DEFERRABLE" in str(calls[2][0][0])

    @pytest.mark.asyncio
    async def test_retry_transaction_success(self, mock_db_manager):
        manager = TransactionManager(mock_db_manager)
        func = AsyncMock(return_value="success")

        result = await manager.retry_transaction(func)

        assert result == "success"
        func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_transaction_retryable_error(self, mock_db_manager):
        manager = TransactionManager(mock_db_manager)
        func = AsyncMock(side_effect=[RetryableError("Retry"), "success"])

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await manager.retry_transaction(func)

        assert result == "success"
        assert func.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_transaction_max_retries_exceeded(self, mock_db_manager):
        manager = TransactionManager(mock_db_manager)
        func = AsyncMock(side_effect=RetryableError("Retry"))
        config = TransactionConfig(max_retries=2, retry_delay=0.01)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryableError):
                await manager.retry_transaction(func, config=config)

        assert func.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_transaction_non_retryable_error(self, mock_db_manager):
        manager = TransactionManager(mock_db_manager)
        func = AsyncMock(side_effect=ValueError("Fatal"))

        with pytest.raises(ValueError):
            await manager.retry_transaction(func)

        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_bulk_transaction(self, mock_db_manager):
        manager = TransactionManager(mock_db_manager)
        op1 = AsyncMock(return_value=1)
        op2 = AsyncMock(return_value=2)

        results = await manager.bulk_transaction([op1, op2])

        assert results == [1, 2]
        op1.assert_called_once()
        op2.assert_called_once()

    @pytest.mark.asyncio
    async def test_savepoint_transaction(self, mock_db_manager, mock_session):
        manager = TransactionManager(mock_db_manager)
        op1 = AsyncMock(return_value=1)
        op2 = AsyncMock(side_effect=ValueError("Fail"))
        op3 = AsyncMock(return_value=3)

        # Get the nested mock from the fixture
        nested_mock = mock_session.begin_nested.return_value

        results = await manager.savepoint_transaction([op1, op2, op3])

        assert results == [1, None, 3]
        assert nested_mock.commit.call_count == 2  # op1 and op3
        assert nested_mock.rollback.call_count == 1  # op2


class TestDecorators:
    @pytest.mark.asyncio
    async def test_transactional_decorator(self, mock_db_manager):
        @transactional()
        async def my_func(db_manager=None):
            return "success"

        result = await my_func(db_manager=mock_db_manager)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_transactional_decorator_missing_manager(self):
        @transactional()
        async def my_func():
            pass

        with pytest.raises(ValueError, match="No database manager found"):
            await my_func()

    @pytest.mark.asyncio
    async def test_handle_database_errors_integrity(self):
        @handle_database_errors
        async def my_func():
            raise IntegrityError("statement", "params", "orig")

        with pytest.raises(TransactionError, match="Data integrity violation"):
            await my_func()

    @pytest.mark.asyncio
    async def test_handle_database_errors_deadlock(self):
        @handle_database_errors
        async def my_func():
            raise SQLAlchemyError("deadlock detected")

        with pytest.raises(DeadlockError):
            await my_func()

    @pytest.mark.asyncio
    async def test_handle_database_errors_connection(self):
        @handle_database_errors
        async def my_func():
            raise SQLAlchemyError("connection timeout")

        with pytest.raises(RetryableError):
            await my_func()


class TestUtilityFunctions:
    @pytest.mark.asyncio
    async def test_execute_in_transaction(self, mock_db_manager):
        func = AsyncMock(return_value="success")
        result = await execute_in_transaction(mock_db_manager, func)
        assert result == "success"
        func.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_bulk_operations(self, mock_db_manager):
        op1 = AsyncMock(return_value=1)
        results = await execute_bulk_operations(mock_db_manager, [op1])
        assert results == [1]

    @pytest.mark.asyncio
    async def test_execute_with_savepoints(self, mock_db_manager, mock_session):
        op1 = AsyncMock(return_value=1)

        results = await execute_with_savepoints(mock_db_manager, [op1])
        assert results == [1]
