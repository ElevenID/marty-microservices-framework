"""
Decorators for MMF plugin services.

This module provides decorators that plugin services can use to integrate
with MMF infrastructure components like authentication, metrics, tracing,
and event handling.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def plugin_service(
    name: str | None = None,
    version: str = "1.0.0",
    description: str = "",
    dependencies: list[str] | None = None,
):
    """Decorator to mark a class as a plugin service.

    Args:
        name: Service name (defaults to class name)
        version: Service version
        description: Service description
        dependencies: List of service dependencies
    """
    def decorator(cls):
        # Set service metadata on the class
        cls._service_name = name or cls.__name__
        cls._service_version = version
        cls._service_description = description
        cls._service_dependencies = dependencies or []
        
        # Mark as plugin service
        cls._is_plugin_service = True
        
        return cls
    return decorator


def requires_auth(
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    scopes: list[str] | None = None,
):
    """Decorator to require authentication for a plugin service method.

    Args:
        roles: Required user roles
        permissions: Required permissions
        scopes: Required OAuth scopes
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement actual auth checking when security system is integrated
            logger.debug(f"Auth check for {func.__name__}: roles={roles}, permissions={permissions}, scopes={scopes}")
            return await func(*args, **kwargs)
        
        # Store auth requirements on function
        wrapper._auth_roles = roles or []
        wrapper._auth_permissions = permissions or []
        wrapper._auth_scopes = scopes or []
        wrapper._requires_auth = True
        
        return wrapper
    return decorator


def track_metrics(
    metric_name: str | None = None,
    labels: dict[str, str] | None = None,
    track_duration: bool = True,
    track_calls: bool = True,
):
    """Decorator to track metrics for a plugin service method.

    Args:
        metric_name: Custom metric name (defaults to function name)
        labels: Static labels to add to metrics
        track_duration: Whether to track execution duration
        track_calls: Whether to track call count
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement actual metrics tracking when monitoring is integrated
            name = metric_name or func.__name__ 
            logger.debug(f"Metrics tracking for {name}: duration={track_duration}, calls={track_calls}, labels={labels}")
            return await func(*args, **kwargs)
        
        # Store metrics metadata
        wrapper._metric_name = metric_name
        wrapper._metric_labels = labels or {}
        wrapper._track_duration = track_duration
        wrapper._track_calls = track_calls
        wrapper._tracks_metrics = True
        
        return wrapper
    return decorator


def trace_operation(
    operation_name: str | None = None,
    tags: dict[str, str] | None = None,
    trace_args: bool = False,
    trace_result: bool = False,
):
    """Decorator to add tracing to a plugin service method.

    Args:
        operation_name: Custom operation name for tracing
        tags: Static tags to add to trace spans
        trace_args: Whether to trace function arguments
        trace_result: Whether to trace function result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement actual tracing when observability is integrated
            name = operation_name or func.__name__
            logger.debug(f"Tracing operation {name}: args={trace_args}, result={trace_result}, tags={tags}")
            return await func(*args, **kwargs)
        
        # Store tracing metadata
        wrapper._operation_name = operation_name
        wrapper._trace_tags = tags or {}
        wrapper._trace_args = trace_args
        wrapper._trace_result = trace_result
        wrapper._has_tracing = True
        
        return wrapper
    return decorator


def event_handler(
    event_types: list[str] | str,
    priority: int = 0,
    async_handler: bool = True,
):
    """Decorator to mark a method as an event handler.

    Args:
        event_types: Event type(s) this handler processes
        priority: Handler priority (higher numbers run first)
        async_handler: Whether this is an async event handler
    """
    if isinstance(event_types, str):
        event_types = [event_types]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger.debug(f"Event handler {func.__name__} processing events: {event_types}")
            return await func(*args, **kwargs)
        
        # Store event handler metadata
        wrapper._event_types = event_types
        wrapper._handler_priority = priority
        wrapper._is_async_handler = async_handler
        wrapper._is_event_handler = True
        
        return wrapper
    return decorator


def cache_result(
    ttl: int = 300,  # 5 minutes default
    key_prefix: str | None = None,
    vary_on_args: bool = True,
    vary_on_kwargs: list[str] | None = None,
):
    """Decorator to cache the result of a plugin service method.

    Args:
        ttl: Time to live for cached results in seconds
        key_prefix: Prefix for cache keys
        vary_on_args: Whether to include args in cache key
        vary_on_kwargs: Specific kwargs to include in cache key
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement actual caching when cache system is integrated
            logger.debug(f"Cache check for {func.__name__}: ttl={ttl}, prefix={key_prefix}")
            return await func(*args, **kwargs)
        
        # Store caching metadata
        wrapper._cache_ttl = ttl
        wrapper._cache_key_prefix = key_prefix
        wrapper._cache_vary_on_args = vary_on_args
        wrapper._cache_vary_on_kwargs = vary_on_kwargs or []
        wrapper._has_caching = True
        
        return wrapper
    return decorator


def rate_limit(
    requests_per_minute: int = 60,
    per_user: bool = True,
    burst_size: int | None = None,
):
    """Decorator to add rate limiting to a plugin service method.

    Args:
        requests_per_minute: Maximum requests per minute
        per_user: Whether to apply limit per user or globally
        burst_size: Maximum burst size (defaults to requests_per_minute)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implement actual rate limiting when implemented
            logger.debug(f"Rate limit check for {func.__name__}: {requests_per_minute}/min, per_user={per_user}")
            return await func(*args, **kwargs)
        
        # Store rate limiting metadata
        wrapper._rate_limit_rpm = requests_per_minute
        wrapper._rate_limit_per_user = per_user
        wrapper._rate_limit_burst = burst_size or requests_per_minute
        wrapper._has_rate_limiting = True
        
        return wrapper
    return decorator