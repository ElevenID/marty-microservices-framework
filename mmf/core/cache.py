"""
MMF Cache Infrastructure.

This module provides the core caching abstractions for the Marty Microservices Framework.
It defines the cache interface protocol, key prefix configuration for namespace isolation,
and cache manager implementations.

Usage:
    # Create a namespaced cache for a plugin
    prefix = KeyPrefixConfig(
        app_prefix="marty:",
        plugin_prefix="auth",
        component_prefix="session",
    )
    cache = RedisCacheManager(redis_client, prefix, metrics)

    # Use the cache
    await cache.set("user123", user_data, ttl=3600)
    data = await cache.get("user123")
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Key Prefix Configuration
# =============================================================================


@dataclass
class KeyPrefixConfig:
    """
    Hierarchical key prefix configuration for multi-tenant/multi-plugin isolation.

    Key structure: {app_prefix}:{plugin_prefix}:{tenant_id}:{component_prefix}:{key}

    Example:
        prefix = KeyPrefixConfig(
            app_prefix="marty",
            plugin_prefix="auth",
            component_prefix="pkce",
        )
        prefix.build_key("state123")  # -> "marty:auth:pkce:state123"
    """

    # Application-level prefix (e.g., "marty")
    app_prefix: str = "marty"

    # Plugin-specific prefix (e.g., "auth", "pkd", "trust-registry")
    plugin_prefix: str = ""

    # Component prefix (e.g., "session", "pkce", "cache", "ratelimit")
    component_prefix: str = ""

    # Tenant isolation (optional, for multi-tenant deployments)
    tenant_id: str | None = None

    @property
    def full_prefix(self) -> str:
        """
        Build complete prefix with trailing colon.

        Returns:
            Full prefix string, e.g., "marty:auth:pkce:"
        """
        parts = [self.app_prefix.rstrip(":")]
        if self.plugin_prefix:
            parts.append(self.plugin_prefix.rstrip(":"))
        if self.tenant_id:
            parts.append(f"tenant-{self.tenant_id}")
        if self.component_prefix:
            parts.append(self.component_prefix.rstrip(":"))
        return ":".join(parts) + ":"

    def build_key(self, *key_parts: str) -> str:
        """
        Build full cache key with prefix.

        Args:
            *key_parts: Variable key segments to join

        Returns:
            Full key with prefix, e.g., "marty:auth:pkce:abc123"
        """
        return f"{self.full_prefix}{':'.join(key_parts)}"

    def strip_prefix(self, full_key: str) -> str:
        """
        Strip the prefix from a full key.

        Args:
            full_key: Full key including prefix

        Returns:
            Key without prefix
        """
        if full_key.startswith(self.full_prefix):
            return full_key[len(self.full_prefix) :]
        return full_key


# =============================================================================
# Cache Interface Protocol
# =============================================================================


@runtime_checkable
class ICacheManager(Protocol):
    """
    Protocol defining the cache manager interface.

    All cache implementations must conform to this protocol.
    Methods are async to support both local and remote cache backends.
    """

    async def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            Cached value or None if not found/expired
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in the cache.

        Args:
            key: Cache key (will be prefixed automatically)
            value: Value to cache (will be serialized)
            ttl: Time-to-live in seconds, None for no expiration

        Returns:
            True if successful
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if key was deleted, False if key didn't exist
        """
        ...

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if key exists
        """
        ...

    async def get_and_delete(self, key: str) -> Any | None:
        """
        Atomically get and delete a key (consume pattern).

        This is useful for single-use tokens like PKCE state.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            Cached value or None if not found
        """
        ...

    async def set_if_not_exists(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value only if the key doesn't exist (SETNX pattern).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if set, False if key already existed
        """
        ...

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter.

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        ...

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration on an existing key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            True if expiration was set
        """
        ...

    async def ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no expiration, -2 if key doesn't exist
        """
        ...


# =============================================================================
# Cache Metrics Interface
# =============================================================================


@runtime_checkable
class ICacheMetrics(Protocol):
    """Protocol for cache metrics collection."""

    def record_hit(self, cache_name: str) -> None:
        """Record a cache hit."""
        ...

    def record_miss(self, cache_name: str) -> None:
        """Record a cache miss."""
        ...

    def record_latency(self, cache_name: str, operation: str, latency_seconds: float) -> None:
        """Record operation latency."""
        ...

    def record_error(self, cache_name: str, operation: str) -> None:
        """Record a cache error."""
        ...


# =============================================================================
# Abstract Cache Manager Base
# =============================================================================


class BaseCacheManager(ABC):
    """
    Abstract base class for cache manager implementations.

    Provides common functionality like key prefixing and metrics collection.
    Subclasses implement the actual cache backend operations.
    """

    def __init__(
        self,
        prefix_config: KeyPrefixConfig | None = None,
        metrics: ICacheMetrics | None = None,
        default_ttl: int = 3600,
    ):
        self._prefix = prefix_config or KeyPrefixConfig()
        self._metrics = metrics
        self._default_ttl = default_ttl
        self._cache_name = self._prefix.full_prefix.rstrip(":")
        self._logger = logging.getLogger(f"cache.{self._cache_name}")

    def _build_key(self, key: str) -> str:
        """Build full key with prefix."""
        return self._prefix.build_key(key)

    def _record_hit(self) -> None:
        """Record cache hit metric."""
        if self._metrics:
            self._metrics.record_hit(self._cache_name)

    def _record_miss(self) -> None:
        """Record cache miss metric."""
        if self._metrics:
            self._metrics.record_miss(self._cache_name)

    def _record_latency(self, operation: str, latency: float) -> None:
        """Record operation latency metric."""
        if self._metrics:
            self._metrics.record_latency(self._cache_name, operation, latency)

    def _record_error(self, operation: str) -> None:
        """Record error metric."""
        if self._metrics:
            self._metrics.record_error(self._cache_name, operation)

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from the cache."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in the cache."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from the cache."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""

    @abstractmethod
    async def get_and_delete(self, key: str) -> Any | None:
        """Atomically get and delete a key."""

    @abstractmethod
    async def set_if_not_exists(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set only if key doesn't exist."""

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Get remaining TTL."""


# =============================================================================
# In-Memory Cache (for testing and development)
# =============================================================================


@dataclass
class _CacheEntry:
    """Internal cache entry with expiration tracking."""

    value: Any
    expires_at: float | None = None

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class InMemoryCacheManager(BaseCacheManager):
    """
    In-memory cache implementation for testing and development.

    NOT suitable for production multi-process deployments.
    """

    def __init__(
        self,
        prefix_config: KeyPrefixConfig | None = None,
        metrics: ICacheMetrics | None = None,
        default_ttl: int = 3600,
    ):
        super().__init__(prefix_config, metrics, default_ttl)
        self._store: dict[str, _CacheEntry] = {}

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items() if v.expires_at is not None and v.expires_at < now
        ]
        for key in expired_keys:
            del self._store[key]

    async def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        start = time.time()
        full_key = self._build_key(key)

        entry = self._store.get(full_key)
        if entry is None or entry.is_expired():
            if entry is not None:
                del self._store[full_key]
            self._record_miss()
            self._record_latency("get", time.time() - start)
            return None

        self._record_hit()
        self._record_latency("get", time.time() - start)
        return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in cache."""
        start = time.time()
        full_key = self._build_key(key)
        ttl = ttl or self._default_ttl

        expires_at = time.time() + ttl if ttl else None
        self._store[full_key] = _CacheEntry(value=value, expires_at=expires_at)

        self._record_latency("set", time.time() - start)
        return True

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        start = time.time()
        full_key = self._build_key(key)

        existed = full_key in self._store
        if existed:
            del self._store[full_key]

        self._record_latency("delete", time.time() - start)
        return existed

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        full_key = self._build_key(key)
        entry = self._store.get(full_key)
        if entry is None:
            return False
        if entry.is_expired():
            del self._store[full_key]
            return False
        return True

    async def get_and_delete(self, key: str) -> Any | None:
        """Atomically get and delete a key."""
        start = time.time()
        full_key = self._build_key(key)

        entry = self._store.pop(full_key, None)
        if entry is None or entry.is_expired():
            self._record_miss()
            self._record_latency("get_and_delete", time.time() - start)
            return None

        self._record_hit()
        self._record_latency("get_and_delete", time.time() - start)
        return entry.value

    async def set_if_not_exists(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set only if key doesn't exist."""
        if await self.exists(key):
            return False

        return await self.set(key, value, ttl)

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        full_key = self._build_key(key)

        entry = self._store.get(full_key)
        if entry is None or entry.is_expired():
            self._store[full_key] = _CacheEntry(value=amount, expires_at=None)
            return amount

        new_value = int(entry.value) + amount
        entry.value = new_value
        return new_value

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""
        full_key = self._build_key(key)

        entry = self._store.get(full_key)
        if entry is None or entry.is_expired():
            return False

        entry.expires_at = time.time() + ttl
        return True

    async def ttl(self, key: str) -> int:
        """Get remaining TTL."""
        full_key = self._build_key(key)

        entry = self._store.get(full_key)
        if entry is None:
            return -2
        if entry.expires_at is None:
            return -1

        remaining = int(entry.expires_at - time.time())
        return max(0, remaining)


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "KeyPrefixConfig",
    "ICacheManager",
    "ICacheMetrics",
    "BaseCacheManager",
    "InMemoryCacheManager",
]
