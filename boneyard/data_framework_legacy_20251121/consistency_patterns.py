"""
Data Consistency Management for Marty Microservices Framework

This module implements data consistency patterns including distributed caching,
consistency levels, and data synchronization strategies.
"""

import asyncio
import builtins
import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConsistencyLevel(Enum):
    """Data consistency levels."""

    STRONG = "strong"
    EVENTUAL = "eventual"
    WEAK = "weak"
    SESSION = "session"
    BOUNDED_STALENESS = "bounded_staleness"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 3600  # 1 hour default
    version: int = 1
    checksum: str = field(default="")

    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum for value."""
        try:
            value_str = json.dumps(self.value, sort_keys=True, default=str)
            return hashlib.sha256(value_str.encode()).hexdigest()
        except (TypeError, ValueError):
            # Fallback for non-serializable values
            return hashlib.sha256(str(self.value).encode()).hexdigest()

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds <= 0:
            return False  # Never expires

        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds

    def is_valid(self) -> bool:
        """Validate cache entry integrity."""
        return self.checksum == self._calculate_checksum()


@dataclass
class ConsistencyConfig:
    """Configuration for data consistency."""

    level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    max_staleness_seconds: int = 300  # 5 minutes
    replication_factor: int = 3
    consistency_timeout_seconds: int = 30
    enable_read_repair: bool = True
    enable_anti_entropy: bool = True


class DistributedCache:
    """Distributed cache with consistency guarantees."""

    def __init__(self, node_id: str, consistency_config: ConsistencyConfig | None = None):
        """Initialize distributed cache."""
        self.node_id = node_id
        self.consistency_config = consistency_config or ConsistencyConfig()

        # Local cache storage
        self.cache: builtins.dict[str, CacheEntry] = {}
        self.cache_lock = threading.RLock()

        # Cluster state
        self.peer_nodes: builtins.list[str] = []
        self.node_health: builtins.dict[str, bool] = {}

        # Background tasks
        self.background_tasks: builtins.list[asyncio.Task] = []
        self.is_running = False

    async def start(self):
        """Start cache background tasks."""
        if self.is_running:
            return

        self.is_running = True

        # Start background tasks
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        anti_entropy_task = asyncio.create_task(self._anti_entropy_loop())

        self.background_tasks.extend([cleanup_task, anti_entropy_task])
        logging.info("Distributed cache started: %s", self.node_id)

    async def stop(self):
        """Stop cache background tasks."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        self.background_tasks.clear()
        logging.info("Distributed cache stopped: %s", self.node_id)

    def add_peer_node(self, node_id: str):
        """Add peer node to cluster."""
        if node_id not in self.peer_nodes:
            self.peer_nodes.append(node_id)
            self.node_health[node_id] = True

    def remove_peer_node(self, node_id: str):
        """Remove peer node from cluster."""
        if node_id in self.peer_nodes:
            self.peer_nodes.remove(node_id)
            if node_id in self.node_health:
                del self.node_health[node_id]

    async def get(self, key: str, consistency_level: ConsistencyLevel | None = None) -> Any:
        """Get value from cache with consistency guarantees."""
        level = consistency_level or self.consistency_config.level

        if level == ConsistencyLevel.STRONG:
            return await self._get_strong_consistency(key)
        elif level == ConsistencyLevel.EVENTUAL:
            return await self._get_eventual_consistency(key)
        elif level == ConsistencyLevel.SESSION:
            return await self._get_session_consistency(key)
        elif level == ConsistencyLevel.BOUNDED_STALENESS:
            return await self._get_bounded_staleness(key)
        else:  # WEAK
            return await self._get_weak_consistency(key)

    async def put(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
        consistency_level: ConsistencyLevel | None = None,
    ) -> bool:
        """Put value in cache with consistency guarantees."""
        level = consistency_level or self.consistency_config.level

        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

        # Store locally first
        with self.cache_lock:
            existing_entry = self.cache.get(key)
            if existing_entry:
                entry.version = existing_entry.version + 1
            self.cache[key] = entry

        # Replicate based on consistency level
        if level == ConsistencyLevel.STRONG:
            return await self._put_strong_consistency(entry)
        elif level in [ConsistencyLevel.EVENTUAL, ConsistencyLevel.WEAK]:
            asyncio.create_task(self._put_eventual_consistency(entry))
            return True
        else:
            return await self._put_session_consistency(entry)

    async def delete(self, key: str, consistency_level: ConsistencyLevel | None = None) -> bool:
        """Delete value from cache."""
        level = consistency_level or self.consistency_config.level

        # Delete locally
        with self.cache_lock:
            if key in self.cache:
                del self.cache[key]

        # Propagate deletion based on consistency level
        if level == ConsistencyLevel.STRONG:
            return await self._delete_strong_consistency(key)
        else:
            asyncio.create_task(self._delete_eventual_consistency(key))
            return True

    async def _get_strong_consistency(self, key: str) -> Any:
        """Get with strong consistency (read from majority)."""
        # Read from local cache
        local_entry = None
        with self.cache_lock:
            local_entry = self.cache.get(key)

        # If we have enough healthy nodes, read from majority
        healthy_nodes = [node for node, health in self.node_health.items() if health]
        required_nodes = (len(healthy_nodes) + 1) // 2  # Majority

        if len(healthy_nodes) >= required_nodes:
            # In a real implementation, this would query peer nodes
            # For now, return local value if available and valid
            if local_entry and not local_entry.is_expired() and local_entry.is_valid():
                return local_entry.value

        return None

    async def _get_eventual_consistency(self, key: str) -> Any:
        """Get with eventual consistency (read from local)."""
        with self.cache_lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired() and entry.is_valid():
                return entry.value
        return None

    async def _get_session_consistency(self, key: str) -> Any:
        """Get with session consistency."""
        # For session consistency, we ensure reads are monotonic
        # In this implementation, it's similar to eventual consistency
        return await self._get_eventual_consistency(key)

    async def _get_bounded_staleness(self, key: str) -> Any:
        """Get with bounded staleness consistency."""
        with self.cache_lock:
            entry = self.cache.get(key)
            if entry and entry.is_valid():
                # Check staleness
                staleness = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
                if staleness <= self.consistency_config.max_staleness_seconds:
                    return entry.value
        return None

    async def _get_weak_consistency(self, key: str) -> Any:
        """Get with weak consistency (no guarantees)."""
        with self.cache_lock:
            entry = self.cache.get(key)
            # Return even if expired, for weak consistency
            if entry and entry.is_valid():
                return entry.value
        return None

    async def _put_strong_consistency(self, entry: CacheEntry) -> bool:
        """Put with strong consistency (write to majority)."""
        # In a real implementation, this would write to majority of nodes
        # For now, just simulate the behavior
        healthy_nodes = [node for node, health in self.node_health.items() if health]
        required_nodes = (len(healthy_nodes) + 1) // 2

        if len(healthy_nodes) >= required_nodes:
            # Simulate successful write to majority
            await asyncio.sleep(0.01)  # Simulate network delay
            return True

        return False

    async def _put_eventual_consistency(self, entry: CacheEntry):
        """Put with eventual consistency (async replication)."""
        # Simulate async replication to peer nodes
        for node_id in self.peer_nodes:
            if self.node_health.get(node_id, False):
                # In a real implementation, this would send to peer
                await asyncio.sleep(0.001)  # Simulate async operation

    async def _put_session_consistency(self, entry: CacheEntry) -> bool:
        """Put with session consistency."""
        # Similar to eventual consistency for this implementation
        await self._put_eventual_consistency(entry)
        return True

    async def _delete_strong_consistency(self, key: str) -> bool:
        """Delete with strong consistency."""
        # Similar to put_strong_consistency but for deletion
        healthy_nodes = [node for node, health in self.node_health.items() if health]
        required_nodes = (len(healthy_nodes) + 1) // 2

        if len(healthy_nodes) >= required_nodes:
            await asyncio.sleep(0.01)
            return True

        return False

    async def _delete_eventual_consistency(self, key: str):
        """Delete with eventual consistency."""
        # Simulate async deletion propagation
        for node_id in self.peer_nodes:
            if self.node_health.get(node_id, False):
                await asyncio.sleep(0.001)

    async def _cleanup_loop(self):
        """Background task to clean up expired entries."""
        while self.is_running:
            try:
                await self._cleanup_expired_entries()
                await asyncio.sleep(60)  # Run every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception("Cache cleanup error: %s", e)
                await asyncio.sleep(60)

    async def _cleanup_expired_entries(self):
        """Remove expired cache entries."""
        expired_keys = []

        with self.cache_lock:
            for key, entry in self.cache.items():
                if entry.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]

        if expired_keys:
            logging.info("Cleaned up %d expired cache entries", len(expired_keys))

    async def _anti_entropy_loop(self):
        """Background anti-entropy process for consistency."""
        if not self.consistency_config.enable_anti_entropy:
            return

        while self.is_running:
            try:
                await self._run_anti_entropy()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception("Anti-entropy error: %s", e)
                await asyncio.sleep(300)

    async def _run_anti_entropy(self):
        """Run anti-entropy process to repair inconsistencies."""
        # In a real implementation, this would:
        # 1. Exchange merkle trees with peer nodes
        # 2. Identify inconsistent keys
        # 3. Repair inconsistencies
        pass

    def get_cache_statistics(self) -> builtins.dict[str, Any]:
        """Get cache statistics."""
        with self.cache_lock:
            total_entries = len(self.cache)
            expired_entries = sum(1 for entry in self.cache.values() if entry.is_expired())

            return {
                "node_id": self.node_id,
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "valid_entries": total_entries - expired_entries,
                "peer_nodes": len(self.peer_nodes),
                "healthy_peers": sum(1 for health in self.node_health.values() if health),
                "consistency_level": self.consistency_config.level.value,
            }


class DataConsistencyManager:
    """Manages data consistency across distributed systems."""

    def __init__(self, manager_id: str):
        """Initialize consistency manager."""
        self.manager_id = manager_id
        self.consistency_policies: builtins.dict[str, ConsistencyConfig] = {}
        self.data_sources: builtins.dict[str, Any] = {}
        self.sync_tasks: builtins.dict[str, asyncio.Task] = {}
        self.is_running = False

    async def start(self):
        """Start consistency manager."""
        if self.is_running:
            return

        self.is_running = True
        logging.info("Data consistency manager started: %s", self.manager_id)

    async def stop(self):
        """Stop consistency manager."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel sync tasks
        for task in self.sync_tasks.values():
            task.cancel()

        if self.sync_tasks:
            await asyncio.gather(*self.sync_tasks.values(), return_exceptions=True)

        self.sync_tasks.clear()
        logging.info("Data consistency manager stopped: %s", self.manager_id)

    def register_data_source(self, source_id: str, source: Any, policy: ConsistencyConfig):
        """Register data source with consistency policy."""
        self.data_sources[source_id] = source
        self.consistency_policies[source_id] = policy

    def unregister_data_source(self, source_id: str):
        """Unregister data source."""
        if source_id in self.data_sources:
            del self.data_sources[source_id]
        if source_id in self.consistency_policies:
            del self.consistency_policies[source_id]
        if source_id in self.sync_tasks:
            self.sync_tasks[source_id].cancel()
            del self.sync_tasks[source_id]

    async def ensure_consistency(self, source_id: str, key: str) -> bool:
        """Ensure data consistency for specific key."""
        if source_id not in self.data_sources:
            return False

        policy = self.consistency_policies.get(source_id)
        if not policy:
            return False

        # Implementation would depend on the specific data source type
        # For now, just simulate consistency check
        await asyncio.sleep(0.01)
        return True

    async def repair_inconsistency(
        self, source_id: str, key: str, authoritative_value: Any
    ) -> bool:
        """Repair data inconsistency."""
        if source_id not in self.data_sources:
            return False

        # In a real implementation, this would:
        # 1. Identify all replicas of the data
        # 2. Update inconsistent replicas with authoritative value
        # 3. Verify consistency across all replicas

        await asyncio.sleep(0.01)  # Simulate repair operation
        return True

    def get_consistency_statistics(self) -> builtins.dict[str, Any]:
        """Get consistency statistics."""
        return {
            "manager_id": self.manager_id,
            "registered_sources": len(self.data_sources),
            "active_sync_tasks": len(self.sync_tasks),
            "consistency_policies": {
                source_id: policy.level.value
                for source_id, policy in self.consistency_policies.items()
            },
        }
