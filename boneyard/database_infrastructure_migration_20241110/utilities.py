"""Database utilities for the infrastructure layer."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatabaseUtilities:
    """Utility functions for database operations."""

    def __init__(self, db_manager):
        """Initialize utilities with database manager."""
        self.db_manager = db_manager
        self._metadata = MetaData()

    def _validate_table_name(self, table_name: str) -> str:
        """Validate and sanitize table name to prevent SQL injection."""
        # Only allow alphanumeric characters, underscores, and periods
        if not re.match(
            r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$", table_name
        ):
            raise ValueError(f"Invalid table name: {table_name}")
        return table_name

    def _quote_identifier(self, identifier: str) -> str:
        """Quote SQL identifier safely."""
        validated = self._validate_table_name(identifier)
        # Use double quotes for SQL standard identifier quoting
        return f'"{validated}"'

    def _reflect_table(self, table_name: str) -> Table:
        """Safely reflect a table using SQLAlchemy Core."""
        validated = self._validate_table_name(table_name)
        return Table(
            validated, self._metadata, autoload_with=self.db_manager.sync_engine
        )

    async def check_connection(self) -> dict[str, Any]:
        """Check database connection and return status."""
        return await self.db_manager.health_check()

    async def get_database_info(self) -> dict[str, Any]:
        """Get comprehensive database information."""
        async with self.db_manager.get_session() as session:
            info = {
                "service_name": self.db_manager.config.service_name,
                "database_name": self.db_manager.config.database,
                "database_type": self.db_manager.config.db_type.value,
                "connection_url": self._mask_connection_url(),
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
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                        )
                    )
                    active_connections = result.scalar()
                    info["active_connections"] = active_connections

            except Exception as e:
                logger.warning("Could not retrieve additional database info: %s", e)
                info["info_error"] = str(e)

            return info

    def _mask_connection_url(self) -> str:
        """Return connection URL with password masked."""
        return self.db_manager.config.connection_url.replace(
            f":{self.db_manager.config.password}@", ":***@"
        )

    async def get_table_info(self, table_name: str) -> dict[str, Any]:
        """Get information about a specific table."""
        async with self.db_manager.get_session() as session:
            info = {
                "table_name": table_name,
                "exists": False,
                "columns": [],
                "indexes": [],
                "row_count": 0,
            }

            try:
                # Check if table exists and get basic info
                if self.db_manager.config.db_type.value == "postgresql":
                    exists_query = text(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = :table_name
                        )
                    """
                    )
                    result = await session.execute(
                        exists_query, {"table_name": table_name}
                    )
                    info["exists"] = result.scalar()

                    if info["exists"]:
                        # Get column information
                        columns_query = text(
                            """
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                            AND table_name = :table_name
                            ORDER BY ordinal_position
                        """
                        )
                        result = await session.execute(
                            columns_query, {"table_name": table_name}
                        )
                        info["columns"] = [dict(row._mapping) for row in result]

                        # Get row count using SQLAlchemy
                        table = self._reflect_table(table_name)
                        count_query = select(func.count()).select_from(table)
                        result = await session.execute(count_query)
                        info["row_count"] = result.scalar()

            except Exception as e:
                logger.error("Error getting table info for %s: %s", table_name, e)
                info["error"] = str(e)

            return info

    async def vacuum_analyze(self, table_name: str | None = None) -> dict[str, Any]:
        """Perform VACUUM ANALYZE on specified table or entire database."""
        if self.db_manager.config.db_type.value != "postgresql":
            return {"error": "VACUUM ANALYZE only supported for PostgreSQL"}

        try:
            # Use sync engine for maintenance operations
            with self.db_manager.sync_engine.connect() as conn:
                if table_name:
                    validated_name = self._validate_table_name(table_name)
                    query = f'VACUUM ANALYZE "{validated_name}"'
                else:
                    query = "VACUUM ANALYZE"

                start_time = datetime.utcnow()
                conn.execute(text(query))
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()

                return {
                    "success": True,
                    "table": table_name or "entire database",
                    "duration_seconds": duration,
                    "timestamp": end_time.isoformat(),
                }

        except Exception as e:
            logger.error("Error during VACUUM ANALYZE: %s", e)
            return {"success": False, "error": str(e)}

    async def get_table_statistics(self, table_name: str) -> dict[str, Any]:
        """Get detailed statistics for a table."""
        async with self.db_manager.get_session() as session:
            stats = {"table_name": table_name}

            try:
                if self.db_manager.config.db_type.value == "postgresql":
                    # Get PostgreSQL table statistics
                    stats_query = text(
                        """
                        SELECT
                            schemaname,
                            tablename,
                            n_tup_ins as inserts,
                            n_tup_upd as updates,
                            n_tup_del as deletes,
                            n_live_tup as live_rows,
                            n_dead_tup as dead_rows,
                            last_vacuum,
                            last_autovacuum,
                            last_analyze,
                            last_autoanalyze
                        FROM pg_stat_user_tables
                        WHERE tablename = :table_name
                    """
                    )
                    result = await session.execute(
                        stats_query, {"table_name": table_name}
                    )
                    row = result.first()
                    if row:
                        stats.update(dict(row._mapping))

            except Exception as e:
                logger.error("Error getting table statistics: %s", e)
                stats["error"] = str(e)

            return stats

    async def get_connection_info(self) -> dict[str, Any]:
        """Get information about current database connections."""
        async with self.db_manager.get_session() as session:
            conn_info = {}

            try:
                if self.db_manager.config.db_type.value == "postgresql":
                    query = text(
                        """
                        SELECT
                            count(*) as total_connections,
                            count(*) FILTER (WHERE state = 'active') as active_connections,
                            count(*) FILTER (WHERE state = 'idle') as idle_connections,
                            count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                    """
                    )
                    result = await session.execute(query)
                    row = result.first()
                    if row:
                        conn_info.update(dict(row._mapping))

                    # Add pool information if available
                    pool = self.db_manager._async_engine.pool
                    conn_info.update(
                        {
                            "pool_size": pool.size(),
                            "pool_checked_in": pool.checkedin(),
                            "pool_checked_out": pool.checkedout(),
                            "pool_overflow": pool.overflow(),
                            "pool_invalid": pool.invalid(),
                        }
                    )

            except Exception as e:
                logger.error("Error getting connection info: %s", e)
                conn_info["error"] = str(e)

            return conn_info

    async def optimize_table(self, table_name: str) -> dict[str, Any]:
        """Optimize a table (PostgreSQL: VACUUM ANALYZE, MySQL: OPTIMIZE TABLE)."""
        try:
            start_time = datetime.utcnow()

            if self.db_manager.config.db_type.value == "postgresql":
                return await self.vacuum_analyze(table_name)

            elif self.db_manager.config.db_type.value == "mysql":
                with self.db_manager.sync_engine.connect() as conn:
                    validated_name = self._validate_table_name(table_name)
                    conn.execute(text(f"OPTIMIZE TABLE `{validated_name}`"))

                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()

                return {
                    "success": True,
                    "table": table_name,
                    "operation": "OPTIMIZE TABLE",
                    "duration_seconds": duration,
                    "timestamp": end_time.isoformat(),
                }

            else:
                return {
                    "error": f"Table optimization not supported for {self.db_manager.config.db_type.value}"
                }

        except Exception as e:
            logger.error("Error optimizing table %s: %s", table_name, e)
            return {"success": False, "error": str(e)}


# Factory function
def create_database_utilities(db_manager) -> DatabaseUtilities:
    """Create database utilities with the given database manager."""
    return DatabaseUtilities(db_manager)
