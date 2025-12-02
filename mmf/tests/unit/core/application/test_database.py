import os
from unittest.mock import MagicMock, patch

import pytest

from mmf.core.application.database import (
    ConnectionPoolConfig,
    DatabaseConfig,
    DatabaseType,
    TransactionConfig,
)


class TestConnectionPoolConfig:
    def test_defaults(self):
        config = ConnectionPoolConfig()
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.max_overflow == 20
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.echo is False
        assert config.echo_pool is False


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


class TestDatabaseConfig:
    def test_initialization(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
        )
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "test_db"
        assert config.username == "user"
        assert config.password == "password"  # pragma: allowlist secret
        assert config.service_name == "test-service"
        assert config.db_type == DatabaseType.POSTGRESQL
        assert isinstance(config.pool_config, ConnectionPoolConfig)

    def test_connection_url_postgres(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.POSTGRESQL,
            service_name="test-service",
        )
        url = config.connection_url
        assert url.startswith(
            "postgresql+asyncpg://user:password@localhost:5432/test_db"  # pragma: allowlist secret
        )
        assert "options=-c timezone=UTC" in url

    def test_connection_url_mysql(self):
        config = DatabaseConfig(
            host="localhost",
            port=3306,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.MYSQL,
            service_name="test-service",
        )
        url = config.connection_url
        assert (
            url
            == "mysql+aiomysql://user:password@localhost:3306/test_db"  # pragma: allowlist secret
        )

    def test_connection_url_sqlite(self):
        config = DatabaseConfig(
            host="",
            port=0,
            database="test.db",
            username="",
            password="",
            db_type=DatabaseType.SQLITE,
            service_name="test-service",
        )
        url = config.connection_url
        assert url == "sqlite+aiosqlite:///test.db"

    def test_connection_url_with_ssl(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
            ssl_mode="require",
            ssl_cert="/path/to/cert",
            ssl_key="/path/to/key",
            ssl_ca="/path/to/ca",
        )
        url = config.connection_url
        assert "sslmode=require" in url
        assert "sslcert=/path/to/cert" in url
        assert "sslkey=/path/to/key" in url
        assert "sslrootcert=/path/to/ca" in url

    def test_sync_connection_url_postgres(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.POSTGRESQL,
            service_name="test-service",
        )
        url = config.sync_connection_url
        assert url.startswith(
            "postgresql+psycopg2://user:password@localhost:5432/test_db"  # pragma: allowlist secret
        )

    def test_connection_url_oracle(self):
        config = DatabaseConfig(
            host="localhost",
            port=1521,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.ORACLE,
            service_name="test-service",
        )
        url = config.connection_url
        assert (
            url
            == "oracle+cx_oracle://user:password@localhost:1521/test_db"  # pragma: allowlist secret
        )

    def test_connection_url_mssql(self):
        config = DatabaseConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.MSSQL,
            service_name="test-service",
        )
        url = config.connection_url
        assert (
            url
            == "mssql+aioodbc://user:password@localhost:1433/test_db"  # pragma: allowlist secret
        )

    def test_sync_connection_url_oracle(self):
        config = DatabaseConfig(
            host="localhost",
            port=1521,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.ORACLE,
            service_name="test-service",
        )
        url = config.sync_connection_url
        assert (
            url
            == "oracle+cx_oracle://user:password@localhost:1521/test_db"  # pragma: allowlist secret
        )

    def test_sync_connection_url_mssql(self):
        config = DatabaseConfig(
            host="localhost",
            port=1433,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.MSSQL,
            service_name="test-service",
        )
        url = config.sync_connection_url
        assert (
            url == "mssql+pyodbc://user:password@localhost:1433/test_db"  # pragma: allowlist secret
        )

    def test_sync_connection_url_sqlite(self):
        config = DatabaseConfig(
            host="",
            port=0,
            database="test.db",
            username="",
            password="",
            db_type=DatabaseType.SQLITE,
            service_name="test-service",
        )
        url = config.sync_connection_url
        assert url == "sqlite:///test.db"

    def test_sync_connection_url_mysql(self):
        config = DatabaseConfig(
            host="localhost",
            port=3306,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            db_type=DatabaseType.MYSQL,
            service_name="test-service",
        )
        url = config.sync_connection_url
        assert (
            url
            == "mysql+pymysql://user:password@localhost:3306/test_db"  # pragma: allowlist secret
        )

    def test_from_url(self):
        url = "postgresql://user:password@localhost:5432/test_db?sslmode=require"  # pragma: allowlist secret
        config = DatabaseConfig.from_url(url, service_name="test-service")

        assert config.db_type == DatabaseType.POSTGRESQL
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "test_db"
        assert config.username == "user"
        assert config.password == "password"  # pragma: allowlist secret
        assert config.ssl_mode == "require"
        assert config.service_name == "test-service"

    def test_from_environment_generic(self):
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db-host",
                "DB_PORT": "5432",
                "DB_NAME": "db-name",
                "DB_USER": "db-user",
                "DB_PASSWORD": "db-password",  # pragma: allowlist secret
                "DB_TYPE": "postgresql",
            },
        ):
            config = DatabaseConfig.from_environment(service_name="test-service")

            assert config.host == "db-host"
            assert config.port == 5432
            assert config.database == "db-name"
            assert config.username == "db-user"
            assert config.password == "db-password"  # pragma: allowlist secret
            assert config.db_type == DatabaseType.POSTGRESQL

    def test_from_environment_service_specific(self):
        with patch.dict(
            os.environ,
            {
                "TEST_SERVICE_DB_HOST": "service-host",
                "TEST_SERVICE_DB_PORT": "5433",
                "TEST_SERVICE_DB_NAME": "service-db",
                "TEST_SERVICE_DB_USER": "service-user",
                "TEST_SERVICE_DB_PASSWORD": "service-password",  # pragma: allowlist secret
                "DB_HOST": "generic-host",
            },
        ):
            config = DatabaseConfig.from_environment(service_name="test-service")

            assert config.host == "service-host"
            assert config.port == 5433
            assert config.database == "service-db"
            assert config.username == "service-user"
            assert config.password == "service-password"  # pragma: allowlist secret

    def test_from_environment_full(self):
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db-host",
                "DB_PORT": "5432",
                "DB_NAME": "db-name",
                "DB_USER": "db-user",
                "DB_PASSWORD": "db-password",  # pragma: allowlist secret
                "DB_TYPE": "postgresql",
                "DB_SSL_MODE": "require",
                "DB_SSL_CERT": "/cert",
                "DB_SSL_KEY": "/key",
                "DB_SSL_CA": "/ca",
                "DB_POOL_MIN_SIZE": "5",
                "DB_POOL_MAX_SIZE": "20",
                "DB_POOL_MAX_OVERFLOW": "30",
                "DB_POOL_TIMEOUT": "60",
                "DB_POOL_RECYCLE": "1800",
                "DB_ECHO": "true",
                "DB_SCHEMA": "public",
                "DB_TIMEZONE": "UTC",
            },
        ):
            config = DatabaseConfig.from_environment(service_name="test-service")

            assert config.ssl_mode == "require"
            assert config.ssl_cert == "/cert"
            assert config.ssl_key == "/key"
            assert config.ssl_ca == "/ca"
            assert config.pool_config.min_size == 5
            assert config.pool_config.max_size == 20
            assert config.pool_config.max_overflow == 30
            assert config.pool_config.pool_timeout == 60
            assert config.pool_config.pool_recycle == 1800
            assert config.pool_config.echo is True
            assert config.schema == "public"
            assert config.timezone == "UTC"

    def test_to_dict(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
            ssl_mode="require",
        )
        data = config.to_dict()

        assert data["host"] == "localhost"
        assert data["port"] == 5432
        assert data["database"] == "test_db"
        assert data["username"] == "user"
        assert "password" not in data  # Should be excluded
        assert data["service_name"] == "test-service"
        assert data["ssl_mode"] == "require"
        assert data["db_type"] == "postgresql"

    def test_validate_success(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
        )
        # Should not raise exception
        config.validate()

    def test_validate_missing_service_name(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="unknown",
        )
        with pytest.raises(ValueError, match="service_name is required"):
            config.validate()

    def test_validate_missing_host(self):
        config = DatabaseConfig(
            host="",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
        )
        with pytest.raises(ValueError, match="host is required"):
            config.validate()

    def test_validate_missing_username(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
        )
        with pytest.raises(ValueError, match="username is required for non-SQLite databases"):
            config.validate()

    def test_validate_invalid_pool_config(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
            pool_config=ConnectionPoolConfig(min_size=-1),
        )
        with pytest.raises(ValueError, match="pool min_size must be non-negative"):
            config.validate()

    def test_connection_url_with_options(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            options={"connect_timeout": 10, "application_name": "test"},
        )
        url = config.connection_url
        assert "connect_timeout=10" in url
        assert "application_name=test" in url

    def test_sync_connection_url_full(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            ssl_mode="verify-full",
            ssl_cert="/path/to/cert",
            ssl_key="/path/to/key",
            ssl_ca="/path/to/ca",
            timezone="UTC",
            options={"connect_timeout": 10},
        )
        url = config.sync_connection_url
        assert "postgresql+psycopg2://" in url
        assert "sslmode=verify-full" in url
        assert "sslcert=/path/to/cert" in url
        assert "sslkey=/path/to/key" in url
        assert "sslrootcert=/path/to/ca" in url
        assert "timezone=UTC" in url
        assert "connect_timeout=10" in url

    def test_from_url_with_ssl_params(self):
        url = "postgresql://user:pass@localhost:5432/db?sslmode=require&sslcert=/cert&sslkey=/key&sslrootcert=/ca&other=value"  # pragma: allowlist secret
        config = DatabaseConfig.from_url(url)

        assert config.ssl_mode == "require"
        assert config.ssl_cert == "/cert"
        assert config.ssl_key == "/key"
        assert config.ssl_ca == "/ca"
        assert config.options["other"] == "value"

    def test_validate_invalid_pool_size(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
            pool_config=ConnectionPoolConfig(min_size=10, max_size=5),
        )
        with pytest.raises(ValueError, match="pool max_size must be >= min_size"):
            config.validate()

    def test_validate_negative_min_size(self):
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="password",  # pragma: allowlist secret
            service_name="test-service",
            pool_config=ConnectionPoolConfig(min_size=-1),
        )
        with pytest.raises(ValueError, match="pool min_size must be non-negative"):
            config.validate()

    def test_get_default_port(self):
        assert DatabaseConfig._get_default_port(DatabaseType.POSTGRESQL) == 5432
        assert DatabaseConfig._get_default_port(DatabaseType.MYSQL) == 3306
        assert DatabaseConfig._get_default_port(DatabaseType.SQLITE) == 0
