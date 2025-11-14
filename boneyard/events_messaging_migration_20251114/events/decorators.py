"""
Event Publishing Decorators

Decorators for automatic event publishing on method success/failure using Enhanced Event Bus.
"""

import asyncio
import functools
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from marty_msf.core.enhanced_di import get_service

from .enhanced_event_bus import (
    BaseEvent,
    EnhancedEventBus,
    EventMetadata,
    EventPriority,
)
from .event_bus_service import EventBusService
from .types import AuditEventType

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _get_event_bus() -> EnhancedEventBus:
    """Get the event bus instance from the DI container."""
    event_bus_service = get_service(EventBusService)
    return event_bus_service.get_event_bus()


def initialize_event_bus_service() -> None:
    """Initialize the event bus service."""
    event_bus_service = get_service(EventBusService)
    if not event_bus_service.is_initialized:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule initialization in the background
            loop.create_task(event_bus_service.initialize())
        else:
            loop.run_until_complete(event_bus_service.initialize())


def audit_event(
    event_type: AuditEventType,
    action: str,
    resource_type: str,
    resource_id_field: str | None = None,
    success_only: bool = False,
    include_args: bool = False,
    include_result: bool = False,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """
    Decorator to automatically publish audit events when a method is called.

    Args:
        event_type: Type of audit event
        action: Action being performed
        resource_type: Type of resource being acted upon
        resource_id_field: Field name in args/kwargs containing resource ID
        success_only: Only publish on successful execution
        include_args: Include method arguments in event data
        include_result: Include method result in event data
        priority: Event priority level

    Returns:
        Decorated function that publishes audit events
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Execute the original function
                result = await func(*args, **kwargs)

                # Publish audit event on success
                try:
                    event_bus = _get_event_bus()

                    # Extract resource ID if specified
                    resource_id = None
                    if resource_id_field:
                        # Look for resource_id_field in kwargs first, then args
                        if resource_id_field in kwargs:
                            resource_id = str(kwargs[resource_id_field])
                        elif args and len(args) > 0:
                            # Try to find in args by name (assume first arg if no kwargs)
                            resource_id = str(args[0])

                    # Build event data
                    event_data = {
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "outcome": "success",
                    }

                    if include_args:
                        event_data["arguments"] = {
                            "args": [str(arg) for arg in args],
                            "kwargs": {k: str(v) for k, v in kwargs.items()},
                        }

                    if include_result:
                        event_data["result"] = str(result)

                    # Create and publish event
                    event = BaseEvent(
                        event_type=f"audit.{event_type.value}",
                        data=event_data,
                        metadata=EventMetadata(
                            event_id=str(uuid.uuid4()),
                            event_type=f"audit.{event_type.value}",
                            timestamp=datetime.now(timezone.utc),
                            priority=priority,
                        ),
                    )

                    await event_bus.publish(event)

                except Exception as e:
                    logger.error(f"Failed to publish audit event: {e}")

                return result

            except Exception as e:
                # Publish audit event on failure if not success_only
                if not success_only:
                    try:
                        event_bus = _get_event_bus()

                        event_data = {
                            "action": action,
                            "resource_type": resource_type,
                            "outcome": "failure",
                            "error": str(e),
                        }

                        if include_args:
                            event_data["arguments"] = {
                                "args": [str(arg) for arg in args],
                                "kwargs": {k: str(v) for k, v in kwargs.items()},
                            }

                        event = BaseEvent(
                            event_type=f"audit.{event_type.value}",
                            data=event_data,
                            metadata=EventMetadata(
                                event_id=str(uuid.uuid4()),
                                event_type=f"audit.{event_type.value}",
                                timestamp=datetime.now(timezone.utc),
                                priority=EventPriority.HIGH,  # Failures are high priority
                            ),
                        )

                        await event_bus.publish(event)

                    except Exception as publish_error:
                        logger.error(f"Failed to publish audit failure event: {publish_error}")

                # Re-raise the original exception
                raise

        return wrapper

    return decorator


def domain_event(
    aggregate_type: str,
    event_type: str,
    aggregate_id_field: str | None = None,
    include_result: bool = True,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """
    Decorator to automatically publish domain events when a method is called.

    Args:
        aggregate_type: Type of domain aggregate
        event_type: Type of domain event
        aggregate_id_field: Field name containing aggregate ID
        include_result: Include method result in event data
        priority: Event priority level

    Returns:
        Decorated function that publishes domain events
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the original function
            result = await func(*args, **kwargs)

            try:
                event_bus = _get_event_bus()

                # Extract aggregate ID if specified
                aggregate_id = None
                if aggregate_id_field:
                    if aggregate_id_field in kwargs:
                        aggregate_id = str(kwargs[aggregate_id_field])
                    elif args and len(args) > 0:
                        aggregate_id = str(args[0])

                # Build event data
                event_data = {
                    "aggregate_type": aggregate_type,
                    "aggregate_id": aggregate_id,
                }

                if include_result:
                    event_data["result"] = str(result) if result is not None else None

                # Create and publish domain event
                event = BaseEvent(
                    event_type=f"domain.{aggregate_type}.{event_type}",
                    data=event_data,
                    metadata=EventMetadata(
                        event_id=str(uuid.uuid4()),
                        event_type=f"domain.{aggregate_type}.{event_type}",
                        timestamp=datetime.now(timezone.utc),
                        correlation_id=aggregate_id,
                        priority=priority,
                    ),
                )

                await event_bus.publish(event)

            except Exception as e:
                logger.error(f"Failed to publish domain event: {e}")

            return result

        return wrapper

    return decorator


def publish_on_success(
    event_type: str,
    event_data_builder: Callable[..., dict] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """
    Decorator to publish events only on successful method execution.

    Args:
        event_type: Type of event to publish
        event_data_builder: Function to build event data from method args/result
        priority: Event priority level

    Returns:
        Decorated function that publishes events on success
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            try:
                event_bus = _get_event_bus()

                # Build event data
                if event_data_builder:
                    event_data = event_data_builder(*args, result=result, **kwargs)
                else:
                    event_data = {"method": func.__name__, "result": str(result)}

                event = BaseEvent(
                    event_type=event_type,
                    data=event_data,
                    metadata=EventMetadata(
                        event_id=str(uuid.uuid4()),
                        event_type=event_type,
                        timestamp=datetime.now(timezone.utc),
                        priority=priority,
                    ),
                )

                await event_bus.publish(event)

            except Exception as e:
                logger.error(f"Failed to publish success event: {e}")

            return result

        return wrapper

    return decorator


def publish_on_error(
    event_type: str,
    event_data_builder: Callable[..., dict] | None = None,
    priority: EventPriority = EventPriority.HIGH,
) -> Callable[[F], F]:
    """
    Decorator to publish events only on method execution failure.

    Args:
        event_type: Type of event to publish
        event_data_builder: Function to build event data from method args/error
        priority: Event priority level (defaults to HIGH for errors)

    Returns:
        Decorated function that publishes events on error
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                try:
                    event_bus = _get_event_bus()

                    # Build event data
                    if event_data_builder:
                        event_data = event_data_builder(*args, error=e, **kwargs)
                    else:
                        event_data = {
                            "method": func.__name__,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }

                    event = BaseEvent(
                        event_type=event_type,
                        data=event_data,
                        metadata=EventMetadata(
                            event_id=str(uuid.uuid4()),
                            event_type=event_type,
                            timestamp=datetime.now(timezone.utc),
                            priority=priority,
                        ),
                    )

                    await event_bus.publish(event)

                except Exception as publish_error:
                    logger.error(f"Failed to publish error event: {publish_error}")

                # Re-raise the original exception
                raise

        return wrapper

    return decorator


async def cleanup_decorators_event_bus():
    """Cleanup the event bus service."""
    event_bus_service = get_service(EventBusService)
    if event_bus_service.is_initialized:
        await event_bus_service.shutdown()
