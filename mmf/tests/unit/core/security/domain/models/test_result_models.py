import pytest

from mmf.core.security.domain.models.result import (
    AuthenticationResult,
    AuthorizationResult,
    ComplianceResult,
    PolicyResult,
    SecurityDecision,
)
from mmf.core.security.domain.models.user import AuthenticatedUser


class TestResultModels:
    def test_authentication_result(self):
        user = AuthenticatedUser(user_id="user-1")

        success = AuthenticationResult(success=True, user=user)
        assert success.success is True
        assert success.user == user
        assert success.error is None
        assert success.error_code is None
        assert success.metadata == {}

        failure = AuthenticationResult(
            success=False, error="Invalid credentials", error_code="AUTH_FAILED"
        )
        assert failure.success is False
        assert failure.user is None
        assert failure.error == "Invalid credentials"
        assert failure.error_code == "AUTH_FAILED"

    def test_authorization_result(self):
        result = AuthorizationResult(
            allowed=True, reason="Admin access", policies_evaluated=["admin_policy"]
        )

        assert result.allowed is True
        assert result.reason == "Admin access"
        assert result.policies_evaluated == ["admin_policy"]
        assert result.metadata == {}

    def test_security_decision(self):
        decision = SecurityDecision(
            allowed=False,
            reason="Rate limit exceeded",
            policies_evaluated=["rate_limit_policy"],
            required_attributes={"tier": "gold"},
            evaluation_time_ms=10.5,
            cache_key="key-123",
        )

        assert decision.allowed is False
        assert decision.reason == "Rate limit exceeded"
        assert decision.policies_evaluated == ["rate_limit_policy"]
        assert decision.required_attributes == {"tier": "gold"}
        assert decision.evaluation_time_ms == 10.5
        assert decision.cache_key == "key-123"

    def test_policy_result(self):
        result = PolicyResult(decision=True, confidence=0.95, evaluation_time=0.5)

        assert result.decision is True
        assert result.confidence == 0.95
        assert result.evaluation_time == 0.5
        assert result.metadata == {}

    def test_compliance_result(self):
        result = ComplianceResult(
            framework="GDPR",
            passed=False,
            score=0.75,
            findings=[{"id": "F1", "desc": "Missing encryption"}],
            recommendations=["Enable TLS"],
        )

        assert result.framework == "GDPR"
        assert result.passed is False
        assert result.score == 0.75
        assert len(result.findings) == 1
        assert result.recommendations == ["Enable TLS"]
        assert result.metadata == {}
