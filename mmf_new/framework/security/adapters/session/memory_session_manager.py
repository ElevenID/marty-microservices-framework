"""
Memory Session Manager Adapter

Implementation of ISessionManager using in-memory storage.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from mmf_new.core.security.domain.config import SessionConfig
from mmf_new.core.security.domain.models.session import (
    SessionCleanupEvent,
    SessionData,
    SessionEventType,
    SessionMetrics,
    SessionState,
)
from mmf_new.core.security.ports.session import ISessionManager

logger = logging.getLogger(__name__)


class MemorySessionManager(ISessionManager):
    """
    In-memory session manager implementation.

    Stores session data in a dictionary.
    Useful for testing and development.
    """

    def __init__(self, config: SessionConfig):
        """
        Initialize Memory session manager.

        Args:
            config: Session configuration
        """
        self.config = config
        self._sessions: dict[str, SessionData] = {}
        self._user_sessions: dict[str, set[str]] = {}

    async def create_session(
        self,
        user_id: str,
        timeout_minutes: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **attributes: Any,
    ) -> SessionData:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        timeout = timeout_minutes or self.config.default_timeout_minutes
        timeout = min(timeout, self.config.max_timeout_minutes)

        expires_at = now + timedelta(minutes=timeout)

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_accessed=now,
            expires_at=expires_at,
            state=SessionState.ACTIVE,
            ip_address=ip_address,
            user_agent=user_agent,
            attributes=attributes,
            security_context={},
        )

        self._sessions[session_id] = session

        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = set()
        self._user_sessions[user_id].add(session_id)

        return session

    async def get_session(self, session_id: str) -> SessionData | None:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check expiration
        if session.expires_at < datetime.utcnow():
            await self.terminate_session(session_id, SessionEventType.TIMEOUT)
            return None

        if session.state != SessionState.ACTIVE:
            return session

        return session

    async def update_session(self, session: SessionData) -> bool:
        """Update session data."""
        if session.session_id not in self._sessions:
            return False

        if session.state != SessionState.ACTIVE:
            return False

        if session.expires_at < datetime.utcnow():
            return False

        self._sessions[session.session_id] = session
        return True

    async def extend_session(self, session_id: str, minutes: int) -> bool:
        """Extend session expiration."""
        session = self._sessions.get(session_id)
        if not session or session.state != SessionState.ACTIVE:
            return False

        now = datetime.utcnow()
        new_expires_at = now + timedelta(minutes=minutes)

        max_expiry = session.created_at + timedelta(minutes=self.config.max_timeout_minutes)
        session.expires_at = min(new_expires_at, max_expiry)

        if session.expires_at <= now:
            await self.terminate_session(session_id, SessionEventType.TIMEOUT)
            return False

        return True

    async def terminate_session(
        self, session_id: str, reason: SessionEventType = SessionEventType.LOGOUT
    ) -> bool:
        """Terminate a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.state = SessionState.TERMINATED

        # Remove from storage
        del self._sessions[session_id]

        # Remove from user index
        if session.user_id in self._user_sessions:
            self._user_sessions[session.user_id].discard(session_id)
            if not self._user_sessions[session.user_id]:
                del self._user_sessions[session.user_id]

        # Publish event if enabled (log only for memory)
        if self.config.enable_event_driven_cleanup:
            event = SessionCleanupEvent(
                session_id=session_id,
                user_id=session.user_id,
                event_type=reason,
                timestamp=datetime.utcnow(),
            )
            logger.info("Session %s terminated: %s. Event: %s", session_id, reason.value, event)

        return True

    async def cleanup_expired_sessions(self) -> int:
        """Cleanup expired sessions."""
        now = datetime.utcnow()
        expired_ids = []

        for session_id, session in self._sessions.items():
            if session.expires_at < now:
                expired_ids.append(session_id)

        count = 0
        for session_id in expired_ids:
            if await self.terminate_session(session_id, SessionEventType.TIMEOUT):
                count += 1

        return count

    async def get_user_sessions(self, user_id: str) -> list[SessionData]:
        """Get all active sessions for a user."""
        session_ids = self._user_sessions.get(user_id, set())
        sessions = []

        # Copy to avoid modification during iteration if cleanup happens
        for sid in list(session_ids):
            session = await self.get_session(sid)
            if session:
                sessions.append(session)

        return sessions

    async def terminate_user_sessions(
        self,
        user_id: str,
        except_session_id: str | None = None,
        reason: SessionEventType = SessionEventType.ADMIN_TERMINATION,
    ) -> int:
        """Terminate all sessions for a user."""
        sessions = await self.get_user_sessions(user_id)
        count = 0
        for session in sessions:
            if except_session_id and session.session_id == except_session_id:
                continue
            if await self.terminate_session(session.session_id, reason):
                count += 1
        return count

    async def process_cleanup_event(self, event: SessionCleanupEvent) -> bool:
        """Process a session cleanup event."""
        logger.info(
            "Processing cleanup event for session %s: %s", event.session_id, event.event_type
        )
        return True

    async def get_metrics(self) -> SessionMetrics:
        """Get session management metrics."""
        return SessionMetrics(
            active_sessions=len(self._sessions),
            total_sessions_created=len(self._sessions),  # Approximation
        )

    async def health_check(self) -> bool:
        """Check if session manager is healthy."""
        return True
