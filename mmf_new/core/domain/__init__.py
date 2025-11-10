"""Domain layer base classes and interfaces."""

from .entity import AggregateRoot, DomainEvent, Entity, ValueObject
from .repository import (
    DomainRepository,
    EntityConflictError,
    EntityNotFoundError,
    Repository,
    RepositoryError,
    RepositoryValidationError,
)

__all__ = [
    "Entity",
    "AggregateRoot",
    "ValueObject",
    "DomainEvent",
    "Repository",
    "DomainRepository",
    "RepositoryError",
    "EntityNotFoundError",
    "EntityConflictError",
    "RepositoryValidationError",
]
