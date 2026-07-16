"""
Session Management Port

Interface for session management functionality.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.session import (
    SessionCleanupEvent,
    SessionData,
    SessionEventType,
    SessionMetrics,
)


class ISessionManager(ABC):
    """Interface for session management implementations."""

    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        timeout_minutes: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **attributes: Any,
    ) -> SessionData:
        """
        Create a new session.

        Args:
            user_id: User identifier
            timeout_minutes: Session timeout in minutes
            ip_address: Client IP address
            user_agent: Client user agent
            **attributes: Additional session attributes

        Returns:
            Created SessionData
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionData | None:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SessionData if found and valid, None otherwise
        """
        pass

    @abstractmethod
    async def update_session(self, session: SessionData) -> bool:
        """
        Update session data.

        Args:
            session: Session data to update

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def extend_session(self, session_id: str, minutes: int) -> bool:
        """
        Extend session expiration.

        Args:
            session_id: Session identifier
            minutes: Additional minutes to extend

        Returns:
            True if extension was successful
        """
        pass

    @abstractmethod
    async def terminate_session(
        self,
        session_id: str,
        reason: SessionEventType = SessionEventType.LOGOUT,
    ) -> bool:
        """
        Terminate a session.

        Args:
            session_id: Session identifier
            reason: Termination reason

        Returns:
            True if termination was successful
        """
        pass

    @abstractmethod
    async def terminate_user_sessions(
        self,
        user_id: str,
        except_session_id: str | None = None,
        reason: SessionEventType = SessionEventType.ADMIN_TERMINATION,
    ) -> int:
        """
        Terminate all sessions for a user.

        Args:
            user_id: User identifier
            except_session_id: Session ID to exclude from termination
            reason: Termination reason

        Returns:
            Number of sessions terminated
        """
        pass

    @abstractmethod
    async def get_user_sessions(self, user_id: str) -> list[SessionData]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active sessions
        """
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        pass

    @abstractmethod
    async def process_cleanup_event(self, event: SessionCleanupEvent) -> bool:
        """
        Process a session cleanup event.

        Args:
            event: Cleanup event to process

        Returns:
            True if processing was successful
        """
        pass

    @abstractmethod
    async def get_metrics(self) -> SessionMetrics:
        """
        Get session management metrics.

        Returns:
            SessionMetrics with current statistics
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if session manager is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass
