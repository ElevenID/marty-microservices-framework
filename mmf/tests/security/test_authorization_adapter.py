from unittest.mock import MagicMock

import pytest

from mmf.core.security.domain.models.context import AuthorizationContext
from mmf.core.security.domain.models.result import AuthorizationResult
from mmf.core.security.domain.models.user import User
from mmf.framework.authorization.api import IAuthorizer as CoreIAuthorizer
from mmf.framework.security.adapters.authorization.adapter import CoreAuthorizerAdapter


@pytest.fixture
def mock_core_authorizer():
    return MagicMock(spec=CoreIAuthorizer)


@pytest.fixture
def authorizer_adapter(mock_core_authorizer):
    return CoreAuthorizerAdapter(mock_core_authorizer)


def test_authorize_allowed(authorizer_adapter, mock_core_authorizer):
    # Setup mock
    mock_result = AuthorizationResult(
        allowed=True,
        reason="Policy allowed",
        policies_evaluated=["policy1"],
        metadata={"key": "value"},
    )
    mock_core_authorizer.authorize.return_value = mock_result

    # Call authorize
    context = MagicMock(spec=AuthorizationContext)
    result = authorizer_adapter.authorize(context)

    # Assertions
    assert result.allowed is True
    assert result.reason == "Policy allowed"
    assert result.policies_evaluated == ["policy1"]
    assert result.metadata == {"key": "value"}
    mock_core_authorizer.authorize.assert_called_once_with(context)


def test_authorize_denied(authorizer_adapter, mock_core_authorizer):
    # Setup mock
    mock_result = AuthorizationResult(
        allowed=False, reason="Policy denied", policies_evaluated=["policy1"], metadata={}
    )
    mock_core_authorizer.authorize.return_value = mock_result

    # Call authorize
    context = MagicMock(spec=AuthorizationContext)
    result = authorizer_adapter.authorize(context)

    # Assertions
    assert result.allowed is False
    assert result.reason == "Policy denied"


def test_authorize_exception(authorizer_adapter, mock_core_authorizer):
    # Setup mock to raise exception
    mock_core_authorizer.authorize.side_effect = Exception("Policy engine error")

    # Call authorize
    context = MagicMock(spec=AuthorizationContext)
    result = authorizer_adapter.authorize(context)

    # Assertions
    assert result.allowed is False
    assert "Policy engine error" in result.reason


def test_get_user_permissions(authorizer_adapter, mock_core_authorizer):
    # Setup mock
    mock_core_authorizer.get_user_permissions.return_value = {"read", "write"}

    # Call get_user_permissions
    user = MagicMock(spec=User)
    permissions = authorizer_adapter.get_user_permissions(user)

    # Assertions
    assert permissions == {"read", "write"}
    mock_core_authorizer.get_user_permissions.assert_called_once_with(user)


def test_get_user_permissions_exception(authorizer_adapter, mock_core_authorizer):
    # Setup mock to raise exception
    mock_core_authorizer.get_user_permissions.side_effect = Exception("DB error")

    # Call get_user_permissions
    user = MagicMock(spec=User)
    permissions = authorizer_adapter.get_user_permissions(user)

    # Assertions
    assert permissions == set()
