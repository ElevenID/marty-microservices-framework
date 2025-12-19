from datetime import datetime

import pytest

from mmf.core.security.domain.models.context import (
    AuthorizationContext,
    SecurityContext,
)
from mmf.core.security.domain.models.user import AuthenticatedUser, SecurityPrincipal


class TestAuthorizationContext:
    def test_defaults(self):
        user = AuthenticatedUser(user_id="user-1")
        context = AuthorizationContext(user=user, resource="document:123", action="read")

        assert context.user == user
        assert context.resource == "document:123"
        assert context.action == "read"
        assert context.environment == {}
        assert isinstance(context.timestamp, datetime)

    def test_full_initialization(self):
        user = AuthenticatedUser(user_id="user-1")
        env = {"ip": "127.0.0.1"}
        context = AuthorizationContext(
            user=user, resource="document:123", action="read", environment=env
        )

        assert context.environment == env


class TestSecurityContext:
    def test_defaults(self):
        principal = SecurityPrincipal(id="p-1", type="user")
        context = SecurityContext(principal=principal, resource="api/v1/users", action="GET")

        assert context.principal == principal
        assert context.resource == "api/v1/users"
        assert context.action == "GET"
        assert context.environment == {}
        assert context.request_metadata == {}
        assert context.request_id is None
        assert isinstance(context.timestamp, datetime)

    def test_full_initialization(self):
        principal = SecurityPrincipal(id="p-1", type="user")
        env = {"ip": "127.0.0.1"}
        meta = {"trace_id": "abc"}
        context = SecurityContext(
            principal=principal,
            resource="api/v1/users",
            action="GET",
            environment=env,
            request_metadata=meta,
            request_id="req-123",
        )

        assert context.environment == env
        assert context.request_metadata == meta
        assert context.request_id == "req-123"
