import pytest

from mmf.core.security.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CertificateValidationError,
    InsufficientPermissionsError,
    InvalidTokenError,
    PermissionDeniedError,
    RateLimitExceededError,
    RoleRequiredError,
    SecretManagerError,
    SecurityError,
    handle_security_exception,
)


class TestSecurityExceptions:
    def test_inheritance_hierarchy(self):
        assert issubclass(AuthenticationError, SecurityError)
        assert issubclass(AuthorizationError, SecurityError)
        assert issubclass(SecretManagerError, SecurityError)
        assert issubclass(RateLimitExceededError, SecurityError)

        assert issubclass(InsufficientPermissionsError, AuthorizationError)
        assert issubclass(PermissionDeniedError, AuthorizationError)
        assert issubclass(RoleRequiredError, AuthorizationError)

        assert issubclass(InvalidTokenError, AuthenticationError)
        assert issubclass(CertificateValidationError, AuthenticationError)

    def test_exception_instantiation(self):
        exc = SecurityError("test error")
        assert str(exc) == "test error"

        exc = AuthenticationError("auth failed")
        assert str(exc) == "auth failed"

    def test_handle_security_exception(self):
        # Just verify it doesn't crash
        exc = SecurityError("test")
        handle_security_exception(exc)
