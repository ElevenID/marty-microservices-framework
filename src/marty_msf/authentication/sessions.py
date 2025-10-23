"""
Session Management Module

This module contains concrete implementations of session management for security operations.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- In-memory session storage
- Session expiration and cleanup
- Thread-safe operations
- Configurable session lifetimes
"""

from __future__ import annotations

import logging
import time
from threading import RLock
from typing import Any
from uuid import uuid4

from .api import ISessionManager, SecurityPrincipal

logger = logging.getLogger(__name__)


class InMemorySessionManager:
    """
    In-memory session manager.

    This manager stores sessions in memory, making it suitable for
    single-instance applications or development environments.
    """

    def __init__(self, default_ttl: float = 3600.0):  # 1 hour default
        """
        Initialize the in-memory session manager.

        Args:
            default_ttl: Default session TTL in seconds
        """
        self.default_ttl = default_ttl
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create_session(self, principal: SecurityPrincipal, metadata: dict[str, Any] | None = None) -> str:
        """
        Create a new session for a principal.

        Args:
            principal: Security principal
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        with self._lock:
            session_id = str(uuid4())
            expires_at = time.time() + self.default_ttl

            session_data = {
                "principal": principal,
                "created_at": time.time(),
                "expires_at": expires_at,
                "metadata": metadata or {}
            }

            self._sessions[session_id] = session_data

            logger.debug("Created session %s for principal %s", session_id, principal.id)
            return session_id

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SecurityPrincipal or None if not found
        """
        with self._lock:
            self._cleanup_expired_sessions()

            session_data = self._sessions.get(session_id)
            if session_data is None:
                return None

            # Check if session is expired
            if time.time() > session_data["expires_at"]:
                del self._sessions[session_id]
                logger.debug("Session %s expired", session_id)
                return None

            return session_data["principal"]

    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successfully invalidated
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug("Invalidated session %s", session_id)
                return True
            return False

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from storage."""
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session_data in self._sessions.items()
            if current_time > session_data["expires_at"]
        ]

        for session_id in expired_sessions:
            del self._sessions[session_id]

        if expired_sessions:
            logger.debug("Cleaned up %d expired sessions", len(expired_sessions))

    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            self._cleanup_expired_sessions()
            return len(self._sessions)


class NoOpSessionManager:
    """
    No-operation session manager for testing.

    This manager doesn't actually store sessions, useful for
    stateless applications or testing scenarios.
    """

    def create_session(self, principal: SecurityPrincipal, metadata: dict[str, Any] | None = None) -> str:
        """Create a session (returns dummy ID)."""
        return "noop-session"

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """Get session (always returns None)."""
        return None

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate session (always returns True)."""
        return True
