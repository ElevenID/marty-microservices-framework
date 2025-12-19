from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.security.domain.config import SessionConfig
from mmf.core.security.domain.models.session import SessionData, SessionState
from mmf.core.security.domain.services.middleware.session import SessionMiddleware
from mmf.core.security.ports.session import ISessionManager


@pytest.fixture
def session_manager():
    return AsyncMock(spec=ISessionManager)


@pytest.fixture
def config():
    return SessionConfig(enabled=True, session_cookie_name="session_id")


@pytest.fixture
def middleware(session_manager, config):
    return SessionMiddleware(session_manager=session_manager, config=config)


@pytest.mark.asyncio
class TestSessionMiddleware:
    async def test_process_disabled(self, middleware):
        middleware.config.enabled = False
        context = {"session_id": "123"}
        result = await middleware.process(context)
        assert "session" not in result

    async def test_process_no_session_id(self, middleware):
        context = {}
        result = await middleware.process(context)
        assert "session" not in result

    async def test_process_session_from_cookie(self, middleware, session_manager):
        context = {"cookies": {"session_id": "sess-123"}}
        session = SessionData(
            session_id="sess-123",
            user_id="user-123",
            state=SessionState.ACTIVE,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
        )
        session_manager.get_session.return_value = session

        result = await middleware.process(context)

        assert result["session"] == session
        assert result["user"] == "user-123"
        session_manager.update_session.assert_called_once_with(session)

    async def test_process_invalid_session(self, middleware, session_manager):
        context = {"session_id": "sess-123"}
        session_manager.get_session.return_value = None

        result = await middleware.process(context)

        assert "session" not in result

    async def test_process_inactive_session(self, middleware, session_manager):
        context = {"session_id": "sess-123"}
        session = SessionData(
            session_id="sess-123",
            user_id="user-123",
            state=SessionState.EXPIRED,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
        )
        session_manager.get_session.return_value = session

        result = await middleware.process(context)

        assert "session" not in result
        session_manager.update_session.assert_not_called()

    async def test_process_next_middleware(self, middleware):
        context = {}
        next_called = False

        async def next_mw(ctx):
            nonlocal next_called
            next_called = True
            return ctx

        await middleware.process(context, next_middleware=next_mw)
        assert next_called
