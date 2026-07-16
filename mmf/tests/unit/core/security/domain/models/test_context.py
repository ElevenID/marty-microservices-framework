from datetime import datetime, timezone

import pytest

from mmf.core.security.domain.models.context import (
    AuthorizationContext,
    SecurityContext,
)
from mmf.core.security.domain.models.user import AuthenticatedUser, SecurityPrincipal


class TestAuthorizationContext:
    def test_authorization_context_creation(self):
        user = AuthenticatedUser(user_id="test-user")
        context = AuthorizationContext(user=user, resource="test-resource", action="read")

        assert context.user == user
        assert context.resource == "test-resource"
        assert context.action == "read"
        assert context.environment == {}
        assert isinstance(context.timestamp, datetime)
        assert context.timestamp.tzinfo == timezone.utc

    def test_authorization_context_with_environment(self):
        user = AuthenticatedUser(user_id="test-user")
        env = {"ip": "127.0.0.1"}
        context = AuthorizationContext(
            user=user, resource="test-resource", action="read", environment=env
        )

        assert context.environment == env


class TestSecurityContext:
    def test_security_context_creation(self):
        principal = SecurityPrincipal(id="test-principal", type="user")
        context = SecurityContext(principal=principal, resource="test-resource", action="write")

        assert context.principal == principal
        assert context.resource == "test-resource"
        assert context.action == "write"
        assert context.environment == {}
        assert context.request_metadata == {}
        assert context.request_id is None
        assert isinstance(context.timestamp, datetime)
        assert context.timestamp.tzinfo == timezone.utc

    def test_security_context_full_creation(self):
        principal = SecurityPrincipal(id="test-principal", type="service")
        env = {"ip": "10.0.0.1"}
        metadata = {"user_agent": "test-agent"}

        context = SecurityContext(
            principal=principal,
            resource="api/data",
            action="delete",
            environment=env,
            request_metadata=metadata,
            request_id="req-123",
        )

        assert context.principal == principal
        assert context.resource == "api/data"
        assert context.action == "delete"
        assert context.environment == env
        assert context.request_metadata == metadata
        assert context.request_id == "req-123"
