"""
Database utilities for the application layer.
Provides database maintenance, diagnostics, and utility operations.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import MetaData, Table, func, inspect, select, text

from ..domain.database import DatabaseManager
from ..infrastructure.database import BaseModel

logger = logging.getLogger(__name__)


class DatabaseUtilities:
    """Utility functions for database operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._metadata = MetaData()

    def _validate_table_name(self, table_name: str) -> str:
        """Validate and sanitize table name to prevent SQL injection."""
        # Only allow alphanumeric characters, underscores, and periods
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$", table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        return table_name

    def _quote_identifier(self, identifier: str) -> str:
        """Quote SQL identifier safely."""
        validated = self._validate_table_name(identifier)
        # Use double quotes for SQL standard identifier quoting
        return f'"{validated}"'

    async def check_connection(self) -> dict[str, Any]:
        """Check database connection and return status."""
        return await self.db_manager.health_check()

    async def get_database_info(self) -> dict[str, Any]:
        """Get comprehensive database information."""
        async with self.db_manager.get_session() as session:
            info = {
                "service_name": getattr(self.db_manager, "service_name", "unknown"),
                "database_name": getattr(self.db_manager, "database", "unknown"),
                "connection_status": "connected",
            }

            try:
                # Get current timestamp
                result = await session.execute(text("SELECT CURRENT_TIMESTAMP"))
                current_time = result.scalar()
                info["current_timestamp"] = current_time

            except Exception as e:
                logger.warning("Could not retrieve additional database info: %s", e)
                info["info_error"] = str(e)

            return info

    async def get_table_info(self, table_name: str) -> dict[str, Any]:
        """Get information about a specific table."""
        async with self.db_manager.get_session() as session:
            try:
                # Use a simple count query for demonstration
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {self._quote_identifier(table_name)}")
                )
                row_count = result.scalar() or 0

                return {
                    "table_name": table_name,
                    "row_count": row_count,
                }

            except Exception as e:
                logger.error("Error getting table info for %s: %s", table_name, e)
                raise

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        async with self.db_manager.get_session() as session:
            try:
                await session.execute(
                    text(f"SELECT 1 FROM {self._quote_identifier(table_name)} LIMIT 1")
                )
                return True
            except Exception:
                return False

    async def truncate_table(self, table_name: str, restart_identity: bool = True) -> bool:
        """Truncate a table."""
        async with self.db_manager.get_transaction() as session:
            try:
                quoted_table = self._quote_identifier(table_name)
                await session.execute(text(f"DELETE FROM {quoted_table}"))
                logger.info("Truncated table: %s", table_name)
                return True

            except Exception as e:
                logger.error("Error truncating table %s: %s", table_name, e)
                return False

    async def clean_soft_deleted(
        self, model_class: type[BaseModel], older_than_days: int = 30
    ) -> int:
        """Clean up soft-deleted records older than specified days."""
        if not hasattr(model_class, "deleted_at"):
            raise ValueError(f"Model {model_class.__name__} does not support soft deletion")

        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        table_name = getattr(model_class, "__tablename__", model_class.__name__.lower())

        async with self.db_manager.get_transaction() as session:
            try:
                # Count records to be deleted first
                count_query = text(
                    f"SELECT COUNT(*) FROM {self._quote_identifier(table_name)} "
                    f"WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff_date"
                )
                count_result = await session.execute(count_query, {"cutoff_date": cutoff_date})
                count = count_result.scalar() or 0

                # Delete records
                if count > 0:
                    delete_query = text(
                        f"DELETE FROM {self._quote_identifier(table_name)} "
                        f"WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff_date"
                    )
                    await session.execute(delete_query, {"cutoff_date": cutoff_date})
                    logger.info("Cleaned up %d soft-deleted records from %s", count, table_name)

                return count

            except Exception as e:
                logger.error("Error cleaning soft-deleted records from %s: %s", table_name, e)
                raise

    async def backup_table(self, table_name: str, backup_table_name: str | None = None) -> str:
        """Create a backup copy of a table."""
        if not backup_table_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_table_name = f"{table_name}_backup_{timestamp}"

        async with self.db_manager.get_transaction() as session:
            try:
                valid_src = self._quote_identifier(table_name)
                valid_backup = self._quote_identifier(backup_table_name)

                # Create backup table with data
                backup_query = text(f"CREATE TABLE {valid_backup} AS SELECT * FROM {valid_src}")
                await session.execute(backup_query)

                logger.info("Created backup table: %s", backup_table_name)
                return backup_table_name

            except Exception as e:
                logger.error("Error creating backup for table %s: %s", table_name, e)
                raise

    async def execute_maintenance(
        self, operations: list[str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute maintenance operations."""
        results = {}

        for operation in operations:
            operation = operation.lower().strip()

            try:
                if operation.startswith("backup_"):
                    table_name = operation.replace("backup_", "")
                    if dry_run:
                        results[operation] = f"Would backup table {table_name}"
                    else:
                        backup_name = await self.backup_table(table_name)
                        results[operation] = f"Created backup: {backup_name}"

                elif operation.startswith("truncate_"):
                    table_name = operation.replace("truncate_", "")
                    if dry_run:
                        results[operation] = f"Would truncate table {table_name}"
                    else:
                        success = await self.truncate_table(table_name)
                        results[operation] = "Success" if success else "Failed"

                else:
                    results[operation] = "Unknown operation"

            except Exception as e:
                results[operation] = f"Error: {e}"

        return results


# Utility functions
async def get_database_utilities(db_manager: DatabaseManager) -> DatabaseUtilities:
    """Get database utilities instance."""
    return DatabaseUtilities(db_manager)


async def check_all_database_connections(
    managers: dict[str, DatabaseManager],
) -> dict[str, dict[str, Any]]:
    """Check connections for multiple database managers."""
    results = {}

    for service_name, manager in managers.items():
        try:
            utils = DatabaseUtilities(manager)
            results[service_name] = await utils.check_connection()
        except Exception as e:
            results[service_name] = {
                "status": "error",
                "service": service_name,
                "error": str(e),
            }

    return results


async def cleanup_all_soft_deleted(
    managers: dict[str, DatabaseManager],
    model_classes: list[type[BaseModel]],
    older_than_days: int = 30,
) -> dict[str, dict[str, int]]:
    """Clean up soft-deleted records across multiple services."""
    results = {}

    for service_name, manager in managers.items():
        utils = DatabaseUtilities(manager)
        service_results = {}

        for model_class in model_classes:
            try:
                count = await utils.clean_soft_deleted(model_class, older_than_days)
                service_results[model_class.__name__] = count
            except Exception as e:
                logger.error("Error cleaning %s in %s: %s", model_class.__name__, service_name, e)
                service_results[model_class.__name__] = -1

        results[service_name] = service_results

    return results
