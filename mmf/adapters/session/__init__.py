"""
Session Adapters

This package contains adapter implementations for session management.
"""

from .redis_adapter import RedisSessionAdapter

__all__ = ["RedisSessionAdapter"]
