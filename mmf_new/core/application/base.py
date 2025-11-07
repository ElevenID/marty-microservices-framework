"""Base command interface for all application commands and queries."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class CommandStatus(Enum):
    """Command execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CommandResult(Generic[TResponse]):
    """Command execution result with metadata."""

    request_id: str
    status: CommandStatus
    data: TResponse | None = None
    error_message: str | None = None
    execution_time_ms: float | None = None
    events_generated: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if the command executed successfully."""
        return self.status == CommandStatus.COMPLETED and self.error_message is None

    @property
    def is_failure(self) -> bool:
        """Check if the command failed."""
        return self.status == CommandStatus.FAILED or self.error_message is not None


@dataclass
class CommandRequest:
    """Base request class with tracking metadata."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    causation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryRequest(CommandRequest):
    """Base query request with pagination and filtering."""

    # Pagination
    page: int = 1
    page_size: int = 20

    # Sorting
    sort_by: str | None = None
    sort_order: str = "asc"

    # Filtering
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult(Generic[TResponse]):
    """Query result with pagination metadata."""

    request_id: str
    data: TResponse
    total_count: int | None = None
    page: int | None = None
    page_size: int | None = None
    has_more: bool = False
    execution_time_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Command(ABC, Generic[TRequest, TResponse]):
    """Base class for all commands in the application layer.

    Commands represent the application-specific business rules.
    They orchestrate the flow of data to and from the entities,
    and direct those entities to use their business rules to
    achieve the goals of the command.
    """

    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """Execute the command with the given request.

        Args:
            request: The input data for the command

        Returns:
            The response data from the command
        """
        ...

    async def execute_with_result(self, request: TRequest) -> CommandResult[TResponse]:
        """Execute command and return detailed result with metadata.

        Args:
            request: The input data for the command

        Returns:
            Detailed execution result with status and metadata
        """
        request_id = getattr(request, "request_id", str(uuid4()))
        start_time = datetime.now(timezone.utc)

        try:
            result = await self.execute(request)
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds() * 1000

            return CommandResult(
                request_id=request_id,
                status=CommandStatus.COMPLETED,
                data=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds() * 1000

            return CommandResult(
                request_id=request_id,
                status=CommandStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time,
            )


class Query(Command[TRequest, TResponse]):
    """Base class for query commands that read data without side effects.

    Queries should be idempotent and not modify system state.
    """

    async def execute_paginated(self, request: TRequest) -> QueryResult[TResponse]:
        """Execute query with pagination support.

        Args:
            request: Query request with pagination parameters

        Returns:
            Paginated query result
        """
        start_time = datetime.now(timezone.utc)

        try:
            result = await self.execute(request)
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds() * 1000

            # Extract pagination info if request has it
            page = getattr(request, "page", None)
            page_size = getattr(request, "page_size", None)
            request_id = getattr(request, "request_id", str(uuid4()))

            return QueryResult(
                request_id=request_id,
                data=result,
                page=page,
                page_size=page_size,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            raise QueryError(f"Query execution failed: {str(e)}") from e


class WriteCommand(Command[TRequest, TResponse]):
    """Base class for write commands that modify data or have side effects.

    Write commands should be designed to be idempotent when possible.
    """

    async def execute_with_events(self, request: TRequest) -> CommandResult[TResponse]:
        """Execute command and track any domain events generated.

        Args:
            request: Command request

        Returns:
            Command result with any generated events
        """
        result = await self.execute_with_result(request)

        # TODO: Hook into domain event collection from aggregate roots
        # This would integrate with the AggregateRoot.domain_events property

        return result


# Command Error Hierarchy
class CommandError(Exception):
    """Base exception for command errors."""


class ValidationError(CommandError):
    """Raised when input validation fails."""


class BusinessRuleError(CommandError):
    """Raised when business rule validation fails."""


class NotFoundError(CommandError):
    """Raised when requested entity is not found."""


class UnauthorizedError(CommandError):
    """Raised when user is not authorized to perform action."""


class ConflictError(CommandError):
    """Raised when operation conflicts with current state."""


class QueryError(CommandError):
    """Raised when query execution fails."""


class WriteError(CommandError):
    """Raised when write command execution fails."""


# Factory functions for common command patterns
def create_simple_query(execute_func) -> type[Query]:
    """Create a simple query command from a function.

    Args:
        execute_func: Async function that takes request and returns response

    Returns:
        Query command class
    """

    class SimpleQuery(Query):
        async def execute(self, request: Any) -> Any:
            return await execute_func(request)

    return SimpleQuery


def create_simple_write_command(execute_func) -> type[WriteCommand]:
    """Create a simple write command from a function.

    Args:
        execute_func: Async function that takes request and returns response

    Returns:
        Write command class
    """

    class SimpleWriteCommand(WriteCommand):
        async def execute(self, request: Any) -> Any:
            return await execute_func(request)

    return SimpleWriteCommand
