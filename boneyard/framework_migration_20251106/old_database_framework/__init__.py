"""
Enterprise database framework for microservices.

This module provides:
- Database per service isolation
- Repository patterns
- Transaction management
- Connection pooling
- Audit logging capabilities
- Database utilities
- Outbox pattern for reliable event publishing

Example usage:
from marty_msf.framework.database import DatabaseConfig, DatabaseManager, Repository

    # Configure database for a service
    config = DatabaseConfig(
        service_name="user-service",
        database="user_db",
        host="localhost",
        port=5432,
        username="user_svc",
        password="password"
    )

    # Create database manager
    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    # Create repository
    user_repository = Repository(db_manager, UserModel)

    # Use repository
    user = await user_repository.create({"name": "John", "email": "john@example.com"})
"""

# Outbox pattern components
from ...patterns.outbox.enhanced_outbox import EnhancedOutboxEvent as OutboxEvent
from ...patterns.outbox.enhanced_outbox import (
    EnhancedOutboxRepository as OutboxRepository,
)
from .config import ConnectionPoolConfig, DatabaseConfig, DatabaseType
from .manager import (
    ConnectionError,
    DatabaseError,
    DatabaseManager,
    close_all_database_managers,
    create_database_manager,
    get_database_manager,
    health_check_all_databases,
    register_database_manager,
)
from .models import (
    AuditMixin,
    BaseModel,
    FullAuditModel,
    MetadataMixin,
    ServiceAuditLog,
    ServiceConfiguration,
    ServiceHealthCheck,
    SimpleModel,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)
from .repository import (
    BaseRepository,
    ConflictError,
    NotFoundError,
    Repository,
    RepositoryError,
    ValidationError,
    create_repository,
)
from .transaction import (
    DeadlockError,
    IsolationLevel,
    RetryableError,
    TransactionConfig,
    TransactionError,
    TransactionManager,
    execute_bulk_operations,
    execute_in_transaction,
    execute_with_savepoints,
    handle_database_errors,
    transactional,
)
from .utilities import (
    DatabaseUtilities,
    check_all_database_connections,
    cleanup_all_soft_deleted,
    get_database_utilities,
)

# Create aliases for backward compatibility
DatabaseConnection = DatabaseManager

__all__ = [
    "AuditMixin",
    # Models
    "BaseModel",
    # Repository
    "BaseRepository",
    "ConflictError",
    "ConnectionError",
    "ConnectionPoolConfig",
    "DatabaseConfig",
    "DatabaseConnection",
    "DatabaseError",
    # Manager
    "DatabaseManager",
    # Config
    "DatabaseType",
    # Utilities
    "DatabaseUtilities",
    "DeadlockError",
    "FullAuditModel",
    # Transaction
    "IsolationLevel",
    "MetadataMixin",
    "NotFoundError",
    # Outbox pattern
    "OutboxEvent",
    "OutboxRepository",
    "Repository",
    "RepositoryError",
    "RetryableError",
    "ServiceAuditLog",
    "ServiceConfiguration",
    "ServiceHealthCheck",
    "SimpleModel",
    "SoftDeleteMixin",
    "TimestampMixin",
    "TransactionConfig",
    "TransactionError",
    "TransactionManager",
    "UUIDMixin",
    "ValidationError",
    "check_all_database_connections",
    "cleanup_all_soft_deleted",
    "close_all_database_managers",
    "create_database_manager",
    "create_repository",
    "execute_bulk_operations",
    "execute_in_transaction",
    "execute_with_savepoints",
    "get_database_manager",
    "get_database_utilities",
    "handle_database_errors",
    "health_check_all_databases",
    "register_database_manager",
    "transactional",
]

# Version
__version__ = "1.0.0"
