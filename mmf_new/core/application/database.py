"""
Database configuration for the application layer.
Contains configuration classes and database connection details.
"""

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..domain.database import DatabaseType


@dataclass
class ConnectionPoolConfig:
    """Database connection pool configuration."""

    min_size: int = 1
    max_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo: bool = False
    echo_pool: bool = False


@dataclass
class DatabaseConfig:
    """Database configuration for a service."""

    # Connection details
    host: str
    port: int
    database: str
    username: str
    password: str

    # Database type
    db_type: DatabaseType = DatabaseType.POSTGRESQL

    # Connection pool configuration
    pool_config: ConnectionPoolConfig = field(default_factory=ConnectionPoolConfig)

    # SSL configuration
    ssl_mode: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None
    ssl_ca: str | None = None

    # Service identification
    service_name: str = "unknown"

    # Additional options
    timezone: str = "UTC"
    schema: str | None = None
    options: dict[str, Any] = field(default_factory=dict)

    # Migration settings
    migration_table: str = "alembic_version"
    migration_directory: str | None = None

    @property
    def connection_url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        # Build basic URL
        if self.db_type == DatabaseType.POSTGRESQL:
            driver = "postgresql+asyncpg"
        elif self.db_type == DatabaseType.MYSQL:
            driver = "mysql+aiomysql"
        elif self.db_type == DatabaseType.SQLITE:
            return f"sqlite+aiosqlite:///{self.database}"
        elif self.db_type == DatabaseType.ORACLE:
            driver = "oracle+cx_oracle"
        elif self.db_type == DatabaseType.MSSQL:
            driver = "mssql+aioodbc"
        else:
            driver = str(self.db_type.value)

        # Build URL
        url = f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        # Add SSL parameters
        params = []
        if self.ssl_mode:
            params.append(f"sslmode={self.ssl_mode}")
        if self.ssl_cert:
            params.append(f"sslcert={self.ssl_cert}")
        if self.ssl_key:
            params.append(f"sslkey={self.ssl_key}")
        if self.ssl_ca:
            params.append(f"sslrootcert={self.ssl_ca}")

        # Add timezone
        if self.timezone and self.db_type == DatabaseType.POSTGRESQL:
            params.append(f"options=-c timezone={self.timezone}")

        # Add custom options
        for key, value in self.options.items():
            params.append(f"{key}={value}")

        if params:
            url += "?" + "&".join(params)

        return url

    @property
    def sync_connection_url(self) -> str:
        """Generate synchronous SQLAlchemy connection URL."""
        # Build basic URL with sync drivers
        if self.db_type == DatabaseType.POSTGRESQL:
            driver = "postgresql+psycopg2"
        elif self.db_type == DatabaseType.MYSQL:
            driver = "mysql+pymysql"
        elif self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        elif self.db_type == DatabaseType.ORACLE:
            driver = "oracle+cx_oracle"
        elif self.db_type == DatabaseType.MSSQL:
            driver = "mssql+pyodbc"
        else:
            driver = str(self.db_type.value)

        # Build URL
        url = f"{driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        # Add parameters (same as async version)
        params = []
        if self.ssl_mode:
            params.append(f"sslmode={self.ssl_mode}")
        if self.ssl_cert:
            params.append(f"sslcert={self.ssl_cert}")
        if self.ssl_key:
            params.append(f"sslkey={self.ssl_key}")
        if self.ssl_ca:
            params.append(f"sslrootcert={self.ssl_ca}")

        if self.timezone and self.db_type == DatabaseType.POSTGRESQL:
            params.append(f"options=-c timezone={self.timezone}")

        for key, value in self.options.items():
            params.append(f"{key}={value}")

        if params:
            url += "?" + "&".join(params)

        return url

    @classmethod
    def from_url(cls, url: str, service_name: str = "unknown") -> "DatabaseConfig":
        """Create DatabaseConfig from a connection URL."""

        parsed = urlparse(url)

        # Extract database type
        scheme = parsed.scheme.split("+")[0]
        db_type = DatabaseType(scheme)

        # Extract connection details
        config = cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or cls._get_default_port(db_type),
            database=parsed.path.lstrip("/") if parsed.path else "",
            username=parsed.username or "",
            password=parsed.password or "",
            db_type=db_type,
            service_name=service_name,
        )

        # Parse query parameters
        if parsed.query:
            params = parse_qs(parsed.query)
            for key, values in params.items():
                value = values[0] if values else ""

                if key == "sslmode":
                    config.ssl_mode = value
                elif key == "sslcert":
                    config.ssl_cert = value
                elif key == "sslkey":
                    config.ssl_key = value
                elif key == "sslrootcert":
                    config.ssl_ca = value
                else:
                    config.options[key] = value

        return config

    @classmethod
    def from_environment(cls, service_name: str) -> "DatabaseConfig":
        """Create DatabaseConfig from environment variables."""

        # Service-specific environment variables
        prefix = f"{service_name.upper().replace('-', '_')}_DB_"

        # Try service-specific variables first, then generic ones
        host = os.getenv(f"{prefix}HOST") or os.getenv("DB_HOST", "localhost")
        port = int(os.getenv(f"{prefix}PORT") or os.getenv("DB_PORT", "5432"))
        database = os.getenv(f"{prefix}NAME") or os.getenv("DB_NAME", service_name)
        username = os.getenv(f"{prefix}USER") or os.getenv("DB_USER", "postgres")
        password = os.getenv(f"{prefix}PASSWORD") or os.getenv("DB_PASSWORD", "")

        # Database type
        db_type_str = os.getenv(f"{prefix}TYPE") or os.getenv("DB_TYPE", "postgresql")
        db_type = DatabaseType(db_type_str.lower())

        # SSL configuration
        ssl_mode = os.getenv(f"{prefix}SSL_MODE") or os.getenv("DB_SSL_MODE")
        ssl_cert = os.getenv(f"{prefix}SSL_CERT") or os.getenv("DB_SSL_CERT")
        ssl_key = os.getenv(f"{prefix}SSL_KEY") or os.getenv("DB_SSL_KEY")
        ssl_ca = os.getenv(f"{prefix}SSL_CA") or os.getenv("DB_SSL_CA")

        # Pool configuration
        pool_config = ConnectionPoolConfig(
            min_size=int(
                os.getenv(f"{prefix}POOL_MIN_SIZE")
                or os.getenv("DB_POOL_MIN_SIZE", "1")
            ),
            max_size=int(
                os.getenv(f"{prefix}POOL_MAX_SIZE")
                or os.getenv("DB_POOL_MAX_SIZE", "10")
            ),
            max_overflow=int(
                os.getenv(f"{prefix}POOL_MAX_OVERFLOW")
                or os.getenv("DB_POOL_MAX_OVERFLOW", "20")
            ),
            pool_timeout=int(
                os.getenv(f"{prefix}POOL_TIMEOUT") or os.getenv("DB_POOL_TIMEOUT", "30")
            ),
            pool_recycle=int(
                os.getenv(f"{prefix}POOL_RECYCLE")
                or os.getenv("DB_POOL_RECYCLE", "3600")
            ),
            echo=os.getenv(f"{prefix}ECHO", "false").lower() == "true",
        )

        # Schema
        schema = os.getenv(f"{prefix}SCHEMA") or os.getenv("DB_SCHEMA")

        # Timezone
        timezone = os.getenv(f"{prefix}TIMEZONE") or os.getenv("DB_TIMEZONE", "UTC")

        return cls(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            db_type=db_type,
            pool_config=pool_config,
            ssl_mode=ssl_mode,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            ssl_ca=ssl_ca,
            service_name=service_name,
            schema=schema,
            timezone=timezone,
        )

    @staticmethod
    def _get_default_port(db_type: DatabaseType) -> int:
        """Get default port for database type."""
        port_map = {
            DatabaseType.POSTGRESQL: 5432,
            DatabaseType.MYSQL: 3306,
            DatabaseType.SQLITE: 0,  # Not applicable
            DatabaseType.ORACLE: 1521,
            DatabaseType.MSSQL: 1433,
        }
        return port_map.get(db_type, 5432)

    def validate(self) -> None:
        """Validate the database configuration."""
        if not self.service_name or self.service_name == "unknown":
            raise ValueError("service_name is required for database configuration")

        if self.db_type != DatabaseType.SQLITE:
            if not self.host:
                raise ValueError("host is required for non-SQLite databases")
            if not self.username:
                raise ValueError("username is required for non-SQLite databases")
            if not self.database:
                raise ValueError("database name is required")

        if self.pool_config.min_size < 0:
            raise ValueError("pool min_size must be non-negative")
        if self.pool_config.max_size < self.pool_config.min_size:
            raise ValueError("pool max_size must be >= min_size")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding sensitive information)."""
        return {
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "db_type": self.db_type.value,
            "schema": self.schema,
            "timezone": self.timezone,
            "ssl_mode": self.ssl_mode,
            "pool_config": {
                "min_size": self.pool_config.min_size,
                "max_size": self.pool_config.max_size,
                "max_overflow": self.pool_config.max_overflow,
                "pool_timeout": self.pool_config.pool_timeout,
                "pool_recycle": self.pool_config.pool_recycle,
                "echo": self.pool_config.echo,
            },
        }
