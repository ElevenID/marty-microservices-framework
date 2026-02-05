"""Database migration infrastructure for MMF framework.

This module provides hexagonal architecture-compliant migration support using Alembic.
The migration infrastructure follows the ports/adapters pattern:
- MigrationManagerPort: Abstract port interface (application layer)
- AlembicMigrationAdapter: Concrete adapter implementation (infrastructure layer)
"""

from .adapters import AlembicMigrationAdapter
from .ports import MigrationError, MigrationManagerPort

__all__ = ["MigrationManagerPort", "AlembicMigrationAdapter", "MigrationError"]
