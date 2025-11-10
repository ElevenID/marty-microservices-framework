"""Database migration management for Alembic integration."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic."""

    def __init__(self, db_manager, migration_directory: str | None = None):
        """Initialize migration manager.

        Args:
            db_manager: Database manager instance
            migration_directory: Path to Alembic migration directory
        """
        self.db_manager = db_manager
        self.migration_directory = migration_directory or "alembic"
        self.config_file = f"{self.migration_directory}/alembic.ini"

    def _get_alembic_config(self) -> Config:
        """Get Alembic configuration."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(
                f"Alembic config file not found: {self.config_file}. "
                "Run 'migration_manager.init_alembic()' first."
            )

        alembic_cfg = Config(self.config_file)
        alembic_cfg.set_main_option("sqlalchemy.url", self.db_manager.config.sync_connection_url)
        alembic_cfg.set_main_option("script_location", self.migration_directory)

        return alembic_cfg

    def init_alembic(self, template: str = "generic") -> dict[str, Any]:
        """Initialize Alembic in the project.

        Args:
            template: Alembic template to use (generic, async, etc.)

        Returns:
            Result dictionary with success status and details
        """
        try:
            if os.path.exists(self.migration_directory):
                return {
                    "success": False,
                    "error": f"Migration directory already exists: {self.migration_directory}"
                }

            # Create migration directory
            os.makedirs(self.migration_directory, exist_ok=True)

            # Initialize Alembic
            alembic_cfg = Config()
            alembic_cfg.set_main_option("script_location", self.migration_directory)
            alembic_cfg.set_main_option("sqlalchemy.url", self.db_manager.config.sync_connection_url)

            command.init(alembic_cfg, self.migration_directory, template=template)

            # Customize alembic.ini
            self._customize_alembic_ini()

            return {
                "success": True,
                "migration_directory": self.migration_directory,
                "config_file": self.config_file,
            }

        except Exception as e:
            logger.error("Failed to initialize Alembic: %s", e)
            return {"success": False, "error": str(e)}

    def _customize_alembic_ini(self):
        """Customize the generated alembic.ini file."""
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                content = f.read()

            # Add service-specific customizations
            customizations = f"""
# Service: {self.db_manager.config.service_name}
# Database: {self.db_manager.config.database}

# Custom migration settings
compare_type = true
compare_server_default = true
render_as_batch = true
"""

            # Insert customizations after the main section
            content = content.replace(
                "[post_write_hooks]",
                customizations + "\n[post_write_hooks]"
            )

            with open(self.config_file, "w") as f:
                f.write(content)

    def get_current_revision(self) -> str | None:
        """Get the current database revision."""
        try:
            with self.db_manager.sync_engine.connect() as conn:
                context = MigrationContext.configure(conn)
                return context.get_current_revision()
        except Exception as e:
            logger.error("Error getting current revision: %s", e)
            return None

    def get_head_revision(self) -> str | None:
        """Get the head (latest) revision from migration scripts."""
        try:
            alembic_cfg = self._get_alembic_config()
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            return script_dir.get_current_head()
        except Exception as e:
            logger.error("Error getting head revision: %s", e)
            return None

    def get_migration_status(self) -> dict[str, Any]:
        """Get comprehensive migration status."""
        status = {
            "current_revision": self.get_current_revision(),
            "head_revision": self.get_head_revision(),
            "migrations_pending": False,
            "migration_directory_exists": os.path.exists(self.migration_directory),
            "config_file_exists": os.path.exists(self.config_file),
        }

        if status["current_revision"] and status["head_revision"]:
            status["migrations_pending"] = status["current_revision"] != status["head_revision"]
            status["up_to_date"] = not status["migrations_pending"]
        else:
            status["up_to_date"] = False

        return status

    def create_migration(self, message: str, auto_generate: bool = True) -> dict[str, Any]:
        """Create a new migration.

        Args:
            message: Migration description
            auto_generate: Whether to auto-generate migration from model changes

        Returns:
            Result dictionary with migration details
        """
        try:
            alembic_cfg = self._get_alembic_config()

            if auto_generate:
                # Auto-generate migration from model changes
                command.revision(
                    alembic_cfg,
                    message=message,
                    autogenerate=True
                )
            else:
                # Create empty migration template
                command.revision(alembic_cfg, message=message)

            # Get the new revision ID
            new_revision = self.get_head_revision()

            return {
                "success": True,
                "message": message,
                "revision": new_revision,
                "auto_generated": auto_generate,
            }

        except Exception as e:
            logger.error("Failed to create migration: %s", e)
            return {"success": False, "error": str(e)}

    def run_migrations(self, target_revision: str = "head") -> dict[str, Any]:
        """Run migrations to upgrade database.

        Args:
            target_revision: Target revision to migrate to (default: head)

        Returns:
            Result dictionary with migration details
        """
        try:
            alembic_cfg = self._get_alembic_config()

            # Store current revision before migration
            current_before = self.get_current_revision()

            # Run migration
            command.upgrade(alembic_cfg, target_revision)

            # Get new current revision
            current_after = self.get_current_revision()

            return {
                "success": True,
                "from_revision": current_before,
                "to_revision": current_after,
                "target": target_revision,
            }

        except Exception as e:
            logger.error("Failed to run migrations: %s", e)
            return {"success": False, "error": str(e)}

    def rollback_migration(self, target_revision: str) -> dict[str, Any]:
        """Rollback database to a specific revision.

        Args:
            target_revision: Target revision to rollback to

        Returns:
            Result dictionary with rollback details
        """
        try:
            alembic_cfg = self._get_alembic_config()

            # Store current revision before rollback
            current_before = self.get_current_revision()

            # Run downgrade
            command.downgrade(alembic_cfg, target_revision)

            # Get new current revision
            current_after = self.get_current_revision()

            return {
                "success": True,
                "from_revision": current_before,
                "to_revision": current_after,
                "target": target_revision,
            }

        except Exception as e:
            logger.error("Failed to rollback migration: %s", e)
            return {"success": False, "error": str(e)}

    def get_migration_history(self) -> list[dict[str, Any]]:
        """Get migration history."""
        try:
            alembic_cfg = self._get_alembic_config()
            script_dir = ScriptDirectory.from_config(alembic_cfg)

            history = []
            for revision in script_dir.walk_revisions():
                history.append({
                    "revision": revision.revision,
                    "down_revision": revision.down_revision,
                    "message": revision.doc,
                    "branch_labels": revision.branch_labels,
                    "depends_on": revision.depends_on,
                })

            return history

        except Exception as e:
            logger.error("Error getting migration history: %s", e)
            return []

    def validate_migrations(self) -> dict[str, Any]:
        """Validate migration scripts and database state."""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        try:
            # Check if migration directory exists
            if not os.path.exists(self.migration_directory):
                validation["errors"].append("Migration directory does not exist")
                validation["valid"] = False
                return validation

            # Check Alembic configuration
            try:
                alembic_cfg = self._get_alembic_config()
            except Exception as e:
                validation["errors"].append(f"Invalid Alembic configuration: {e}")
                validation["valid"] = False
                return validation

            # Check if database has migration table
            with self.db_manager.sync_engine.connect() as conn:
                migration_table = self.db_manager.config.migration_table

                if self.db_manager.config.db_type.value == "postgresql":
                    check_query = text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = :table_name
                        )
                    """)
                else:
                    # For other databases, use a generic approach
                    check_query = text(f"SELECT COUNT(*) FROM {migration_table} LIMIT 1")

                try:
                    result = conn.execute(check_query, {"table_name": migration_table})
                    if self.db_manager.config.db_type.value == "postgresql":
                        table_exists = result.scalar()
                    else:
                        table_exists = True  # If query succeeds, table exists
                except Exception:
                    table_exists = False

                if not table_exists:
                    validation["warnings"].append("Migration table does not exist - database may not be initialized")

            # Validate migration scripts syntax
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            try:
                list(script_dir.walk_revisions())
            except Exception as e:
                validation["errors"].append(f"Invalid migration scripts: {e}")
                validation["valid"] = False

        except Exception as e:
            validation["errors"].append(f"Validation error: {e}")
            validation["valid"] = False

        return validation


# Factory function
def create_migration_manager(db_manager, migration_directory: str | None = None) -> MigrationManager:
    """Create migration manager with the given database manager."""
    return MigrationManager(db_manager, migration_directory)
