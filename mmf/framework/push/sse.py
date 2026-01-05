"""
SSE Push Adapter.

Server-Sent Events adapter for real-time push notifications.
Provides the same interface as other push adapters but uses
persistent HTTP connections for delivery.

Features:
- Connection management
- Heartbeat support (configurable interval)
- User/organization targeting
- Connection limits per user
- Stale connection cleanup
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mmf.core.push import IPushAdapter, PushChannel, PushMessage, PushResult, PushStatus

logger = logging.getLogger(__name__)


@dataclass
class SSEConfig:
    """
    SSE adapter configuration.

    Heartbeat interval can be configured to match development
    needs (faster for local testing) vs production (longer for
    efficiency).
    """

    # Heartbeat interval in seconds (comment format for heartbeats)
    heartbeat_interval: int = 30

    # Maximum connections per user (oldest removed when exceeded)
    max_connections_per_user: int = 5

    # Stale connection timeout (seconds without activity)
    stale_timeout: int = 300  # 5 minutes

    # Event ID format (useful for resumption)
    event_id_format: str = "{message_id}"


@dataclass
class SSEConnection:
    """A single SSE client connection."""

    id: str
    user_id: str | None = None
    organization_id: str | None = None
    device_id: str | None = None
    queue: asyncio.Queue[str | None] = field(default_factory=asyncio.Queue)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_event_id: str | None = None

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


class SSEAdapter:
    """
    Server-Sent Events push adapter.

    Implements IPushAdapter for SSE delivery. Unlike FCM which pushes
    to external servers, SSE maintains connections to clients and
    pushes events through those connections.

    Usage:
        config = SSEConfig(heartbeat_interval=15)  # 15s heartbeat
        adapter = SSEAdapter(config)
        await adapter.start()

        # Add a connection (from HTTP endpoint)
        conn = adapter.add_connection(
            connection_id="conn-123",
            user_id="user-456",
        )

        # Stream events to client
        async for event in adapter.event_stream(conn):
            yield event

        # Send a message
        message = PushMessage(
            target=PushTarget(connection_ids=["conn-123"]),
            data={"type": "notification", "content": "Hello"},
        )
        result = await adapter.send(message)
    """

    def __init__(self, config: SSEConfig | None = None):
        """
        Initialize the SSE adapter.

        Args:
            config: SSE configuration (uses defaults if not provided)
        """
        self.config = config or SSEConfig()
        self._connections: dict[str, SSEConnection] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    @property
    def channel(self) -> PushChannel:
        """The channel this adapter handles."""
        return PushChannel.SSE

    async def start(self) -> None:
        """Start the SSE adapter (heartbeat task)."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"SSE adapter started (heartbeat={self.config.heartbeat_interval}s)")

    async def stop(self) -> None:
        """Stop the SSE adapter."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for conn in list(self._connections.values()):
            await conn.queue.put(None)  # Signal close

        self._connections.clear()
        logger.info("SSE adapter stopped")

    def add_connection(
        self,
        connection_id: str,
        user_id: str | None = None,
        organization_id: str | None = None,
        device_id: str | None = None,
    ) -> SSEConnection:
        """
        Add a new SSE connection.

        Args:
            connection_id: Unique connection identifier
            user_id: Optional user identifier
            organization_id: Optional organization identifier
            device_id: Optional device identifier

        Returns:
            SSEConnection object
        """
        # Check connection limit per user
        if user_id:
            user_connections = [c for c in self._connections.values() if c.user_id == user_id]
            while len(user_connections) >= self.config.max_connections_per_user:
                # Remove oldest connection
                oldest = min(user_connections, key=lambda c: c.connected_at)
                asyncio.create_task(self._close_connection(oldest.id))
                user_connections.remove(oldest)

        connection = SSEConnection(
            id=connection_id,
            user_id=user_id,
            organization_id=organization_id,
            device_id=device_id,
        )
        self._connections[connection_id] = connection

        logger.debug(f"Added SSE connection {connection_id}")
        return connection

    def remove_connection(self, connection_id: str) -> None:
        """Remove an SSE connection."""
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.debug(f"Removed SSE connection {connection_id}")

    async def _close_connection(self, connection_id: str) -> None:
        """Close and remove a connection."""
        if connection_id in self._connections:
            conn = self._connections[connection_id]
            await conn.queue.put(None)
            self.remove_connection(connection_id)

    async def send(self, message: PushMessage) -> PushResult:
        """
        Send a push notification via SSE.

        Broadcasts to matching connections based on target.

        Args:
            message: The push message

        Returns:
            PushResult with success status
        """
        matching_connections = self._get_matching_connections(message)

        if not matching_connections:
            return PushResult(
                message_id=message.id,
                channel=PushChannel.SSE,
                status=PushStatus.DELIVERED,
                success=True,
                metadata={"connections": 0, "skipped": "No matching connections"},
            )

        # Build SSE event
        event = self._build_event(message)

        # Send to all matching connections
        send_count = 0
        for conn in matching_connections:
            try:
                await asyncio.wait_for(
                    conn.queue.put(event),
                    timeout=1.0,
                )
                conn.touch()
                send_count += 1
            except asyncio.TimeoutError:
                logger.warning(f"Timeout sending to connection {conn.id}")
            except Exception as e:
                logger.error(f"Error sending to connection {conn.id}: {e}")

        return PushResult(
            message_id=message.id,
            channel=PushChannel.SSE,
            status=PushStatus.DELIVERED if send_count > 0 else PushStatus.FAILED,
            success=send_count > 0,
            delivered_at=datetime.now(timezone.utc) if send_count > 0 else None,
            metadata={
                "connections_sent": send_count,
                "connections_matched": len(matching_connections),
            },
        )

    async def send_batch(self, messages: list[PushMessage]) -> list[PushResult]:
        """Send multiple messages."""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    def _get_matching_connections(
        self,
        message: PushMessage,
    ) -> list[SSEConnection]:
        """Get connections that should receive this message."""
        matching = []
        target = message.target

        for conn in self._connections.values():
            # Check specific connection IDs
            if target.connection_ids:
                if conn.id in target.connection_ids:
                    matching.append(conn)
                continue

            # Check organization match
            if target.organization_id:
                if conn.organization_id == target.organization_id:
                    matching.append(conn)
                    continue

            # Check user match
            if target.user_id:
                if conn.user_id == target.user_id:
                    matching.append(conn)
                    continue

            # If no specific target, send to all
            if not target.has_targets():
                matching.append(conn)

        return matching

    def _build_event(self, message: PushMessage) -> str:
        """Build SSE event string."""
        # Build data payload
        data = {
            "id": message.id,
            "title": message.title,
            "body": message.body,
            "data": message.data,
            "priority": message.priority.value,
            "timestamp": message.created_at.isoformat(),
        }

        if message.correlation_id:
            data["correlation_id"] = message.correlation_id

        data_json = json.dumps(data)

        # Build event ID
        event_id = self.config.event_id_format.format(message_id=message.id)

        # Determine event type
        event_type = message.data.get("event_type", "message")

        lines = [
            f"id: {event_id}",
            f"event: {event_type}",
            f"data: {data_json}",
            "",  # Empty line to end event
        ]

        return "\n".join(lines)

    async def event_stream(
        self,
        connection: SSEConnection,
    ) -> AsyncIterator[str]:
        """
        Generate SSE event stream for a connection.

        This is an async generator that yields SSE events.
        Use this in a FastAPI streaming response.

        Args:
            connection: The SSE connection

        Yields:
            SSE formatted event strings
        """
        try:
            while self._running:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(
                        connection.queue.get(),
                        timeout=self.config.heartbeat_interval,
                    )

                    if event is None:
                        break  # Connection closed

                    connection.touch()
                    yield event

                except asyncio.TimeoutError:
                    # Send heartbeat comment
                    yield ": heartbeat\n\n"

        finally:
            self.remove_connection(connection.id)

    async def _heartbeat_loop(self) -> None:
        """Cleanup stale connections periodically."""
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval)

            now = datetime.now(timezone.utc)
            stale = []

            for conn_id, conn in self._connections.items():
                # Check for stale connections
                age = (now - conn.last_activity).total_seconds()
                if age > self.config.stale_timeout:
                    stale.append(conn_id)

            for conn_id in stale:
                logger.info(f"Removing stale SSE connection {conn_id}")
                await self._close_connection(conn_id)

    @property
    def connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        by_org: dict[str, int] = {}
        by_user: dict[str, int] = {}

        for conn in self._connections.values():
            if conn.organization_id:
                by_org[conn.organization_id] = by_org.get(conn.organization_id, 0) + 1
            if conn.user_id:
                by_user[conn.user_id] = by_user.get(conn.user_id, 0) + 1

        return {
            "total_connections": len(self._connections),
            "by_organization": by_org,
            "by_user": by_user,
            "heartbeat_interval": self.config.heartbeat_interval,
        }

    def get_connection(self, connection_id: str) -> SSEConnection | None:
        """Get a specific connection by ID."""
        return self._connections.get(connection_id)
