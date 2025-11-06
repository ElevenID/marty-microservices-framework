"""
Unit tests for the AuthenticationResult domain model.

Tests the validation, factory methods, and behavior of the AuthenticationResult
value object following domain-driven design principles.
"""

from datetime import datetime, timezone

import pytest

from mmf_new.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)


class TestAuthenticationResult:
    """Test suite for AuthenticationResult domain model."""

    def test_create_success_result(self):
        """Test creating a successful authentication result."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult.create_success(
            user=user,
            metadata={"source": "test"}
        )

        assert result.status == AuthenticationStatus.SUCCESS
        assert result.authenticated_user == user
        assert result.error_message is None
        assert result.error_code is None
        assert result.metadata == {"source": "test"}
        assert result.is_successful is True
        assert result.failed is False

    def test_create_failure_result(self):
        """Test creating a failed authentication result."""
        result = AuthenticationResult.failure(
            message="Invalid credentials",
            code=AuthenticationErrorCode.INVALID_PASSWORD,
            metadata={"attempts": 3}
        )

        assert result.status == AuthenticationStatus.FAILED
        assert result.authenticated_user is None
        assert result.error_message == "Invalid credentials"
        assert result.error_code == AuthenticationErrorCode.INVALID_PASSWORD
        assert result.metadata == {"attempts": 3}
        assert result.is_successful is False
        assert result.failed is True

    def test_create_mfa_required_result(self):
        """Test creating an MFA required result."""
        result = AuthenticationResult.pending_mfa(
            message="Multi-factor authentication required",
            metadata={"mfa_method": "sms"}
        )

        assert result.status == AuthenticationStatus.REQUIRES_MFA
        assert result.authenticated_user is None
        assert result.error_message == "Multi-factor authentication required"
        assert result.error_code == AuthenticationErrorCode.MFA_REQUIRED
        assert result.metadata == {"mfa_method": "sms"}
        assert result.requires_action is True

    def test_validation_success_with_user(self):
        """Test validation rules for successful authentication."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        # Valid success result
        result = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            authenticated_user=user
        )
        assert result.is_successful is True

    def test_validation_success_without_user_fails(self):
        """Test that successful authentication must include a user."""
        with pytest.raises(ValueError, match="Successful authentication must include an authenticated user"):
            AuthenticationResult(
                status=AuthenticationStatus.SUCCESS,
                authenticated_user=None
            )

    def test_validation_success_with_error_fails(self):
        """Test that successful authentication cannot include error details."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        with pytest.raises(ValueError, match="Successful authentication should not include error details"):
            AuthenticationResult(
                status=AuthenticationStatus.SUCCESS,
                authenticated_user=user,
                error_message="Some error"
            )

    def test_validation_failure_without_error_fails(self):
        """Test that failed authentication must include error details."""
        with pytest.raises(ValueError, match="Failed authentication must include an error message"):
            AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                authenticated_user=None
            )

    def test_validation_failure_without_error_code_fails(self):
        """Test that failed authentication must include error code."""
        with pytest.raises(ValueError, match="Failed authentication must include an error code"):
            AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                authenticated_user=None,
                error_message="Error occurred"
            )

    def test_validation_failure_with_user_fails(self):
        """Test that failed authentication should not include user details."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        with pytest.raises(ValueError, match="Failed authentication should not include user details"):
            AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                authenticated_user=user,
                error_message="Error occurred",
                error_code=AuthenticationErrorCode.INVALID_PASSWORD
            )

    def test_timezone_handling(self):
        """Test that attempted_at is timezone-aware."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        # Without timezone
        naive_time = datetime(2023, 1, 1, 12, 0, 0)
        result = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            authenticated_user=user,
            attempted_at=naive_time
        )
        assert result.attempted_at.tzinfo == timezone.utc

    def test_with_user_method(self):
        """Test the with_user method for adding user to success result."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            authenticated_user=user
        )

        new_user = AuthenticatedUser(
            user_id="test-456",
            username="newuser",
            auth_method="password"
        )

        new_result = result.with_user(new_user)
        assert new_result.authenticated_user == new_user
        assert new_result.status == AuthenticationStatus.SUCCESS

    def test_with_user_method_fails_on_non_success(self):
        """Test that with_user fails on non-successful results."""
        result = AuthenticationResult.failure(
            message="Failed",
            code=AuthenticationErrorCode.INVALID_PASSWORD
        )

        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        with pytest.raises(ValueError, match="Cannot add user to non-successful authentication result"):
            result.with_user(user)

    def test_with_error_method(self):
        """Test the with_error method for adding error details."""
        result = AuthenticationResult.failure(
            message="Original error",
            code=AuthenticationErrorCode.INVALID_PASSWORD
        )

        new_result = result.with_error(
            message="New error",
            code=AuthenticationErrorCode.ACCOUNT_LOCKED
        )

        assert new_result.error_message == "New error"
        assert new_result.error_code == AuthenticationErrorCode.ACCOUNT_LOCKED
        assert new_result.status == AuthenticationStatus.FAILED

    def test_with_error_method_fails_on_success(self):
        """Test that with_error fails on successful results."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult.create_success(user=user)

        with pytest.raises(ValueError, match="Cannot add error to successful authentication result"):
            result.with_error("Error", AuthenticationErrorCode.INVALID_PASSWORD)

    def test_with_metadata_method(self):
        """Test the with_metadata method for adding metadata."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult.create_success(user=user)
        new_result = result.with_metadata("key", "value")

        assert new_result.metadata == {"key": "value"}
        assert result.metadata == {}  # Original unchanged

    def test_to_dict_method(self):
        """Test the to_dict method for serialization."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult.create_success(
            user=user,
            metadata={"source": "test"}
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "success"
        assert result_dict["success"] is True
        assert "authenticated_user" in result_dict
        assert result_dict["metadata"] == {"source": "test"}
        assert "attempted_at" in result_dict

    def test_to_dict_with_error(self):
        """Test the to_dict method with error details."""
        result = AuthenticationResult.failure(
            message="Test error",
            code=AuthenticationErrorCode.INVALID_PASSWORD
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "failed"
        assert result_dict["success"] is False
        assert result_dict["error_message"] == "Test error"
        assert result_dict["error_code"] == "INVALID_PASSWORD"

    def test_from_legacy_success(self):
        """Test converting from legacy successful result format."""
        legacy_result = {
            "success": True,
            "user": {
                "user_id": "test-123",
                "username": "testuser",
                "email": "test@example.com",
                "roles": ["admin"],
                "permissions": ["read"],
                "auth_method": "password",
                "metadata": {"key": "value"}
            },
            "metadata": {"source": "legacy"}
        }

        result = AuthenticationResult.from_legacy(legacy_result)

        assert result.is_successful is True
        assert result.authenticated_user.user_id == "test-123"
        assert result.authenticated_user.username == "testuser"
        assert result.metadata == {"source": "legacy"}

    def test_from_legacy_failure(self):
        """Test converting from legacy failed result format."""
        legacy_result = {
            "success": False,
            "error": "Invalid credentials",
            "error_code": "INVALID_PASSWORD",
            "metadata": {"attempts": 3}
        }

        result = AuthenticationResult.from_legacy(legacy_result)

        assert result.is_successful is False
        assert result.error_message == "Invalid credentials"
        assert result.error_code == AuthenticationErrorCode.INVALID_PASSWORD
        assert result.metadata == {"attempts": 3}

    def test_from_legacy_unknown_error_code(self):
        """Test converting legacy result with unknown error code."""
        legacy_result = {
            "success": False,
            "error": "Unknown error",
            "error_code": "UNKNOWN_CODE"
        }

        result = AuthenticationResult.from_legacy(legacy_result)

        assert result.error_code == AuthenticationErrorCode.INTERNAL_ERROR

    def test_immutability(self):
        """Test that the result object is immutable."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )

        result = AuthenticationResult.create_success(user=user)

        # Should not be able to modify attributes
        with pytest.raises(AttributeError):
            result.status = AuthenticationStatus.FAILED

    def test_requires_action_property(self):
        """Test the requires_action property."""
        # MFA required should require action
        mfa_result = AuthenticationResult.pending_mfa()
        assert mfa_result.requires_action is True

        # Success should not require action
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="password"
        )
        success_result = AuthenticationResult.create_success(user=user)
        assert success_result.requires_action is False

        # Failure should not require action
        failure_result = AuthenticationResult.failure(
            message="Failed",
            code=AuthenticationErrorCode.INVALID_PASSWORD
        )
        assert failure_result.requires_action is False
