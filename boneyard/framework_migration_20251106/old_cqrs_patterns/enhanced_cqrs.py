"""
Enhanced CQRS (Command Query Responsibility Segregation) Templates for Marty Microservices Framework

This module provides comprehensive CQRS templates and samples with:
- Advanced command/query handlers with validation
- Read model projections and builders
- Event-driven read model updates
- Materialized view management
- Performance optimization patterns
- Sample implementations for common scenarios
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Type variables for generic types
TCommand = TypeVar('TCommand')
TQuery = TypeVar('TQuery')
TResult = TypeVar('TResult')
TAggregate = TypeVar('TAggregate')
TEvent = TypeVar('TEvent')

Base = declarative_base()


class CommandStatus(Enum):
    """Command execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryExecutionMode(Enum):
    """Query execution modes."""
    SYNC = "sync"
    ASYNC = "async"
    CACHED = "cached"
    EVENTUAL_CONSISTENCY = "eventual_consistency"


@dataclass
class ValidationResult:
    """Result of command/query validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CommandResult:
    """Result of command execution."""
    command_id: str
    status: CommandStatus
    result_data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    execution_time_ms: int = 0
    events_generated: list[str] = field(default_factory=list)


@dataclass
class QueryResult:
    """Result of query execution."""
    query_id: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    cache_hit: bool = False
    staleness_ms: int = 0


class BaseCommand(ABC):
    """Enhanced base command with validation and metadata."""

    def __init__(self, command_id: str = None, correlation_id: str = None):
        self.command_id = command_id or str(uuid.uuid4())
        self.correlation_id = correlation_id
        self.timestamp = datetime.now(timezone.utc)
        self.metadata: dict[str, Any] = {}

    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate command data."""
        pass

    def to_dict(self) -> dict[str, Any]:
        """Convert command to dictionary."""
        return {
            'command_id': self.command_id,
            'command_type': self.__class__.__name__,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            **self._get_command_data()
        }

    @abstractmethod
    def _get_command_data(self) -> dict[str, Any]:
        """Get command-specific data."""
        pass


class BaseQuery(ABC):
    """Enhanced base query with filtering and pagination."""

    def __init__(self, query_id: str = None, correlation_id: str = None):
        self.query_id = query_id or str(uuid.uuid4())
        self.correlation_id = correlation_id
        self.timestamp = datetime.now(timezone.utc)
        self.metadata: dict[str, Any] = {}

        # Common query parameters
        self.page: int = 1
        self.page_size: int = 50
        self.sort_by: str | None = None
        self.sort_order: str = "asc"
        self.filters: dict[str, Any] = {}
        self.include_total_count: bool = True

    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate query parameters."""
        pass

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            'query_id': self.query_id,
            'query_type': self.__class__.__name__,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat(),
            'page': self.page,
            'page_size': self.page_size,
            'sort_by': self.sort_by,
            'sort_order': self.sort_order,
            'filters': self.filters,
            'metadata': self.metadata,
            **self._get_query_data()
        }

    @abstractmethod
    def _get_query_data(self) -> dict[str, Any]:
        """Get query-specific data."""
        pass


class CommandHandler(ABC, Generic[TCommand]):
    """Enhanced base command handler with validation and error handling."""

    def __init__(self, event_store=None, event_bus=None):
        self.event_store = event_store
        self.event_bus = event_bus

    async def handle(self, command: TCommand) -> CommandResult:
        """Handle command with full lifecycle management."""
        start_time = datetime.now()

        try:
            # Validate command
            validation_result = command.validate()
            if not validation_result.is_valid:
                return CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    errors=validation_result.errors
                )

            # Execute command
            result = await self._execute(command)

            # Calculate execution time
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result.execution_time_ms = execution_time

            # Publish events if event bus is available
            if self.event_bus and result.events_generated:
                await self._publish_events(result.events_generated)

            return result

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    @abstractmethod
    async def _execute(self, command: TCommand) -> CommandResult:
        """Execute the command logic."""
        pass

    async def _publish_events(self, event_ids: list[str]) -> None:
        """Publish domain events."""
        if self.event_bus:
            for _event_id in event_ids:
                # Implementation would depend on event bus interface
                pass


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Enhanced base query handler with caching and performance optimization."""

    def __init__(self, read_store=None, cache=None):
        self.read_store = read_store
        self.cache = cache
        self.execution_mode = QueryExecutionMode.SYNC

    async def handle(self, query: TQuery) -> QueryResult:
        """Handle query with caching and performance optimization."""
        start_time = datetime.now()
        cache_hit = False

        try:
            # Validate query
            validation_result = query.validate()
            if not validation_result.is_valid:
                return QueryResult(
                    query_id=query.query_id,
                    metadata={'errors': validation_result.errors}
                )

            # Check cache if available
            cache_key = self._get_cache_key(query)
            if self.cache and cache_key:
                cached_result = await self._get_from_cache(cache_key)
                if cached_result:
                    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    return QueryResult(
                        query_id=query.query_id,
                        data=cached_result,
                        execution_time_ms=execution_time,
                        cache_hit=True
                    )

            # Execute query
            data = await self._execute(query)

            # Cache result if caching is enabled
            if self.cache and cache_key:
                await self._store_in_cache(cache_key, data)

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return QueryResult(
                query_id=query.query_id,
                data=data,
                execution_time_ms=execution_time,
                cache_hit=cache_hit
            )

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return QueryResult(
                query_id=query.query_id,
                metadata={'errors': [str(e)]},
                execution_time_ms=execution_time
            )

    @abstractmethod
    async def _execute(self, query: TQuery) -> dict[str, Any]:
        """Execute the query logic."""
        pass

    def _get_cache_key(self, query: TQuery) -> str | None:
        """Generate cache key for query."""
        # Default implementation - can be overridden
        query_data = query.to_dict()
        return f"{query.__class__.__name__}:{hash(str(query_data))}"

    async def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Get result from cache."""
        # Implementation depends on cache interface
        return None

    async def _store_in_cache(self, cache_key: str, data: dict[str, Any]) -> None:
        """Store result in cache."""
        # Implementation depends on cache interface
        pass


class ReadModel(Base):
    """Enhanced base read model with metadata and versioning."""

    __abstract__ = True

    id = Column(String(255), primary_key=True)
    aggregate_id = Column(String(255), nullable=False, index=True)
    aggregate_type = Column(String(100), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Metadata for tracking data lineage
    last_event_id = Column(String(255), nullable=True)
    last_event_timestamp = Column(DateTime, nullable=True)
    projection_version = Column(String(50), nullable=False, default="1.0")

    # Soft delete support
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)


class EventProjection(ABC):
    """Enhanced base event projection for building read models."""

    def __init__(self, projection_name: str, version: str = "1.0"):
        self.projection_name = projection_name
        self.version = version
        self.supported_events: dict[str, Callable] = {}

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Register handler for specific event type."""
        self.supported_events[event_type] = handler

    async def project(self, event: dict[str, Any], session: Session) -> bool:
        """Project event to read model."""
        event_type = event.get('event_type')

        if event_type not in self.supported_events:
            logger.debug(f"No handler for event type: {event_type}")
            return False

        try:
            handler = self.supported_events[event_type]
            await handler(event, session)
            return True

        except Exception as e:
            logger.error(f"Projection failed for event {event.get('event_id')}: {e}")
            return False

    @abstractmethod
    async def handle_created_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle entity created event."""
        pass

    @abstractmethod
    async def handle_updated_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle entity updated event."""
        pass

    @abstractmethod
    async def handle_deleted_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle entity deleted event."""
        pass


class ProjectionBuilder:
    """Builder for creating and managing projections."""

    def __init__(self, event_store, read_store):
        self.event_store = event_store
        self.read_store = read_store
        self.projections: dict[str, EventProjection] = {}

    def register_projection(self, projection: EventProjection) -> None:
        """Register a projection."""
        self.projections[projection.projection_name] = projection

    async def rebuild_projection(self, projection_name: str, from_event_id: str = None) -> None:
        """Rebuild a projection from events."""
        if projection_name not in self.projections:
            raise ValueError(f"Projection {projection_name} not found")

        projection = self.projections[projection_name]

        # Get events from event store
        events = await self._get_events_for_projection(projection_name, from_event_id)

        # Process events in order
        async with self.read_store.get_session() as session:
            for event in events:
                await projection.project(event, session)
            await session.commit()

    async def _get_events_for_projection(
        self,
        projection_name: str,
        from_event_id: str = None
    ) -> list[dict[str, Any]]:
        """Get events for projection rebuild."""
        # Implementation depends on event store interface
        return []


# Sample implementations
@dataclass
class CreateUserCommand(BaseCommand):
    """Sample command for creating a user."""

    def __init__(self, email: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.email = email
        self.name = name

    def validate(self) -> ValidationResult:
        """Validate create user command."""
        errors = []

        if not self.email:
            errors.append("Email is required")
        elif "@" not in self.email:
            errors.append("Invalid email format")

        if not self.name:
            errors.append("Name is required")
        elif len(self.name) < 2:
            errors.append("Name must be at least 2 characters")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_command_data(self) -> dict[str, Any]:
        return {"email": self.email, "name": self.name}


@dataclass
class GetUserQuery(BaseQuery):
    """Sample query for getting user information."""

    def __init__(self, user_id: str = None, email: str = None, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.email = email

    def validate(self) -> ValidationResult:
        """Validate get user query."""
        errors = []

        if not self.user_id and not self.email:
            errors.append("Either user_id or email must be provided")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_query_data(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "email": self.email}


class UserReadModel(ReadModel):
    """Sample read model for user data."""

    __tablename__ = "user_read_models"

    # User-specific fields
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    profile_data = Column(JSON, nullable=True)

    # Derived/computed fields
    display_name = Column(String(255), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    total_orders = Column(Integer, nullable=False, default=0)
    total_spent = Column(Integer, nullable=False, default=0)  # in cents


class CreateUserCommandHandler(CommandHandler[CreateUserCommand]):
    """Sample command handler for creating users."""

    async def _execute(self, command: CreateUserCommand) -> CommandResult:
        """Execute create user command."""
        try:
            # Simulate user creation
            user_id = str(uuid.uuid4())

            # In real implementation, this would interact with the domain model
            # and persist the user entity

            # Generate domain events
            event_id = str(uuid.uuid4())

            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.COMPLETED,
                result_data={"user_id": user_id},
                events_generated=[event_id]
            )

        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                errors=[str(e)]
            )


class GetUserQueryHandler(QueryHandler[GetUserQuery, dict]):
    """Sample query handler for getting user data."""

    async def _execute(self, query: GetUserQuery) -> dict[str, Any]:
        """Execute get user query."""
        # In real implementation, this would query the read model

        # Simulate user data retrieval
        if query.user_id:
            user_data = {
                "user_id": query.user_id,
                "email": f"user_{query.user_id}@example.com",
                "name": f"User {query.user_id}",
                "status": "active",
                "total_orders": 5,
                "total_spent": 25000
            }
        elif query.email:
            user_data = {
                "user_id": str(uuid.uuid4()),
                "email": query.email,
                "name": "Sample User",
                "status": "active",
                "total_orders": 3,
                "total_spent": 15000
            }
        else:
            user_data = {}

        return user_data


class UserProjection(EventProjection):
    """Sample projection for user read models."""

    def __init__(self):
        super().__init__("user_projection", "1.0")

        # Register event handlers
        self.register_event_handler("user_created", self.handle_created_event)
        self.register_event_handler("user_updated", self.handle_updated_event)
        self.register_event_handler("user_deleted", self.handle_deleted_event)

    async def handle_created_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle user created event."""
        event_data = event.get('data', {})

        user_read_model = UserReadModel(
            id=str(uuid.uuid4()),
            aggregate_id=event.get('aggregate_id'),
            aggregate_type=event.get('aggregate_type'),
            email=event_data.get('email'),
            name=event_data.get('name'),
            display_name=event_data.get('name'),
            last_event_id=event.get('event_id'),
            last_event_timestamp=datetime.fromisoformat(event.get('timestamp'))
        )

        session.add(user_read_model)

    async def handle_updated_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle user updated event."""
        user_read_model = session.query(UserReadModel).filter_by(
            aggregate_id=event.get('aggregate_id')
        ).first()

        if user_read_model:
            event_data = event.get('data', {})

            # Update fields
            if 'name' in event_data:
                user_read_model.name = event_data['name']
                user_read_model.display_name = event_data['name']

            if 'email' in event_data:
                user_read_model.email = event_data['email']

            # Update metadata
            user_read_model.updated_at = datetime.now(timezone.utc)
            user_read_model.last_event_id = event.get('event_id')
            user_read_model.last_event_timestamp = datetime.fromisoformat(event.get('timestamp'))
            user_read_model.version += 1

    async def handle_deleted_event(self, event: dict[str, Any], session: Session) -> None:
        """Handle user deleted event."""
        user_read_model = session.query(UserReadModel).filter_by(
            aggregate_id=event.get('aggregate_id')
        ).first()

        if user_read_model:
            # Soft delete
            user_read_model.is_deleted = True
            user_read_model.deleted_at = datetime.now(timezone.utc)
            user_read_model.updated_at = datetime.now(timezone.utc)
            user_read_model.last_event_id = event.get('event_id')
            user_read_model.last_event_timestamp = datetime.fromisoformat(event.get('timestamp'))


# Factory functions for easy integration
def create_command_handler(handler_class, **dependencies):
    """Create command handler with dependencies."""
    return handler_class(**dependencies)


def create_query_handler(handler_class, **dependencies):
    """Create query handler with dependencies."""
    return handler_class(**dependencies)


def create_projection_builder(event_store, read_store):
    """Create projection builder with stores."""
    return ProjectionBuilder(event_store, read_store)


# Decorator for automatic command/query handling
def command_handler(command_type):
    """Decorator for registering command handlers."""
    def decorator(handler_class):
        # Registration logic would go here
        return handler_class
    return decorator


def query_handler(query_type):
    """Decorator for registering query handlers."""
    def decorator(handler_class):
        # Registration logic would go here
        return handler_class
    return decorator
