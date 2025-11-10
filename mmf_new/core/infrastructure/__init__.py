"""Infrastructure layer base classes and interfaces."""

from .database import BaseModel, DatabaseManager
from .migration import MigrationManager, create_migration_manager
from .repository import SQLAlchemyDomainRepository, SQLAlchemyRepository
from .transaction import SQLAlchemyTransactionManager, create_transaction_manager
from .utilities import DatabaseUtilities, create_database_utilities

__all__ = [
    # Database management
    "DatabaseManager",
    "BaseModel",
    # Repository patterns
    "SQLAlchemyRepository",
    "SQLAlchemyDomainRepository",
    # Transaction management
    "SQLAlchemyTransactionManager",
    "create_transaction_manager",
    # Migration management
    "MigrationManager",
    "create_migration_manager",
    # Database utilities
    "DatabaseUtilities",
    "create_database_utilities",
]
