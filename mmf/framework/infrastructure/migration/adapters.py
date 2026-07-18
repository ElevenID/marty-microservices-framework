"""Alembic migration adapter implementation (infrastructure layer).

This module provides a concrete implementation of MigrationManagerPort using Alembic.
It handles all Alembic-specific details while exposing a clean, framework-agnostic
interface through the port.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

from .ports import MigrationError, MigrationManagerPort

logger = logging.getLogger(__name__)


class AlembicMigrationAdapter(MigrationManagerPort):
    """Alembic-based implementation of MigrationManagerPort.

    This adapter encapsulates all Alembic-specific logic, providing a clean
    interface for database migrations that follows hexagonal architecture principles.

    Args:
        database_url: SQLAlchemy database URL
        metadata: SQLAlchemy MetaData object containing table definitions
    """

    def __init__(self, database_url: str, metadata):
        """Initialize Alembic migration adapter.

        Args:
            database_url: SQLAlchemy database URL (e.g., postgresql+asyncpg://...)
            metadata: SQLAlchemy MetaData object with table definitions
        """
        self.database_url = database_url
        self.metadata = metadata
        self.alembic_cfg: Config | None = None
        self._service_name: str | None = None
        self._migrations_dir: Path | None = None

    def initialize(self, service_name: str, migrations_dir: Path) -> None:
        """Initialize Alembic migration infrastructure.

        Creates alembic.ini and env.py if they don't exist, sets up the
        versions directory structure.

        Args:
            service_name: Name of the service (used for schema in env.py)
            migrations_dir: Path where migration files will be stored
        """
        try:
            self._service_name = service_name
            self._migrations_dir = Path(migrations_dir)
            self._migrations_dir.mkdir(parents=True, exist_ok=True)

            # Create alembic.ini
            alembic_ini_path = self._migrations_dir / "alembic.ini"
            if not alembic_ini_path.exists():
                self._create_alembic_ini(alembic_ini_path)

            # Create versions directory
            versions_dir = self._migrations_dir / "versions"
            versions_dir.mkdir(exist_ok=True)

            # Create env.py
            env_py_path = self._migrations_dir / "env.py"
            if not env_py_path.exists():
                self._create_env_py(env_py_path, service_name)

            # Create script.py.mako template
            script_mako_path = self._migrations_dir / "script.py.mako"
            if not script_mako_path.exists():
                self._create_script_mako(script_mako_path)

            # Initialize Alembic config
            self.alembic_cfg = Config(str(alembic_ini_path))
            self.alembic_cfg.set_main_option("script_location", str(self._migrations_dir))
            self.alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)

            logger.info(f"Initialized Alembic migrations for {service_name} at {migrations_dir}")

        except Exception as e:
            raise MigrationError(f"Failed to initialize migrations: {e}") from e

    def create_migration(
        self,
        message: str,
        autogenerate: bool = True,
        sql_mode: bool = False,
    ) -> str | None:
        """Create a new Alembic migration.

        Args:
            message: Description of the migration
            autogenerate: Whether to auto-detect schema changes
            sql_mode: If True, generate SQL instead of applying

        Returns:
            Path to created migration file, or None if no changes
        """
        self._ensure_initialized()

        try:
            # Set target metadata for autogenerate
            self.alembic_cfg.attributes["target_metadata"] = self.metadata

            if sql_mode:
                command.revision(
                    self.alembic_cfg,
                    message=message,
                    autogenerate=autogenerate,
                    sql=True,
                )
                return None
            else:
                result = command.revision(
                    self.alembic_cfg,
                    message=message,
                    autogenerate=autogenerate,
                )
                if result:
                    logger.info(f"Created migration: {result.path}")
                    return str(result.path)
                return None

        except Exception as e:
            raise MigrationError(f"Failed to create migration: {e}") from e

    def upgrade(self, revision: str = "head", sql_mode: bool = False) -> None:
        """Apply migrations up to revision.

        Args:
            revision: Target revision (default: "head")
            sql_mode: If True, generate SQL instead of applying
        """
        self._ensure_initialized()

        try:
            if sql_mode:
                command.upgrade(self.alembic_cfg, revision, sql=True)
            else:
                command.upgrade(self.alembic_cfg, revision)
                logger.info(f"Upgraded to revision: {revision}")

        except Exception as e:
            raise MigrationError(f"Failed to upgrade: {e}") from e

    def downgrade(self, revision: str, sql_mode: bool = False) -> None:
        """Rollback migrations to revision.

        Args:
            revision: Target revision to rollback to
            sql_mode: If True, generate SQL instead of applying
        """
        self._ensure_initialized()

        try:
            if sql_mode:
                command.downgrade(self.alembic_cfg, revision, sql=True)
            else:
                command.downgrade(self.alembic_cfg, revision)
                logger.info(f"Downgraded to revision: {revision}")

        except Exception as e:
            raise MigrationError(f"Failed to downgrade: {e}") from e

    def current(self) -> str | None:
        """Get current migration revision.

        Returns:
            Current revision ID, or None if no migrations applied
        """
        self._ensure_initialized()

        try:
            # Create a synchronous engine for checking revision
            sync_url = self.database_url.replace("+asyncpg", "").replace("+aiomysql", "")
            engine = create_engine(sync_url, poolclass=pool.NullPool)

            with engine.connect() as connection:
                # Configure with service-specific schema if available
                config_opts = {}
                if self._service_name:
                    config_opts["version_table_schema"] = f"{self._service_name}_service"

                context = MigrationContext.configure(connection, opts=config_opts)
                current_rev = context.get_current_revision()
                return current_rev

        except Exception as e:
            raise MigrationError(f"Failed to get current revision: {e}") from e

    def history(self, verbose: bool = False) -> list[str]:
        """Get migration history.

        Args:
            verbose: Include detailed information

        Returns:
            List of revision IDs in chronological order
        """
        self._ensure_initialized()

        try:
            script = ScriptDirectory.from_config(self.alembic_cfg)
            revisions = []

            for revision in script.walk_revisions():
                if verbose:
                    revisions.append(
                        f"{revision.revision}: {revision.doc} (down: {revision.down_revision})"
                    )
                else:
                    revisions.append(revision.revision)

            return list(reversed(revisions))

        except Exception as e:
            raise MigrationError(f"Failed to get history: {e}") from e

    def verify_schema(self, raise_on_mismatch: bool = True) -> bool:
        """Verify database schema matches migration state.

        Args:
            raise_on_mismatch: Raise exception if schema is outdated

        Returns:
            True if schema is up-to-date, False otherwise
        """
        self._ensure_initialized()

        try:
            current_rev = self.current()
            script = ScriptDirectory.from_config(self.alembic_cfg)
            head_rev = script.get_current_head()

            is_up_to_date = current_rev == head_rev

            if not is_up_to_date and raise_on_mismatch:
                raise MigrationError(
                    f"Schema mismatch: current={current_rev}, expected={head_rev}. "
                    f"Run migrations to update schema."
                )

            return is_up_to_date

        except MigrationError:
            raise
        except Exception as e:
            raise MigrationError(f"Failed to verify schema: {e}") from e

    def _ensure_initialized(self) -> None:
        """Ensure migration infrastructure is initialized."""
        if not self.alembic_cfg:
            raise MigrationError("Migration adapter not initialized. Call initialize() first.")

    def _create_alembic_ini(self, path: Path) -> None:
        """Create alembic.ini configuration file."""
        content = """\
# Alembic configuration file

[alembic]
# Path to migration scripts
script_location = %(here)s

# Template used to generate migration files
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Timezone for migration timestamps
timezone = UTC

# Max length of characters to apply to the "slug" field
truncate_slug_length = 40

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
        path.write_text(content)

    def _create_env_py(self, path: Path, service_name: str) -> None:
        """Create env.py for Alembic migrations."""
        content = f'''\
"""Alembic environment configuration for {service_name}."""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your service's metadata
# This will be set dynamically by AlembicMigrationAdapter
target_metadata = context.config.attributes.get("target_metadata", None)

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
        # Include schema in autogenerate
        include_schemas=True,
        # Service-specific schema
        version_table_schema="{service_name}_service",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {{}}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Include schema in autogenerate
            include_schemas=True,
            # Service-specific schema
            version_table_schema="{service_name}_service",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
        path.write_text(content)

    def _create_script_mako(self, path: Path) -> None:
        """Create script.py.mako template for migration files."""
        content = '''\
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
        path.write_text(content)
