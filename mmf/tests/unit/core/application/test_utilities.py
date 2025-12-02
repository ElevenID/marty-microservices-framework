from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from mmf.core.application.utilities import (
    DatabaseUtilities,
    check_all_database_connections,
    cleanup_all_soft_deleted,
    get_database_utilities,
)
from mmf.core.domain.database import DatabaseManager


class TestDatabaseUtilities:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        # Configure async context manager for the session itself if needed
        # But usually get_session() returns a context manager that yields the session
        return session

    @pytest.fixture
    def mock_db_manager(self, mock_session):
        manager = MagicMock(spec=DatabaseManager)
        manager.service_name = "test_service"
        manager.database = "test_db"

        # Mock health_check
        manager.health_check = AsyncMock(return_value={"status": "healthy"})

        # Mock get_session to return an async context manager that yields mock_session
        # We need an object that has __aenter__ and __aexit__
        # __aenter__ should return mock_session

        session_ctx = AsyncMock()
        session_ctx.__aenter__.return_value = mock_session
        manager.get_session.return_value = session_ctx

        # Mock get_transaction similarly
        transaction_ctx = AsyncMock()
        transaction_ctx.__aenter__.return_value = mock_session
        manager.get_transaction.return_value = transaction_ctx

        return manager

    @pytest.fixture
    def db_utilities(self, mock_db_manager):
        return DatabaseUtilities(mock_db_manager)

    def test_validate_table_name_valid(self, db_utilities):
        assert db_utilities._validate_table_name("users") == "users"
        assert db_utilities._validate_table_name("public.users") == "public.users"
        assert db_utilities._validate_table_name("user_data_123") == "user_data_123"

    def test_validate_table_name_invalid(self, db_utilities):
        with pytest.raises(ValueError):
            db_utilities._validate_table_name("users; DROP TABLE users")
        with pytest.raises(ValueError):
            db_utilities._validate_table_name("users--")
        with pytest.raises(ValueError):
            db_utilities._validate_table_name("123users")  # Must start with letter or underscore

    @pytest.mark.asyncio
    async def test_check_connection(self, db_utilities, mock_db_manager):
        result = await db_utilities.check_connection()
        assert result == {"status": "healthy"}
        mock_db_manager.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_database_info_success(self, db_utilities, mock_session):
        # Setup mock return for execute
        mock_result = MagicMock()
        mock_result.scalar.return_value = "2023-01-01 12:00:00"
        mock_session.execute.return_value = mock_result

        info = await db_utilities.get_database_info()

        assert info["service_name"] == "test_service"
        assert info["database_name"] == "test_db"
        assert info["connection_status"] == "connected"
        assert info["current_timestamp"] == "2023-01-01 12:00:00"

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_database_info_error(self, db_utilities, mock_session):
        # Setup mock to raise exception
        mock_session.execute.side_effect = Exception("DB Error")

        info = await db_utilities.get_database_info()

        assert info["service_name"] == "test_service"
        assert "info_error" in info
        assert info["info_error"] == "DB Error"

    @pytest.mark.asyncio
    async def test_get_table_info_success(self, db_utilities, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute.return_value = mock_result

        info = await db_utilities.get_table_info("users")

        assert info["table_name"] == "users"
        assert info["row_count"] == 42

        # Verify the query
        args, _ = mock_session.execute.call_args
        assert 'SELECT COUNT(*) FROM "users"' in str(args[0])

    @pytest.mark.asyncio
    async def test_get_table_info_error(self, db_utilities, mock_session):
        mock_session.execute.side_effect = Exception("Table not found")

        with pytest.raises(Exception, match="Table not found"):
            await db_utilities.get_table_info("users")

    @pytest.mark.asyncio
    async def test_table_exists_true(self, db_utilities, mock_session):
        mock_session.execute.return_value = MagicMock()

        exists = await db_utilities.table_exists("users")
        assert exists is True

    @pytest.mark.asyncio
    async def test_table_exists_false(self, db_utilities, mock_session):
        mock_session.execute.side_effect = Exception("Table not found")

        exists = await db_utilities.table_exists("non_existent")
        assert exists is False

    @pytest.mark.asyncio
    async def test_truncate_table(self, db_utilities, mock_session):
        mock_session.execute.return_value = MagicMock()

        await db_utilities.truncate_table("users")

        args, _ = mock_session.execute.call_args
        assert 'DELETE FROM "users"' in str(args[0])

    @pytest.mark.asyncio
    async def test_clean_soft_deleted_success(self, db_utilities, mock_session):
        class MockModel:
            __tablename__ = "users"
            deleted_at = "some_column"

        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        count = await db_utilities.clean_soft_deleted(MockModel)

        assert count == 5
        assert mock_session.execute.call_count == 2  # One for count, one for delete

    @pytest.mark.asyncio
    async def test_clean_soft_deleted_no_records(self, db_utilities, mock_session):
        class MockModel:
            __tablename__ = "users"
            deleted_at = "some_column"

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        count = await db_utilities.clean_soft_deleted(MockModel)

        assert count == 0
        assert mock_session.execute.call_count == 1  # Only count

    @pytest.mark.asyncio
    async def test_clean_soft_deleted_no_deleted_at(self, db_utilities):
        class MockModel:
            __tablename__ = "users"
            # No deleted_at

        with pytest.raises(ValueError, match="does not support soft deletion"):
            await db_utilities.clean_soft_deleted(MockModel)

    @pytest.mark.asyncio
    async def test_backup_table_success(self, db_utilities, mock_session):
        mock_session.execute.return_value = MagicMock()

        backup_name = await db_utilities.backup_table("users", "users_backup")

        assert backup_name == "users_backup"
        args, _ = mock_session.execute.call_args
        assert 'CREATE TABLE "users_backup" AS SELECT * FROM "users"' in str(args[0])

    @pytest.mark.asyncio
    async def test_backup_table_auto_name(self, db_utilities, mock_session):
        mock_session.execute.return_value = MagicMock()

        backup_name = await db_utilities.backup_table("users")

        assert backup_name.startswith("users_backup_")
        args, _ = mock_session.execute.call_args
        assert f'CREATE TABLE "{backup_name}" AS SELECT * FROM "users"' in str(args[0])

    @pytest.mark.asyncio
    async def test_execute_maintenance(self, db_utilities, mock_session):
        mock_session.execute.return_value = MagicMock()

        results = await db_utilities.execute_maintenance(
            ["backup_users", "truncate_logs", "unknown_op"]
        )

        assert "backup_users" in results
        assert "truncate_logs" in results
        assert "unknown_op" in results
        assert results["unknown_op"] == "Unknown operation"

    @pytest.mark.asyncio
    async def test_execute_maintenance_dry_run(self, db_utilities, mock_session):
        results = await db_utilities.execute_maintenance(
            ["backup_users", "truncate_logs"], dry_run=True
        )

        assert "Would backup table users" in results["backup_users"]
        assert "Would truncate table logs" in results["truncate_logs"]
        mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_database_utilities():
    mock_manager = MagicMock(spec=DatabaseManager)
    utils = await get_database_utilities(mock_manager)
    assert isinstance(utils, DatabaseUtilities)
    assert utils.db_manager == mock_manager


@pytest.mark.asyncio
async def test_check_all_database_connections():
    mock_manager1 = MagicMock(spec=DatabaseManager)
    mock_manager1.health_check = AsyncMock(return_value={"status": "ok"})

    mock_manager2 = MagicMock(spec=DatabaseManager)
    mock_manager2.health_check = AsyncMock(side_effect=Exception("Connection failed"))

    managers = {"service1": mock_manager1, "service2": mock_manager2}

    results = await check_all_database_connections(managers)

    assert results["service1"] == {"status": "ok"}
    assert results["service2"]["status"] == "error"
    assert "Connection failed" in results["service2"]["error"]


@pytest.mark.asyncio
async def test_cleanup_all_soft_deleted():
    mock_manager = MagicMock(spec=DatabaseManager)
    session_ctx = AsyncMock()
    session = AsyncMock()
    session_ctx.__aenter__.return_value = session
    mock_manager.get_transaction.return_value = session_ctx

    # Mock count result
    mock_result = MagicMock()
    mock_result.scalar.return_value = 10
    session.execute.return_value = mock_result

    class MockModel:
        __tablename__ = "users"
        deleted_at = "col"

    managers = {"service1": mock_manager}
    models = [MockModel]

    results = await cleanup_all_soft_deleted(managers, models)

    assert results["service1"]["MockModel"] == 10
