"""Command and Query buses for dispatching to handlers."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..application.base import Command, CommandResult, CommandStatus, Query, QueryResult
from ..application.handlers import CommandHandler, QueryHandler

logger = logging.getLogger(__name__)


class CommandBus:
    """Command bus for dispatching commands to handlers."""

    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
        self._middleware: list[Callable] = []
        self._lock = asyncio.Lock()

    def register_handler(self, command_type: str, handler: CommandHandler) -> None:
        """Register command handler."""
        self._handlers[command_type] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to command pipeline."""
        self._middleware.append(middleware)

    async def send(self, command: Command) -> CommandResult:
        """Send command to appropriate handler."""
        start_time = datetime.now()
        command_type = type(command).__name__

        try:
            # Find handler
            handler = self._handlers.get(command_type)
            if not handler:
                return CommandResult(
                    request_id=getattr(command, "request_id", "unknown"),
                    status=CommandStatus.FAILED,
                    error_message=f"No handler found for command type: {command_type}",
                )

            # Execute middleware pipeline
            for middleware in self._middleware:
                await middleware(command)

            # Handle command
            result = await handler.handle(command)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            result.execution_time_ms = execution_time

            return result

        except Exception as e:
            logger.error(f"Error handling command {getattr(command, 'request_id', 'unknown')}: {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return CommandResult(
                request_id=getattr(command, "request_id", "unknown"),
                status=CommandStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time,
            )


class QueryBus:
    """Query bus for dispatching queries to handlers."""

    def __init__(self):
        self._handlers: dict[str, QueryHandler] = {}
        self._middleware: list[Callable] = []
        self._cache: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    def register_handler(self, query_type: str, handler: QueryHandler) -> None:
        """Register query handler."""
        self._handlers[query_type] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to query pipeline."""
        self._middleware.append(middleware)

    def enable_caching(self, cache: dict[str, Any]) -> None:
        """Enable query result caching."""
        self._cache = cache

    async def send(self, query: Query) -> QueryResult:
        """Send query to appropriate handler."""
        start_time = datetime.now()
        query_type = type(query).__name__

        try:
            # Check cache first
            if self._cache:
                cache_key = self._generate_cache_key(query)
                if cache_key in self._cache:
                    cached_result = self._cache[cache_key]
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    cached_result.execution_time_ms = execution_time
                    return cached_result

            # Find handler
            handler = self._handlers.get(query_type)
            if not handler:
                raise ValueError(f"No handler found for query type: {query_type}")

            # Execute middleware pipeline
            for middleware in self._middleware:
                await middleware(query)

            # Handle query
            result = await handler.handle(query)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            result.execution_time_ms = execution_time

            # Cache result if applicable
            if self._cache:
                cache_key = self._generate_cache_key(query)
                self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Error handling query {getattr(query, 'request_id', 'unknown')}: {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return QueryResult(
                request_id=getattr(query, "request_id", "unknown"),
                data=None,
                execution_time_ms=execution_time,
                metadata={"error": str(e)},
            )

    def _generate_cache_key(self, query: Query) -> str:
        """Generate cache key for query."""
        return f"{type(query).__name__}:{hash(str(query.__dict__))}"
