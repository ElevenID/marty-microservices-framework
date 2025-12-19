"""Audit event caching wrapper using framework CacheManager."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from mmf.core.domain import AuditLevel, SecurityEventType
from mmf.framework.infrastructure.cache import CacheManager

from ...domain.models import SecurityAuditEvent


class AuditEventCache:
    """Cache wrapper for audit events using Redis ZSET sliding window."""

    def __init__(self, cache_manager: CacheManager, ttl_seconds: int = 3600):
        self.cache = cache_manager
        self.ttl = ttl_seconds
        self.sliding_window_size = 10000  # Max events in sliding window

    async def cache_event(self, event: SecurityAuditEvent) -> None:
        """Cache an audit event in Redis ZSET for sliding window access."""
        # Use timestamp as score for sliding window
        score = event.timestamp.timestamp()

        # Create cache key based on different access patterns
        base_key = "audit_events"

        # Cache in multiple keys for different query patterns
        keys_to_update = [
            f"{base_key}:all",
            f"{base_key}:principal:{event.principal_id}",
            f"{base_key}:resource:{event.resource}",
            f"{base_key}:type:{event.event_type.value}",
            f"{base_key}:level:{event.level.value}",
        ]

        # If correlation_id exists, cache by that too
        if event.correlation_id:
            keys_to_update.append(f"{base_key}:correlation:{event.correlation_id}")

        # Serialize event for storage
        event_data = self._serialize_event(event)

        for key in keys_to_update:
            # Add to sorted set with timestamp as score
            await self.cache.zadd(key, {event_data: score})

            # Maintain sliding window size
            await self._maintain_sliding_window(key)

            # Set TTL on the key
            await self.cache.expire(key, self.ttl)

    async def get_recent_events(
        self,
        key_pattern: str = "all",
        limit: int = 100,
        hours_back: int = 24,
    ) -> list[SecurityAuditEvent]:
        """Get recent events from cache."""

        # Calculate time range for sliding window
        end_time = datetime.utcnow().timestamp()
        start_time = (datetime.utcnow() - timedelta(hours=hours_back)).timestamp()

        cache_key = f"audit_events:{key_pattern}"

        # Get events from sorted set within time range
        event_data_list = await self.cache.zrevrangebyscore(
            cache_key,
            end_time,
            start_time,
            start=0,
            num=limit,
        )

        # Deserialize events
        events = []
        for event_data in event_data_list:
            try:
                event = self._deserialize_event(event_data)
                if event:
                    events.append(event)
            except Exception:
                # Skip corrupted cache entries
                continue

        return events

    async def get_events_by_principal(
        self,
        principal_id: str,
        limit: int = 100,
        hours_back: int = 24,
    ) -> list[SecurityAuditEvent]:
        """Get cached events for a specific principal."""
        return await self.get_recent_events(
            key_pattern=f"principal:{principal_id}",
            limit=limit,
            hours_back=hours_back,
        )

    async def get_events_by_resource(
        self,
        resource: str,
        limit: int = 100,
        hours_back: int = 24,
    ) -> list[SecurityAuditEvent]:
        """Get cached events for a specific resource."""
        return await self.get_recent_events(
            key_pattern=f"resource:{resource}",
            limit=limit,
            hours_back=hours_back,
        )

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
        hours_back: int = 24,
    ) -> list[SecurityAuditEvent]:
        """Get cached events by event type."""
        return await self.get_recent_events(
            key_pattern=f"type:{event_type}",
            limit=limit,
            hours_back=hours_back,
        )

    async def get_events_by_correlation(
        self,
        correlation_id: str,
    ) -> list[SecurityAuditEvent]:
        """Get cached events by correlation ID."""
        return await self.get_recent_events(
            key_pattern=f"correlation:{correlation_id}",
            limit=1000,  # Correlation events should be limited naturally
            hours_back=168,  # 7 days for correlation tracking
        )

    async def get_critical_events(
        self,
        limit: int = 50,
        hours_back: int = 24,
    ) -> list[SecurityAuditEvent]:
        """Get cached critical events."""
        return await self.get_recent_events(
            key_pattern="level:CRITICAL",
            limit=limit,
            hours_back=hours_back,
        )

    async def get_event_counts(
        self,
        hours_back: int = 24,
    ) -> dict[str, int]:
        """Get event counts by different categories from cache."""
        end_time = datetime.utcnow().timestamp()
        start_time = (datetime.utcnow() - timedelta(hours=hours_back)).timestamp()

        counts = {}

        # Get all keys for types
        type_keys = await self.cache.keys("audit_events:type:*")
        for key in type_keys:
            type_name = key.split(":")[-1]
            count = await self.cache.zcount(key, start_time, end_time)
            counts[f"type:{type_name}"] = count

        # Get all keys for levels
        level_keys = await self.cache.keys("audit_events:level:*")
        for key in level_keys:
            level_name = key.split(":")[-1]
            count = await self.cache.zcount(key, start_time, end_time)
            counts[f"level:{level_name}"] = count

        return counts

    async def clear_old_events(self, hours_to_keep: int = 168) -> int:
        """Clear events older than specified hours from cache."""
        cutoff_time = (datetime.utcnow() - timedelta(hours=hours_to_keep)).timestamp()

        all_keys = await self.cache.keys("audit_events:*")
        total_removed = 0

        for key in all_keys:
            removed = await self.cache.zremrangebyscore(key, 0, cutoff_time)
            total_removed += removed

        return total_removed

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = await self.cache.get_stats()

        # Add specific audit stats
        all_keys = await self.cache.keys("audit_events:*")
        total_events = 0
        for key in all_keys:
            total_events += await self.cache.zcard(key)

        return {
            "hits": stats.hits,
            "misses": stats.misses,
            "total_keys": len(all_keys),
            "total_events_cached": total_events,
        }

    async def _maintain_sliding_window(self, key: str) -> None:
        """Maintain sliding window size by removing oldest entries."""
        count = await self.cache.zcard(key)
        if count > self.sliding_window_size:
            # Remove oldest entries (lowest scores)
            # Rank 0 is lowest score.
            # We want to keep top N (highest scores).
            # So remove from 0 to (count - N - 1)
            remove_count = count - self.sliding_window_size
            await self.cache.zremrangebyrank(key, 0, remove_count - 1)

    def _serialize_event(self, event: SecurityAuditEvent) -> str:
        """Serialize audit event for cache storage."""
        event_dict = {
            "id": event.id,
            "event_type": event.event_type.value,
            "principal_id": event.principal_id,
            "resource": event.resource,
            "action": event.action,
            "result": event.result,
            "timestamp": event.timestamp.isoformat(),
            "level": event.level.value,
            "correlation_id": event.correlation_id,
            "details": event.details,
        }

        return json.dumps(event_dict, default=str)

    def _deserialize_event(self, event_data: str) -> SecurityAuditEvent | None:
        """Deserialize audit event from cache storage."""
        try:
            event_dict = json.loads(event_data)

            # Import enums

            # Reconstruct the event
            event = SecurityAuditEvent(
                event_type=SecurityEventType(event_dict["event_type"]),
                principal_id=event_dict["principal_id"],
                resource=event_dict["resource"],
                action=event_dict["action"],
                result=event_dict["result"],
                level=AuditLevel(event_dict["level"]),
                correlation_id=event_dict.get("correlation_id"),
                details=event_dict.get("details", {}),
            )

            # Set the ID and timestamp manually
            event.id = event_dict["id"]
            event.timestamp = datetime.fromisoformat(event_dict["timestamp"])

            return event

        except Exception:
            # Log error but don't fail
            return None

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern."""
        keys = await self.cache.keys(pattern)
        count = 0
        for key in keys:
            if await self.cache.delete(key):
                count += 1
        return count

    async def refresh_event_cache(self, events: list[SecurityAuditEvent]) -> None:
        """Refresh cache with a batch of events."""
        for event in events:
            await self.cache_event(event)
