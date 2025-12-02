"""Command and Query handler interfaces for the application layer."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .base import Command, CommandResult, Query, QueryResult

TCommand = TypeVar("TCommand", bound=Command)
TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


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
