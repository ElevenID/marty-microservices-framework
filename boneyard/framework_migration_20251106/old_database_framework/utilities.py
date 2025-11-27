"""
Database utilities for the enterprise database framework.
"""

import builtins
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from mmf_new.core.infrastructure.database import BaseModel
from sqlalchemy import MetaData, Table, func, inspect, select, text

from .manager import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseUtilities:
    """Utility functions for database operations."""

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

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._metadata = MetaData()

    def _reflect_table(self, table_name: str) -> Table:
        """Safely reflect a table using SQLAlchemy Core to avoid raw SQL string construction.

        Bandit B608 flags f-string based SQL even when identifiers are validated. By
        reflecting the table and using SQLAlchemy expression API we eliminate manual
        string concatenation for DML/SELECT statements.
        """
        validated = self._validate_table_name(table_name)
        return Table(validated, self._metadata, autoload_with=self.db_manager.sync_engine)

    async def check_connection(self) -> builtins.dict[str, Any]:
        """Check database connection and return status."""
        return await self.db_manager.health_check()

    async def get_database_info(self) -> builtins.dict[str, Any]:
        """Get comprehensive database information."""
        async with self.db_manager.get_session() as session:
            info = {
                "service_name": self.db_manager.config.service_name,
                "database_name": self.db_manager.config.database,
                "database_type": self.db_manager.config.db_type.value,
                "connection_url": self.db_manager._mask_connection_url(),
            }

            try:
                # Get database version
                if self.db_manager.config.db_type.value == "postgresql":
                    result = await session.execute(text("SELECT version()"))
                    version = result.scalar()
                    info["version"] = version
                elif self.db_manager.config.db_type.value == "mysql":
                    result = await session.execute(text("SELECT VERSION()"))
                    version = result.scalar()
                    info["version"] = version
                elif self.db_manager.config.db_type.value == "sqlite":
                    result = await session.execute(text("SELECT sqlite_version()"))
                    version = result.scalar()
                    info["version"] = f"SQLite {version}"

                # Get current timestamp
                result = await session.execute(text("SELECT CURRENT_TIMESTAMP"))
                current_time = result.scalar()
                info["current_timestamp"] = current_time

                # Get connection count (if supported)
                if self.db_manager.config.db_type.value == "postgresql":
                    result = await session.execute(
                        text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                    )
                    active_connections = result.scalar()
                    info["active_connections"] = active_connections

            except Exception as e:
                logger.warning("Could not retrieve additional database info: %s", e)
                info["info_error"] = str(e)

            return info

    async def get_table_info(self, table_name: str) -> builtins.dict[str, Any]:
        """Get information about a specific table."""
        async with self.db_manager.get_session() as session:
            try:
                inspector = inspect(self.db_manager.sync_engine)

                # Get table info
                columns = inspector.get_columns(table_name)
                indexes = inspector.get_indexes(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                primary_key = inspector.get_pk_constraint(table_name)

                # Use SQLAlchemy Core for row count to avoid raw SQL string (B608)
                tbl = self._reflect_table(table_name)
                result = await session.execute(select(func.count()).select_from(tbl))
                row_count = result.scalar() or 0

                return {
                    "table_name": table_name,
                    "row_count": row_count,
                    "columns": columns,
                    "indexes": indexes,
                    "foreign_keys": foreign_keys,
                    "primary_key": primary_key,
                }

            except Exception as e:
                logger.error("Error getting table info for %s: %s", table_name, e)
                raise

    async def list_tables(self) -> builtins.list[str]:
        """List all tables in the database."""
        try:
            inspector = inspect(self.db_manager.sync_engine)
            return inspector.get_table_names()
        except Exception as e:
            logger.error("Error listing tables: %s", e)
            raise

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        try:
            tables = await self.list_tables()
            return table_name in tables
        except Exception as e:
            logger.error("Error checking if table exists: %s", e)
            return False

    async def create_schema(self, schema_name: str) -> bool:
        """Create a database schema (PostgreSQL only)."""
        if self.db_manager.config.db_type.value != "postgresql":
            logger.warning("Schema creation only supported for PostgreSQL")
            return False

        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                await session.commit()
                logger.info("Created schema: %s", schema_name)
                return True
            except Exception as e:
                logger.error("Error creating schema %s: %s", schema_name, e)
                await session.rollback()
                return False

    async def drop_schema(self, schema_name: str, cascade: bool = False) -> bool:
        """Drop a database schema (PostgreSQL only)."""
        if self.db_manager.config.db_type.value != "postgresql":
            logger.warning("Schema operations only supported for PostgreSQL")
            return False

        async with self.db_manager.get_session() as session:
            try:
                cascade_clause = "CASCADE" if cascade else "RESTRICT"
                await session.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} {cascade_clause}"))
                await session.commit()
                logger.info("Dropped schema: %s", schema_name)
                return True
            except Exception as e:
                logger.error("Error dropping schema %s: %s", schema_name, e)
                await session.rollback()
                return False

    async def vacuum_analyze(self, table_name: str | None = None) -> bool:
        """Run VACUUM ANALYZE on table or entire database (PostgreSQL)."""
        if self.db_manager.config.db_type.value != "postgresql":
            logger.warning("VACUUM ANALYZE only supported for PostgreSQL")
            return False

        # VACUUM cannot be run inside a transaction
        engine = self.db_manager.sync_engine

        try:
            with engine.connect() as conn:
                conn.execute(text("COMMIT"))  # Ensure no active transaction
                if table_name:
                    conn.execute(text(f"VACUUM ANALYZE {table_name}"))
                    logger.info("VACUUM ANALYZE completed for table: %s", table_name)
                else:
                    conn.execute(text("VACUUM ANALYZE"))
                    logger.info("VACUUM ANALYZE completed for entire database")
            return True
        except Exception as e:
            logger.error("Error running VACUUM ANALYZE: %s", e)
            return False

    async def analyze_table_stats(self, table_name: str) -> builtins.dict[str, Any]:
        """Get table statistics.

        Returns dict with keys: table_name (str), row_count (int), column_statistics (list[dict])
        """
        async with self.db_manager.get_session() as session:
            try:
                stats: builtins.dict[str, Any] = {"table_name": table_name}

                # Row count via Core (B608 mitigation)
                tbl = self._reflect_table(table_name)
                result = await session.execute(select(func.count()).select_from(tbl))
                stats["row_count"] = result.scalar() or 0

                if self.db_manager.config.db_type.value == "postgresql":
                    # PostgreSQL specific stats
                    # Column statistics query - parameterize table name comparison to avoid inline string
                    result = await session.execute(
                        text(
                            """
                        SELECT
                            schemaname,
                            tablename,
                            attname,
                            n_distinct,
                            correlation
                        FROM pg_stats
                        WHERE tablename = :tbl
                    """
                        ),
                        {"tbl": table_name},
                    )

                    column_stats: list[dict[str, Any]] = []
                    for row in result:
                        column_stats.append(
                            {
                                "column_name": row.attname,
                                "n_distinct": row.n_distinct,
                                "correlation": row.correlation,
                            }
                        )
                    stats["column_statistics"] = column_stats

                return stats

            except Exception as e:
                logger.error("Error analyzing table stats for %s: %s", table_name, e)
                raise

    async def backup_table(self, table_name: str, backup_table_name: str | None = None) -> str:
        """Create a backup copy of a table."""
        if not backup_table_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_table_name = f"{table_name}_backup_{timestamp}"

        async with self.db_manager.get_session() as session:
            try:
                # SQLAlchemy Core based copy (avoid raw SQL f-string to satisfy B608)
                valid_src = self._validate_table_name(table_name)
                valid_backup = self._validate_table_name(backup_table_name)
                src_tbl = self._reflect_table(valid_src)

                # Create backup table schema
                backup_columns = [c.copy() for c in src_tbl.columns]
                backup_tbl = Table(
                    valid_backup, self._metadata, *backup_columns, extend_existing=True
                )
                backup_tbl.create(self.db_manager.sync_engine, checkfirst=True)

                # Insert data
                insert_stmt = backup_tbl.insert().from_select(
                    [c.name for c in src_tbl.columns], select(src_tbl)
                )
                await session.execute(insert_stmt)
                await session.commit()

                logger.info("Created backup table via Core: %s", backup_table_name)
                return backup_table_name

            except Exception as e:
                logger.error("Error creating backup for table %s: %s", table_name, e)
                await session.rollback()
                raise

    async def truncate_table(self, table_name: str, restart_identity: bool = True) -> bool:
        """Truncate a table."""
        async with self.db_manager.get_session() as session:
            try:
                # Use quoted identifier to prevent SQL injection
                quoted_table = self._quote_identifier(table_name)

                if self.db_manager.config.db_type.value == "postgresql":
                    restart_clause = "RESTART IDENTITY" if restart_identity else "CONTINUE IDENTITY"
                    await session.execute(text(f"TRUNCATE TABLE {quoted_table} {restart_clause}"))
                else:
                    # Use Core delete when possible (non-PostgreSQL path uses generic DELETE)
                    tbl = self._reflect_table(table_name)
                    await session.execute(tbl.delete())

                await session.commit()
                logger.info("Truncated table: %s", table_name)
                return True

            except Exception as e:
                logger.error("Error truncating table %s: %s", table_name, e)
                await session.rollback()
                return False

    async def clean_soft_deleted(
        self, model_class: builtins.type[BaseModel], older_than_days: int = 30
    ) -> int:
        """Clean up soft-deleted records older than specified days."""
        if not hasattr(model_class, "deleted_at"):
            raise ValueError(f"Model {model_class.__name__} does not support soft deletion")

        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        # Some ORMs provide __tablename__ as InstrumentedAttribute; cast to str safely
        raw_table = getattr(model_class, "__tablename__", None)
        if not isinstance(raw_table, str):
            raise ValueError("Model class must define __tablename__ as a string")
        table_name = raw_table

        async with self.db_manager.get_session() as session:
            try:
                # Count records to be deleted
                # Validate table name but keep parameter binding for dynamic value
                tbl = self._reflect_table(table_name)  # table_name is str here
                # Build expression using column attributes to avoid raw SQL
                if not hasattr(tbl.c, "deleted_at"):
                    raise ValueError(
                        "Table does not support soft deletion (missing deleted_at column)"
                    )
                count_expr = (
                    select(func.count())
                    .select_from(tbl)
                    .where(tbl.c.deleted_at.is_not(None), tbl.c.deleted_at < text(":cutoff_date"))
                )
                count_result = await session.execute(count_expr, {"cutoff_date": cutoff_date})

                count = count_result.scalar()

                # Delete records
                if count > 0:
                    delete_stmt = tbl.delete().where(
                        tbl.c.deleted_at.is_not(None), tbl.c.deleted_at < text(":cutoff_date")
                    )
                    await session.execute(delete_stmt, {"cutoff_date": cutoff_date})

                    await session.commit()
                    logger.info("Cleaned up %d soft-deleted records from %s", count, table_name)

                return count

            except Exception as e:
                logger.error("Error cleaning soft-deleted records from %s: %s", table_name, e)
                await session.rollback()
                raise

    async def get_connection_pool_status(self) -> builtins.dict[str, Any]:
        """Get connection pool status."""
        if not self.db_manager.engine:
            return {"error": "Database not initialized"}

        pool = self.db_manager.engine.pool

        # Access attributes defensively; some pool implementations differ
        def _maybe_call(obj, name: str):  # runtime helper; type checker unaware of dynamic attrs
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    return None
            return None

        return {
            "pool_size": _maybe_call(pool, "size"),
            "checked_in": _maybe_call(pool, "checkedin"),
            "checked_out": _maybe_call(pool, "checkedout"),
            "overflow": _maybe_call(pool, "overflow"),
            "invalid": _maybe_call(pool, "invalid"),
        }

    async def execute_maintenance(
        self, operations: builtins.list[str], dry_run: bool = False
    ) -> builtins.dict[str, Any]:
        """Execute maintenance operations."""
        results = {}

        for operation in operations:
            operation = operation.lower().strip()

            try:
                if operation == "vacuum":
                    if dry_run:
                        results[operation] = "Would run VACUUM ANALYZE"
                    else:
                        success = await self.vacuum_analyze()
                        results[operation] = "Success" if success else "Failed"

                elif operation.startswith("backup_"):
                    table_name = operation.replace("backup_", "")
                    if dry_run:
                        results[operation] = f"Would backup table {table_name}"
                    else:
                        backup_name = await self.backup_table(table_name)
                        results[operation] = f"Created backup: {backup_name}"

                elif operation.startswith("clean_"):
                    # Extract model name and days
                    parts = operation.split("_")
                    if len(parts) >= 3:
                        days = int(parts[-1])
                        if dry_run:
                            results[operation] = f"Would clean records older than {days} days"
                        else:
                            # This would need model class resolution
                            results[operation] = "Clean operation not implemented yet"

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
    managers: builtins.dict[str, DatabaseManager],
) -> builtins.dict[str, builtins.dict[str, Any]]:
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
    managers: builtins.dict[str, DatabaseManager],
    model_classes: builtins.list[builtins.type[BaseModel]],
    older_than_days: int = 30,
) -> builtins.dict[str, builtins.dict[str, int]]:
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
