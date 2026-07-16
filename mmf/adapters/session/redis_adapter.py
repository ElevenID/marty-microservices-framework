"""
Redis Session Adapter

Production-grade Redis-backed session management implementing the ISessionManager port.
Supports session storage, token refresh, and sliding window expiration.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from mmf.core.security.domain.models.session import (
    SessionCleanupEvent,
    SessionData,
    SessionEventType,
    SessionMetrics,
    SessionState,
)
from mmf.core.security.ports.session import ISessionManager

logger = logging.getLogger(__name__)


class RedisSessionAdapter(ISessionManager):
    """
    Redis-backed session manager implementation.

    Stores session data as JSON in Redis with automatic TTL-based expiration.
    Supports storing refresh tokens alongside session data for OIDC flows.
    """

    # Redis key prefixes
    SESSION_PREFIX = "session:"
    USER_SESSIONS_PREFIX = "user_sessions:"
    REFRESH_TOKEN_PREFIX = "refresh_token:"  # nosec B105

    def __init__(
        self,
        redis_client: Any,  # redis.asyncio.Redis
        default_timeout_minutes: int = 30,
        max_sessions_per_user: int = 5,
        key_prefix: str = "marty:",
    ) -> None:
        """
        Initialize Redis session adapter.

        Args:
            redis_client: Async Redis client instance
            default_timeout_minutes: Default session timeout in minutes
            max_sessions_per_user: Maximum concurrent sessions per user
            key_prefix: Prefix for all Redis keys
        """
        self._redis = redis_client
        self._default_timeout = default_timeout_minutes
        self._max_sessions_per_user = max_sessions_per_user
        self._key_prefix = key_prefix
        self._metrics = SessionMetrics()

    def _session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self._key_prefix}{self.SESSION_PREFIX}{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's session set."""
        return f"{self._key_prefix}{self.USER_SESSIONS_PREFIX}{user_id}"

    def _refresh_token_key(self, session_id: str) -> str:
        """Get Redis key for refresh token."""
        return f"{self._key_prefix}{self.REFRESH_TOKEN_PREFIX}{session_id}"

    def _serialize_session(self, session: SessionData) -> str:
        """Serialize session data to JSON."""
        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "state": session.state.value,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "attributes": session.attributes,
            "security_context": session.security_context,
        }
        return json.dumps(data)

    def _deserialize_session(self, data: str) -> SessionData:
        """Deserialize session data from JSON."""
        parsed = json.loads(data)
        return SessionData(
            session_id=parsed["session_id"],
            user_id=parsed["user_id"],
            created_at=datetime.fromisoformat(parsed["created_at"]),
            last_accessed=datetime.fromisoformat(parsed["last_accessed"]),
            expires_at=datetime.fromisoformat(parsed["expires_at"]),
            state=SessionState(parsed["state"]),
            ip_address=parsed.get("ip_address"),
            user_agent=parsed.get("user_agent"),
            attributes=parsed.get("attributes", {}),
            security_context=parsed.get("security_context", {}),
        )

    async def create_session(
        self,
        user_id: str,
        timeout_minutes: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **attributes: Any,
    ) -> SessionData:
        """Create a new session in Redis."""
        timeout = timeout_minutes or self._default_timeout
        session = SessionData.create(
            user_id=user_id,
            timeout_minutes=timeout,
            ip_address=ip_address,
            user_agent=user_agent,
            **attributes,
        )

        # Enforce max sessions per user
        await self._enforce_session_limit(user_id)

        # Calculate TTL in seconds
        ttl_seconds = int((session.expires_at - datetime.utcnow()).total_seconds())

        # Store session in Redis
        session_key = self._session_key(session.session_id)
        await self._redis.setex(session_key, ttl_seconds, self._serialize_session(session))

        # Add to user's session set
        user_sessions_key = self._user_sessions_key(user_id)
        await self._redis.sadd(user_sessions_key, session.session_id)
        await self._redis.expire(user_sessions_key, ttl_seconds * 2)  # Keep set longer

        self._metrics.record_session_created()
        logger.info(f"Created session {session.session_id} for user {user_id}")

        return session

    async def _enforce_session_limit(self, user_id: str) -> None:
        """Enforce maximum sessions per user by removing oldest sessions."""
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_sessions_key)

        if len(session_ids) >= self._max_sessions_per_user:
            # Get all sessions with their creation times
            sessions_with_times: list[tuple[str, datetime]] = []
            for sid in session_ids:
                if isinstance(sid, bytes):
                    sid = sid.decode("utf-8")
                session = await self.get_session(sid)
                if session:
                    sessions_with_times.append((sid, session.created_at))
                else:
                    # Clean up stale reference
                    await self._redis.srem(user_sessions_key, sid)

            # Sort by creation time and remove oldest
            sessions_with_times.sort(key=lambda x: x[1])
            sessions_to_remove = len(sessions_with_times) - self._max_sessions_per_user + 1

            for i in range(sessions_to_remove):
                sid = sessions_with_times[i][0]
                await self.terminate_session(sid, SessionEventType.ADMIN_TERMINATION)
                logger.info(f"Removed oldest session {sid} to enforce limit for user {user_id}")

    async def get_session(self, session_id: str) -> SessionData | None:
        """Get session from Redis."""
        session_key = self._session_key(session_id)
        data = await self._redis.get(session_key)

        if not data:
            return None

        if isinstance(data, bytes):
            data = data.decode("utf-8")

        try:
            session = self._deserialize_session(data)

            # Check if expired
            if session.is_expired:
                await self.terminate_session(session_id, SessionEventType.TIMEOUT)
                return None

            # Update last accessed (sliding window)
            session.touch()
            await self.update_session(session)

            return session

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error deserializing session {session_id}: {e}")
            return None

    async def update_session(self, session: SessionData) -> bool:
        """Update session in Redis."""
        session_key = self._session_key(session.session_id)

        # Check if session exists
        if not await self._redis.exists(session_key):
            return False

        # Calculate remaining TTL
        ttl_seconds = int((session.expires_at - datetime.utcnow()).total_seconds())
        if ttl_seconds <= 0:
            return False

        # Update session
        await self._redis.setex(session_key, ttl_seconds, self._serialize_session(session))
        return True

    async def extend_session(self, session_id: str, minutes: int) -> bool:
        """Extend session expiration."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session.extend(minutes)
        return await self.update_session(session)

    async def terminate_session(
        self,
        session_id: str,
        reason: SessionEventType = SessionEventType.LOGOUT,
    ) -> bool:
        """Terminate a session."""
        session_key = self._session_key(session_id)
        session_data = await self._redis.get(session_key)

        if not session_data:
            return False

        if isinstance(session_data, bytes):
            session_data = session_data.decode("utf-8")

        try:
            session = self._deserialize_session(session_data)
            user_id = session.user_id

            # Remove session
            await self._redis.delete(session_key)

            # Remove refresh token if exists
            await self._redis.delete(self._refresh_token_key(session_id))

            # Remove from user's session set
            user_sessions_key = self._user_sessions_key(user_id)
            await self._redis.srem(user_sessions_key, session_id)

            self._metrics.record_session_terminated(reason)
            logger.info(f"Terminated session {session_id} for reason: {reason.value}")

            return True

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error terminating session {session_id}: {e}")
            return False

    async def terminate_user_sessions(
        self,
        user_id: str,
        except_session_id: str | None = None,
        reason: SessionEventType = SessionEventType.ADMIN_TERMINATION,
    ) -> int:
        """Terminate all sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_sessions_key)

        terminated = 0
        for sid in session_ids:
            if isinstance(sid, bytes):
                sid = sid.decode("utf-8")

            if except_session_id and sid == except_session_id:
                continue

            if await self.terminate_session(sid, reason):
                terminated += 1

        return terminated

    async def get_user_sessions(self, user_id: str) -> list[SessionData]:
        """Get all active sessions for a user."""
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_sessions_key)

        sessions = []
        for sid in session_ids:
            if isinstance(sid, bytes):
                sid = sid.decode("utf-8")

            session = await self.get_session(sid)
            if session:
                sessions.append(session)

        return sessions

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (handled automatically by Redis TTL)."""
        # Redis TTL handles this automatically, but we can scan for orphaned user session sets
        self._metrics.record_cleanup_operation()
        return 0

    async def process_cleanup_event(self, event: SessionCleanupEvent) -> bool:
        """Process a session cleanup event."""
        return await self.terminate_session(event.session_id, event.event_type)

    async def get_metrics(self) -> SessionMetrics:
        """Get session management metrics."""
        return self._metrics

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    # ==========================================================================
    # Extended methods for OIDC token management
    # ==========================================================================

    async def store_refresh_token(
        self,
        session_id: str,
        refresh_token: str,
        expires_in_seconds: int | None = None,
    ) -> bool:
        """
        Store refresh token associated with a session.

        Args:
            session_id: Session ID to associate with
            refresh_token: The refresh token to store
            expires_in_seconds: Token expiration time in seconds

        Returns:
            True if stored successfully
        """
        key = self._refresh_token_key(session_id)
        ttl = expires_in_seconds or (7 * 24 * 60 * 60)  # Default 7 days

        try:
            await self._redis.setex(key, ttl, refresh_token)
            return True
        except Exception as e:
            logger.error(f"Error storing refresh token for session {session_id}: {e}")
            return False

    async def get_refresh_token(self, session_id: str) -> str | None:
        """
        Get refresh token for a session.

        Args:
            session_id: Session ID

        Returns:
            Refresh token or None if not found
        """
        key = self._refresh_token_key(session_id)
        token = await self._redis.get(key)

        if token and isinstance(token, bytes):
            return token.decode("utf-8")
        return token

    async def store_id_token(self, session_id: str, id_token: str) -> bool:
        """
        Store ID token for full SSO logout.

        Args:
            session_id: Session ID
            id_token: The ID token from OIDC provider

        Returns:
            True if stored successfully
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.attributes["id_token"] = id_token
        return await self.update_session(session)

    async def get_id_token(self, session_id: str) -> str | None:
        """
        Get ID token for a session (used for SSO logout).

        Args:
            session_id: Session ID

        Returns:
            ID token or None if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        return session.attributes.get("id_token")

    async def should_refresh_token(
        self,
        session_id: str,
        threshold_minutes: int = 5,
    ) -> bool:
        """
        Check if access token should be refreshed (sliding window).

        Args:
            session_id: Session ID
            threshold_minutes: Refresh if less than this many minutes until expiry

        Returns:
            True if token should be refreshed
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        access_token_expiry = session.attributes.get("access_token_expires_at")
        if not access_token_expiry:
            return False

        if isinstance(access_token_expiry, str):
            access_token_expiry = datetime.fromisoformat(access_token_expiry)

        threshold = datetime.now(timezone.utc) + timedelta(minutes=threshold_minutes)
        return access_token_expiry <= threshold

    async def update_access_token(
        self,
        session_id: str,
        access_token: str,
        expires_in_seconds: int,
    ) -> bool:
        """
        Update access token after refresh.

        Args:
            session_id: Session ID
            access_token: New access token
            expires_in_seconds: Token expiration time in seconds

        Returns:
            True if updated successfully
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        session.attributes["access_token"] = access_token
        session.attributes["access_token_expires_at"] = expiry.isoformat()

        return await self.update_session(session)
