"""
CQRS (Command Query Responsibility Segregation) Implementation

Provides command and query handling, projections, and read model management
for scalable CQRS architecture patterns.
"""

import asyncio
import builtins
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from .core import Event

logger = logging.getLogger(__name__)

TCommand = TypeVar("TCommand", bound="Command")
TQuery = TypeVar("TQuery", bound="Query")
TResult = TypeVar("TResult")


class CommandStatus(Enum):
    """Command execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryType(Enum):
    """Query type classification."""

    SINGLE = "single"
    LIST = "list"
    AGGREGATE = "aggregate"
    SEARCH = "search"


@dataclass
class Command:
    """Base command class."""

    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_type: str = field(default="")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.command_type:
            self.command_type = self.__class__.__name__

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert command to dictionary."""
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "metadata": self.metadata,
            "data": {
                k: v
                for k, v in self.__dict__.items()
                if k
                not in [
                    "command_id",
                    "command_type",
                    "timestamp",
                    "correlation_id",
                    "causation_id",
                    "user_id",
                    "tenant_id",
                    "metadata",
                ]
            },
        }


@dataclass
class Query:
    """Base query class."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_type: str = field(default="")
    query_category: QueryType = QueryType.SINGLE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    tenant_id: str | None = None

    # Pagination
    page: int = 1
    page_size: int = 20

    # Sorting
    sort_by: str | None = None
    sort_order: str = "asc"

    # Filtering
    filters: builtins.dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.query_type:
            self.query_type = self.__class__.__name__


@dataclass
class QueryResult(Generic[TResult]):
    """Query result wrapper."""

    query_id: str
    data: TResult
    total_count: int | None = None
    page: int | None = None
    page_size: int | None = None
    has_more: bool = False
    execution_time_ms: float | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Command execution result."""

    command_id: str
    status: CommandStatus
    result_data: Any = None
    error_message: str | None = None
    events: builtins.list[Event] = field(default_factory=list)
    execution_time_ms: float | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


class CommandHandler(ABC, Generic[TCommand]):
    """Abstract command handler interface."""

    @abstractmethod
    async def handle(self, command: TCommand) -> CommandResult:
        """Handle the command."""
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, command: Command) -> bool:
        """Check if this handler can handle the command."""
        raise NotImplementedError


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Abstract query handler interface."""

    @abstractmethod
    async def handle(self, query: TQuery) -> QueryResult[TResult]:
        """Handle the query."""
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, query: Query) -> bool:
        """Check if this handler can handle the query."""
        raise NotImplementedError


class CommandBus:
    """Command bus for dispatching commands to handlers."""

    def __init__(self):
        self._handlers: builtins.dict[str, CommandHandler] = {}
        self._middleware: builtins.list[Callable] = []
        self._lock = asyncio.Lock()

    def register_handler(self, command_type: str, handler: CommandHandler) -> None:
        """Register command handler."""
        self._handlers[command_type] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to command pipeline."""
        self._middleware.append(middleware)

    async def send(self, command: Command) -> CommandResult:
        """Send command to appropriate handler."""
        start_time = datetime.utcnow()

        try:
            # Find handler
            handler = self._handlers.get(command.command_type)
            if not handler:
                return CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.FAILED,
                    error_message=f"No handler found for command type: {command.command_type}",
                )

            # Execute middleware pipeline
            for middleware in self._middleware:
                await middleware(command)

            # Handle command
            result = await handler.handle(command)

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.execution_time_ms = execution_time

            return result

        except Exception as e:
            logger.error(f"Error handling command {command.command_id}: {e}")
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time,
            )


class QueryBus:
    """Query bus for dispatching queries to handlers."""

    def __init__(self):
        self._handlers: builtins.dict[str, QueryHandler] = {}
        self._middleware: builtins.list[Callable] = []
        self._cache: builtins.dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    def register_handler(self, query_type: str, handler: QueryHandler) -> None:
        """Register query handler."""
        self._handlers[query_type] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to query pipeline."""
        self._middleware.append(middleware)

    def enable_caching(self, cache: builtins.dict[str, Any]) -> None:
        """Enable query result caching."""
        self._cache = cache

    async def send(self, query: Query) -> QueryResult:
        """Send query to appropriate handler."""
        start_time = datetime.utcnow()

        try:
            # Check cache first
            if self._cache and query.query_category == QueryType.SINGLE:
                cache_key = self._generate_cache_key(query)
                if cache_key in self._cache:
                    cached_result = self._cache[cache_key]
                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    cached_result.execution_time_ms = execution_time
                    return cached_result

            # Find handler
            handler = self._handlers.get(query.query_type)
            if not handler:
                raise ValueError(f"No handler found for query type: {query.query_type}")

            # Execute middleware pipeline
            for middleware in self._middleware:
                await middleware(query)

            # Handle query
            result = await handler.handle(query)

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.execution_time_ms = execution_time

            # Cache result if applicable
            if self._cache and query.query_category == QueryType.SINGLE:
                cache_key = self._generate_cache_key(query)
                self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Error handling query {query.query_id}: {e}")
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return QueryResult(
                query_id=query.query_id,
                data=None,
                execution_time_ms=execution_time,
                metadata={"error": str(e)},
            )

    def _generate_cache_key(self, query: Query) -> str:
        """Generate cache key for query."""
        return f"{query.query_type}:{hash(str(query.to_dict()))}"


class Projection(ABC):
    """Abstract projection for read models."""

    def __init__(self, projection_name: str):
        self.projection_name = projection_name
        self._version = 0
        self._last_processed_event = None
        self._last_updated = datetime.utcnow()

    @property
    def version(self) -> int:
        """Get projection version."""
        return self._version

    @property
    def last_processed_event(self) -> str | None:
        """Get last processed event ID."""
        return self._last_processed_event

    @property
    def last_updated(self) -> datetime:
        """Get last update timestamp."""
        return self._last_updated

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle event and update projection."""
        raise NotImplementedError

    @abstractmethod
    async def reset(self) -> None:
        """Reset projection to initial state."""
        raise NotImplementedError

    def _update_metadata(self, event: Event) -> None:
        """Update projection metadata."""
        self._version += 1
        self._last_processed_event = event.event_id
        self._last_updated = datetime.utcnow()


class ReadModelStore(ABC):
    """Abstract read model store interface."""

    @abstractmethod
    async def save(self, model_type: str, model_id: str, data: builtins.dict[str, Any]) -> None:
        """Save read model."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, model_type: str, model_id: str) -> builtins.dict[str, Any] | None:
        """Get read model by ID."""
        raise NotImplementedError

    @abstractmethod
    async def query(
        self,
        model_type: str,
        filters: builtins.dict[str, Any] = None,
        sort_by: str = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Query read models."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, model_type: str, model_id: str) -> None:
        """Delete read model."""
        raise NotImplementedError

    @abstractmethod
    async def count(self, model_type: str, filters: builtins.dict[str, Any] = None) -> int:
        """Count read models."""
        raise NotImplementedError


class InMemoryReadModelStore(ReadModelStore):
    """In-memory read model store implementation."""

    def __init__(self):
        self._models: builtins.dict[str, builtins.dict[str, builtins.dict[str, Any]]] = defaultdict(
            dict
        )
        self._lock = asyncio.Lock()

    async def save(self, model_type: str, model_id: str, data: builtins.dict[str, Any]) -> None:
        """Save read model."""
        async with self._lock:
            self._models[model_type][model_id] = data.copy()

    async def get(self, model_type: str, model_id: str) -> builtins.dict[str, Any] | None:
        """Get read model by ID."""
        async with self._lock:
            return self._models[model_type].get(model_id)

    async def query(
        self,
        model_type: str,
        filters: builtins.dict[str, Any] = None,
        sort_by: str = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Query read models."""
        async with self._lock:
            models = list(self._models[model_type].values())

            # Apply filters
            if filters:
                filtered_models = []
                for model in models:
                    if self._matches_filters(model, filters):
                        filtered_models.append(model)
                models = filtered_models

            # Apply sorting
            if sort_by:
                reverse = sort_order.lower() == "desc"
                models.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return models[start_idx:end_idx]

    async def delete(self, model_type: str, model_id: str) -> None:
        """Delete read model."""
        async with self._lock:
            if model_id in self._models[model_type]:
                del self._models[model_type][model_id]

    async def count(self, model_type: str, filters: builtins.dict[str, Any] = None) -> int:
        """Count read models."""
        async with self._lock:
            models = self._models[model_type].values()

            if not filters:
                return len(models)

            count = 0
            for model in models:
                if self._matches_filters(model, filters):
                    count += 1

            return count

    def _matches_filters(
        self, model: builtins.dict[str, Any], filters: builtins.dict[str, Any]
    ) -> bool:
        """Check if model matches filters."""
        for key, value in filters.items():
            if key not in model:
                return False

            if isinstance(value, dict):
                # Handle complex filters like {"$gt": 100}
                for op, op_value in value.items():
                    if not self._apply_filter_operation(model[key], op, op_value):
                        return False
            # Simple equality filter
            elif model[key] != value:
                return False

        return True

    def _apply_filter_operation(self, field_value: Any, operation: str, op_value: Any) -> bool:
        """Apply filter operation."""
        if operation == "$eq":
            return field_value == op_value
        if operation == "$ne":
            return field_value != op_value
        if operation == "$gt":
            return field_value > op_value
        if operation == "$gte":
            return field_value >= op_value
        if operation == "$lt":
            return field_value < op_value
        if operation == "$lte":
            return field_value <= op_value
        if operation == "$in":
            return field_value in op_value
        if operation == "$nin":
            return field_value not in op_value
        return False


class ProjectionManager:
    """Manages projections and their event handling."""

    def __init__(self, read_model_store: ReadModelStore):
        self.read_model_store = read_model_store
        self._projections: builtins.dict[str, Projection] = {}
        self._event_handlers: builtins.dict[str, builtins.list[Projection]] = defaultdict(list)

    def register_projection(self, projection: Projection) -> None:
        """Register projection."""
        self._projections[projection.projection_name] = projection

    def subscribe_to_event(self, event_type: str, projection: Projection) -> None:
        """Subscribe projection to event type."""
        if projection.projection_name not in self._projections:
            self.register_projection(projection)

        self._event_handlers[event_type].append(projection)

    async def handle_event(self, event: Event) -> None:
        """Handle event across all subscribed projections."""
        projections = self._event_handlers.get(event.event_type, [])

        tasks = []
        for projection in projections:
            tasks.append(asyncio.create_task(projection.handle_event(event)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def rebuild_projection(self, projection_name: str, events: builtins.list[Event]) -> None:
        """Rebuild projection from events."""
        projection = self._projections.get(projection_name)
        if not projection:
            raise ValueError(f"Projection {projection_name} not found")

        # Reset projection
        await projection.reset()

        # Replay events
        for event in events:
            await projection.handle_event(event)


# CQRS Patterns and Utilities


class CQRSError(Exception):
    """CQRS specific error."""


class CommandValidationError(CQRSError):
    """Command validation error."""


class QueryValidationError(CQRSError):
    """Query validation error."""


# Decorators for command and query handlers


def command_handler(command_type: str):
    """Decorator for command handlers."""

    def decorator(cls):
        cls._command_type = command_type
        return cls

    return decorator


def query_handler(query_type: str):
    """Decorator for query handlers."""

    def decorator(cls):
        cls._query_type = query_type
        return cls

    return decorator


# Convenience functions


def create_command_result(
    command_id: str,
    status: CommandStatus,
    result_data: Any = None,
    events: builtins.list[Event] = None,
) -> CommandResult:
    """Create command result."""
    return CommandResult(
        command_id=command_id,
        status=status,
        result_data=result_data,
        events=events or [],
    )


def create_query_result(
    query_id: str,
    data: Any,
    total_count: int = None,
    page: int = None,
    page_size: int = None,
) -> QueryResult:
    """Create query result."""
    return QueryResult(
        query_id=query_id,
        data=data,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=page is not None
        and page_size is not None
        and total_count is not None
        and (page * page_size) < total_count,
    )
