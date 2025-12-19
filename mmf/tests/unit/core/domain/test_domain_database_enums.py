from contextlib import AbstractAsyncContextManager

import pytest

from mmf.core.domain.database import (
    ConnectionError,
    DatabaseError,
    DatabaseManager,
    DatabaseType,
    DeadlockError,
    IsolationLevel,
    RetryableError,
    TransactionError,
    TransactionManager,
)


class TestEnums:
    def test_database_type(self):
        assert DatabaseType.POSTGRESQL.value == "postgresql"
        assert DatabaseType.MYSQL.value == "mysql"
        assert DatabaseType.SQLITE.value == "sqlite"

    def test_isolation_level(self):
        assert IsolationLevel.READ_UNCOMMITTED.value == "READ UNCOMMITTED"
        assert IsolationLevel.SERIALIZABLE.value == "SERIALIZABLE"


class TestExceptions:
    def test_inheritance(self):
        assert issubclass(ConnectionError, DatabaseError)
        assert issubclass(TransactionError, DatabaseError)
        assert issubclass(DeadlockError, TransactionError)
        assert issubclass(RetryableError, TransactionError)


class TestInterfaces:
    def test_transaction_manager_is_abstract(self):
        with pytest.raises(TypeError):
            TransactionManager()

    def test_database_manager_is_abstract(self):
        with pytest.raises(TypeError):
            DatabaseManager()

    class ConcreteTransactionManager(TransactionManager):
        async def transaction(self, **kwargs):
            pass

        async def retry_transaction(self, operation, max_retries: int = 3):
            pass

    class ConcreteDatabaseManager(DatabaseManager):
        async def initialize(self) -> None:
            pass

        async def close(self) -> None:
            pass

        def get_session(self):
            pass

        def get_transaction(self):
            pass

        async def health_check(self) -> bool:
            return True

    def test_concrete_implementation(self):
        mgr = self.ConcreteTransactionManager()
        assert isinstance(mgr, TransactionManager)

        db_mgr = self.ConcreteDatabaseManager()
        assert isinstance(db_mgr, DatabaseManager)
