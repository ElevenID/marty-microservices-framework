"""Utility functions for CQRS operations."""

from typing import Any

from .base import Command, CommandResult, CommandStatus, Query, QueryResult


def create_command_result(
    request_id: str,
    status: CommandStatus,
    data: Any = None,
    events_generated: list[Any] | None = None,
) -> CommandResult:
    """Create command result."""
    return CommandResult(
        request_id=request_id,
        status=status,
        data=data,
        events_generated=events_generated or [],
    )


def create_query_result(
    request_id: str,
    data: Any,
    total_count: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> QueryResult:
    """Create query result."""
    return QueryResult(
        request_id=request_id,
        data=data,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=page is not None
        and page_size is not None
        and total_count is not None
        and (page * page_size) < total_count,
    )
