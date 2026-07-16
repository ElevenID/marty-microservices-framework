import pytest

from mmf.core.security.domain.models.result import (
    AuthenticationResult,
    AuthorizationResult,
    ComplianceResult,
    PolicyResult,
    SecurityDecision,
)
from mmf.core.security.domain.models.user import AuthenticatedUser


class TestAuthenticationResult:
    def test_success_result(self):
        user = AuthenticatedUser(user_id="test-user")
        result = AuthenticationResult(success=True, user=user)
        assert result.success
        assert result.user == user
        assert result.error is None
        assert result.error_code is None
        assert result.metadata == {}

    def test_failure_result(self):
        result = AuthenticationResult(
            success=False, error="Invalid credentials", error_code="AUTH_FAILED"
        )
        assert not result.success
        assert result.user is None
        assert result.error == "Invalid credentials"
        assert result.error_code == "AUTH_FAILED"


class TestAuthorizationResult:
    def test_allowed_result(self):
        result = AuthorizationResult(allowed=True, reason="Admin access")
        assert result.allowed
        assert result.reason == "Admin access"
        assert result.policies_evaluated == []
        assert result.metadata == {}

    def test_denied_result(self):
        result = AuthorizationResult(
            allowed=False,
            reason="Insufficient permissions",
            policies_evaluated=["policy-1", "policy-2"],
        )
        assert not result.allowed
        assert result.reason == "Insufficient permissions"
        assert result.policies_evaluated == ["policy-1", "policy-2"]


class TestSecurityDecision:
    def test_decision_creation(self):
        result = SecurityDecision(
            allowed=True,
            reason="Policy match",
            policies_evaluated=["p1"],
            required_attributes={"role": "admin"},
            evaluation_time_ms=10.5,
            cache_key="cache-123",
        )
        assert result.allowed
        assert result.reason == "Policy match"
        assert result.policies_evaluated == ["p1"]
        assert result.required_attributes == {"role": "admin"}
        assert result.evaluation_time_ms == 10.5
        assert result.cache_key == "cache-123"


class TestPolicyResult:
    def test_policy_result_creation(self):
        result = PolicyResult(decision=True, confidence=0.95, evaluation_time=0.05)
        assert result.decision
        assert result.confidence == 0.95
        assert result.evaluation_time == 0.05
        assert result.metadata == {}


class TestComplianceResult:
    def test_compliance_result_creation(self):
        result = ComplianceResult(
            framework="GDPR",
            passed=False,
            score=85.5,
            findings=[{"id": "F1", "severity": "high"}],
            recommendations=["Fix F1"],
        )
        assert result.framework == "GDPR"
        assert not result.passed
        assert result.score == 85.5
        assert result.findings == [{"id": "F1", "severity": "high"}]
        assert result.recommendations == ["Fix F1"]
        assert result.metadata == {}
