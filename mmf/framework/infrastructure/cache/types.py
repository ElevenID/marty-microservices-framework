import builtins
import datetime
import io
import json
import logging
import pickle
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """Supported cache backends."""

    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class CachePattern(Enum):
    """Cache access patterns."""

    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types to prevent code execution."""

    SAFE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "slice",
        "range",
    }

    def find_class(self, module, name):
        # Only allow safe built-in types and specific allowed modules
        if module == "builtins" and name in self.SAFE_BUILTINS:
            return getattr(builtins, name)
        # Allow datetime objects which are commonly cached
        if module == "datetime" and name in {"datetime", "date", "time", "timedelta"}:
            return getattr(datetime, name)
        # Block everything else
        raise pickle.UnpicklingError(f"Forbidden class {module}.{name}")


class SerializationFormat(Enum):
    """Serialization formats for cache values."""

    PICKLE = "pickle"
    JSON = "json"
    STRING = "string"
    BYTES = "bytes"


@dataclass
class CacheConfig:
    """Cache configuration."""

    backend: CacheBackend = CacheBackend.MEMORY
    host: str = "localhost"
    port: int = 6379
    url: str | None = None
    database: int = 0
    password: str | None = None
    max_connections: int = 100
    default_ttl: int = 3600  # 1 hour
    serialization: SerializationFormat = SerializationFormat.JSON
    compression_enabled: bool = True
    key_prefix: str = ""
    namespace: str = "default"


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheSerializer:
    """Handles serialization and deserialization of cache values."""

    def __init__(self, format_type: SerializationFormat = SerializationFormat.PICKLE):
        self.format = format_type

    def serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        try:
            if self.format == SerializationFormat.PICKLE:
                return pickle.dumps(value)
            if self.format == SerializationFormat.JSON:
                return json.dumps(value).encode("utf-8")
            if self.format == SerializationFormat.STRING:
                return str(value).encode("utf-8")
            if self.format == SerializationFormat.BYTES:
                return value if isinstance(value, bytes) else str(value).encode("utf-8")
            raise ValueError(f"Unsupported serialization format: {self.format}")
        except Exception as e:
            logger.error("Serialization failed: %s", e)
            raise

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        try:
            if self.format == SerializationFormat.PICKLE:
                # Security: Use restricted unpickler to prevent arbitrary code execution
                warnings.warn(
                    "Pickle deserialization is potentially unsafe. Consider using JSON format for better security.",
                    UserWarning,
                    stacklevel=2,
                )

                return RestrictedUnpickler(io.BytesIO(data)).load()
            if self.format == SerializationFormat.JSON:
                return json.loads(data.decode("utf-8"))
            if self.format == SerializationFormat.STRING:
                return data.decode("utf-8")
            if self.format == SerializationFormat.BYTES:
                return data
            raise ValueError(f"Unsupported serialization format: {self.format}")
        except Exception as e:
            logger.error("Deserialization failed: %s", e)
            raise


class CacheBackendInterface(ABC):
    """Abstract interface for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Get value from cache."""

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Set value in cache."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""

    @abstractmethod
    async def zadd(self, key: str, mapping: dict[bytes, float]) -> int:
        """Add members to sorted set."""

    @abstractmethod
    async def zrevrangebyscore(
        self,
        key: str,
        max_score: float,
        min_score: float,
        start: int | None = None,
        num: int | None = None,
    ) -> list[bytes]:
        """Get members from sorted set by score (descending)."""

    @abstractmethod
    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with score within range."""

    @abstractmethod
    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove members from sorted set by score range."""

    @abstractmethod
    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""

    @abstractmethod
    async def zremrangebyrank(self, key: str, min_rank: int, max_rank: int) -> int:
        """Remove members from sorted set by rank range."""

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""

    @abstractmethod
    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
