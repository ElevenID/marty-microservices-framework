"""Migration manager port interfaces (application layer).

This module defines abstract port interfaces for database migration management,
following hexagonal architecture principles. These ports are independent of any
specific migration tool (e.g., Alembic) and define the contract that infrastructure
adapters must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class MigrationManagerPort(ABC):
    """Abstract port for database migration management.

    This port defines the interface for managing database schema migrations.
    Infrastructure adapters (e.g., AlembicMigrationAdapter) implement this interface
    to provide concrete migration functionality.

    Follows hexagonal architecture: application layer defines ports (interfaces),
    infrastructure layer provides adapters (implementations).
    """

    @abstractmethod
    def initialize(self, service_name: str, migrations_dir: Path) -> None:
        """Initialize migration infrastructure for a service.

        Args:
            service_name: Name of the service (used for schema/naming)
            migrations_dir: Path where migration files will be stored

        Raises:
            MigrationError: If initialization fails
        """
        pass

    @abstractmethod
    def create_migration(
        self,
        message: str,
        autogenerate: bool = True,
        sql_mode: bool = False,
    ) -> Optional[str]:
        """Create a new migration.

        Args:
            message: Description of the migration
            autogenerate: Whether to auto-detect schema changes from models
            sql_mode: If True, generate SQL statements instead of applying them

        Returns:
            Path to the created migration file, or None if no changes detected

        Raises:
            MigrationError: If migration creation fails
        """
        pass

    @abstractmethod
    def upgrade(self, revision: str = "head", sql_mode: bool = False) -> None:
        """Apply migrations up to a specific revision.

        Args:
            revision: Target revision (default: "head" for latest)
            sql_mode: If True, generate SQL statements instead of applying them

        Raises:
            MigrationError: If upgrade fails
        """
        pass

    @abstractmethod
    def downgrade(self, revision: str, sql_mode: bool = False) -> None:
        """Rollback migrations to a specific revision.

        Args:
            revision: Target revision to rollback to
            sql_mode: If True, generate SQL statements instead of applying them

        Raises:
            MigrationError: If downgrade fails
        """
        pass

    @abstractmethod
    def current(self) -> Optional[str]:
        """Get the current migration revision.

        Returns:
            Current revision identifier, or None if no migrations applied

        Raises:
            MigrationError: If unable to determine current revision
        """
        pass

    @abstractmethod
    def history(self, verbose: bool = False) -> list[str]:
        """Get migration history.

        Args:
            verbose: If True, include detailed information

        Returns:
            List of migration revisions in chronological order

        Raises:
            MigrationError: If unable to retrieve history
        """
        pass

    @abstractmethod
    def verify_schema(self, raise_on_mismatch: bool = True) -> bool:
        """Verify that database schema matches migration state.

        Args:
            raise_on_mismatch: If True, raise exception on schema mismatch

        Returns:
            True if schema is up-to-date, False otherwise

        Raises:
            MigrationError: If raise_on_mismatch is True and schema is outdated
        """
        pass


class MigrationError(Exception):
    """Exception raised for migration-related errors."""

    pass
