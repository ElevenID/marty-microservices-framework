"""
Core framework package for Marty Microservices Framework.

This package provides the foundational components for building microservices
using hexagonal (ports and adapters) architecture.
"""

from ..framework.infrastructure.config import (
    ConfigurationLoader,
    MMFConfiguration,
    SecretResolver,
    load_platform_configuration,
    load_service_configuration,
)
from .application.base import (
    BusinessRuleError,
    Command,
    CommandError,
    CommandResult,
    ConflictError,
    NotFoundError,
    Query,
    QueryResult,
    UnauthorizedError,
    ValidationError,
    WriteCommand,
)
from .application.handlers import CommandHandler, QueryHandler
from .domain.entity import AggregateRoot, DomainEvent, Entity, ValueObject
from .domain.ports.repository import (
    DomainRepository,
    EntityConflictError,
    EntityNotFoundError,
    Repository,
    RepositoryError,
    RepositoryValidationError,
)
from ..framework.infrastructure.messaging import CommandBus, QueryBus
from ..framework.infrastructure.persistence import InMemoryReadModelStore, ReadModelStore
from ..framework.infrastructure.repository import SQLAlchemyDomainRepository, SQLAlchemyRepository

__version__ = "2.0.0"

# Re-export core components for convenient access

# Re-export existing framework repository errors for convenience
# Removed old framework dependency to avoid circular imports

__all__ = [
    "Command",
    "Query",
    "WriteCommand",
    "CommandResult",
    "QueryResult",
    "CommandHandler",
    "QueryHandler",
    "CommandBus",
    "QueryBus",
    "Entity",
    "AggregateRoot",
    "ValueObject",
    "DomainEvent",
    "Repository",
    "DomainRepository",
    "SQLAlchemyRepository",
    "SQLAlchemyDomainRepository",
    "ReadModelStore",
    "InMemoryReadModelStore",
    "MMFConfiguration",
    "ConfigurationLoader",
    "SecretResolver",
    "load_service_configuration",
    "load_platform_configuration",
    "CommandError",
    "ValidationError",
    "BusinessRuleError",
    "NotFoundError",
    "UnauthorizedError",
    "ConflictError",
    "RepositoryError",
    "EntityNotFoundError",
    "EntityConflictError",
    "RepositoryValidationError",
]
