"""
Session Middleware

Middleware for managing user sessions.
"""

from typing import Any

from mmf.core.security.domain.config import SessionConfig
from mmf.core.security.domain.models.session import SessionData, SessionState
from mmf.core.security.domain.services.middleware.base import BaseMiddleware
from mmf.core.security.ports.session import ISessionManager


class SessionMiddleware(BaseMiddleware):
    """Middleware for session management."""

    def __init__(self, session_manager: ISessionManager, config: SessionConfig):
        self.session_manager = session_manager
        self.config = config

    async def process(
        self,
        request_context: dict[str, Any],
        next_middleware: Any = None,
    ) -> dict[str, Any]:
        """
        Manage session for request.
        """
        session = await self._manage_session(request_context)
        if session:
            request_context["user"] = session.user_id
            request_context["session"] = session

        if next_middleware:
            return await next_middleware(request_context)

        return request_context

    async def _manage_session(
        self,
        request_context: dict[str, Any],
    ) -> SessionData | None:
        """Manage session for request."""
        if not self.config.enabled:
            return None

        session_id = request_context.get("session_id")
        if not session_id:
            # Try to get from cookies
            cookies = request_context.get("cookies", {})
            session_id = cookies.get(self.config.session_cookie_name)

        if not session_id:
            return None

        session = await self.session_manager.get_session(session_id)
        if not session:
            return None

        # Validate session
        if session.state != SessionState.ACTIVE:
            return None

        # Update access time (sliding window)
        await self.session_manager.update_session(session)

        return session
