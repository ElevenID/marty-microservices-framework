"""
Cache Port Interface.

This module defines the port (interface) for caching operations that the application layer
depends on. Infrastructure adapters must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class CachePort(ABC, Generic[T]):
    """
    Port for caching operations.

    This interface defines the contract for caching services used by the application layer.
    """

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: T, ttl: int | None = None) -> bool:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)

        Returns:
            True if successfully cached, False otherwise
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if successfully deleted, False otherwise
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        ...
