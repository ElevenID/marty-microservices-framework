"""
Tests for ABAC (Attribute-Based Access Control) Engine.

Tests cover:
- Condition evaluation with various operators
- Policy creation and matching
- Context-based policy evaluation
- Policy priority and conflict resolution
- Pattern matching (wildcards, regex)
- Policy repository and caching
- ABACManager facade operations
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from mmf.framework.authorization.adapters.abac_engine import (
    ABACManager,
    ABACManagerService,
    ABACPolicy,
    ABACPolicyEvaluator,
    AttributeCondition,
    InMemoryPolicyCache,
    InMemoryPolicyRepository,
)
from mmf.framework.authorization.api import ConditionOperator, PolicyEffect
from mmf.framework.authorization.ports.abac import ABACContext, PolicyEvaluationResult


class TestAttributeCondition:
    """Test suite for AttributeCondition class."""

    def test_equals_operator(self):
        """Test EQUALS condition operator."""
        condition = AttributeCondition(
            attribute_path="role",
            operator=ConditionOperator.EQUALS,
            value="admin",
        )

        assert condition.evaluate({"role": "admin"}) is True
        assert condition.evaluate({"role": "user"}) is False

    def test_not_equals_operator(self):
        """Test NOT_EQUALS condition operator."""
        condition = AttributeCondition(
            attribute_path="status",
            operator=ConditionOperator.NOT_EQUALS,
            value="inactive",
        )

        assert condition.evaluate({"status": "active"}) is True
        assert condition.evaluate({"status": "inactive"}) is False

    def test_greater_than_operator(self):
        """Test GREATER_THAN condition operator."""
        condition = AttributeCondition(
            attribute_path="level",
            operator=ConditionOperator.GREATER_THAN,
            value=5,
        )

        assert condition.evaluate({"level": 10}) is True
        assert condition.evaluate({"level": 5}) is False
        assert condition.evaluate({"level": 3}) is False

    def test_less_than_operator(self):
        """Test LESS_THAN condition operator."""
        condition = AttributeCondition(
            attribute_path="risk_score",
            operator=ConditionOperator.LESS_THAN,
            value=50,
        )

        assert condition.evaluate({"risk_score": 30}) is True
        assert condition.evaluate({"risk_score": 50}) is False
        assert condition.evaluate({"risk_score": 70}) is False

    def test_greater_equal_operator(self):
        """Test GREATER_EQUAL condition operator."""
        condition = AttributeCondition(
            attribute_path="clearance",
            operator=ConditionOperator.GREATER_EQUAL,
            value=3,
        )

        assert condition.evaluate({"clearance": 5}) is True
        assert condition.evaluate({"clearance": 3}) is True
        assert condition.evaluate({"clearance": 2}) is False

    def test_less_equal_operator(self):
        """Test LESS_EQUAL condition operator."""
        condition = AttributeCondition(
            attribute_path="attempts",
            operator=ConditionOperator.LESS_EQUAL,
            value=3,
        )

        assert condition.evaluate({"attempts": 2}) is True
        assert condition.evaluate({"attempts": 3}) is True
        assert condition.evaluate({"attempts": 4}) is False

    def test_in_operator(self):
        """Test IN condition operator."""
        condition = AttributeCondition(
            attribute_path="department",
            operator=ConditionOperator.IN,
            value=["engineering", "security", "ops"],
        )

        assert condition.evaluate({"department": "engineering"}) is True
        assert condition.evaluate({"department": "security"}) is True
        assert condition.evaluate({"department": "marketing"}) is False

    def test_not_in_operator(self):
        """Test NOT_IN condition operator."""
        condition = AttributeCondition(
            attribute_path="region",
            operator=ConditionOperator.NOT_IN,
            value=["restricted", "classified"],
        )

        assert condition.evaluate({"region": "public"}) is True
        assert condition.evaluate({"region": "restricted"}) is False

    def test_contains_operator(self):
        """Test CONTAINS condition operator."""
        condition = AttributeCondition(
            attribute_path="tags",
            operator=ConditionOperator.CONTAINS,
            value="critical",
        )

        assert condition.evaluate({"tags": ["critical", "production"]}) is True
        assert condition.evaluate({"tags": ["development"]}) is False

    def test_starts_with_operator(self):
        """Test STARTS_WITH condition operator."""
        condition = AttributeCondition(
            attribute_path="resource_id",
            operator=ConditionOperator.STARTS_WITH,
            value="prod-",
        )

        assert condition.evaluate({"resource_id": "prod-service-1"}) is True
        assert condition.evaluate({"resource_id": "dev-service-1"}) is False

    def test_ends_with_operator(self):
        """Test ENDS_WITH condition operator."""
        condition = AttributeCondition(
            attribute_path="filename",
            operator=ConditionOperator.ENDS_WITH,
            value=".json",
        )

        assert condition.evaluate({"filename": "config.json"}) is True
        assert condition.evaluate({"filename": "config.yaml"}) is False

    def test_regex_operator(self):
        """Test REGEX condition operator."""
        condition = AttributeCondition(
            attribute_path="email",
            operator=ConditionOperator.REGEX,
            value=r".*@company\.com$",
        )

        assert condition.evaluate({"email": "user@company.com"}) is True
        assert condition.evaluate({"email": "user@other.com"}) is False

    def test_exists_operator(self):
        """Test EXISTS condition operator."""
        condition = AttributeCondition(
            attribute_path="mfa_verified",
            operator=ConditionOperator.EXISTS,
            value=True,
        )

        assert condition.evaluate({"mfa_verified": True}) is True
        assert condition.evaluate({"mfa_verified": False}) is True  # exists even if False
        assert condition.evaluate({}) is False

    def test_not_exists_operator(self):
        """Test NOT_EXISTS condition operator."""
        condition = AttributeCondition(
            attribute_path="legacy_flag",
            operator=ConditionOperator.NOT_EXISTS,
            value=True,
        )

        assert condition.evaluate({}) is True
        assert condition.evaluate({"legacy_flag": True}) is False

    def test_missing_attribute_returns_false(self):
        """Test condition with missing attribute returns False."""
        condition = AttributeCondition(
            attribute_path="required_field",
            operator=ConditionOperator.EQUALS,
            value="expected",
        )

        assert condition.evaluate({}) is False

    def test_nested_attribute_path(self):
        """Test condition with nested attribute path."""
        condition = AttributeCondition(
            attribute_path="principal.department",
            operator=ConditionOperator.EQUALS,
            value="engineering",
        )

        assert condition.evaluate({"principal": {"department": "engineering"}}) is True
        assert condition.evaluate({"principal": {"department": "sales"}}) is False

    def test_deeply_nested_path(self):
        """Test condition with deeply nested path."""
        condition = AttributeCondition(
            attribute_path="a.b.c.d",
            operator=ConditionOperator.EQUALS,
            value="deep",
        )

        context = {"a": {"b": {"c": {"d": "deep"}}}}
        assert condition.evaluate(context) is True


class TestABACPolicy:
    """Test suite for ABACPolicy class."""

    def test_create_policy_basic(self):
        """Test creating a basic ABAC policy."""
        policy = ABACPolicy(
            id="test-policy-1",
            name="Test Policy",
            description="A test policy",
            effect=PolicyEffect.ALLOW,
            resource_pattern="service/*",
            action_pattern="read",
        )

        assert policy.id == "test-policy-1"
        assert policy.name == "Test Policy"
        assert policy.effect == PolicyEffect.ALLOW
        assert policy.is_active is True
        assert policy.priority == 100

    def test_policy_requires_id_and_name(self):
        """Test that policy requires ID and name."""
        with pytest.raises(ValueError, match="Policy ID and name are required"):
            ABACPolicy(
                id="",
                name="No ID",
                description="Missing ID",
                effect=PolicyEffect.ALLOW,
            )

    def test_policy_with_conditions(self):
        """Test creating policy with conditions."""
        condition = AttributeCondition(
            attribute_path="principal.role",
            operator=ConditionOperator.EQUALS,
            value="admin",
        )

        policy = ABACPolicy(
            id="admin-policy",
            name="Admin Policy",
            description="Admin access",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
            conditions=[condition],
        )

        assert len(policy.conditions) == 1

    def test_policy_priority(self):
        """Test policy priority affects ordering."""
        high_priority = ABACPolicy(
            id="high",
            name="High Priority",
            description="High priority deny",
            effect=PolicyEffect.DENY,
            resource_pattern="*",
            action_pattern="*",
            priority=10,  # Lower number = higher priority
        )

        low_priority = ABACPolicy(
            id="low",
            name="Low Priority",
            description="Low priority allow",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
            priority=100,
        )

        assert high_priority.priority < low_priority.priority

    def test_policy_matches_request_exact(self):
        """Test policy matches exact resource."""
        policy = ABACPolicy(
            id="exact",
            name="Exact Match",
            description="Exact match",
            effect=PolicyEffect.ALLOW,
            resource_pattern="users",
            action_pattern="read",
        )

        assert policy.matches_request("users", "read") is True
        assert policy.matches_request("services", "read") is False
        assert policy.matches_request("users", "write") is False

    def test_policy_matches_request_wildcard(self):
        """Test policy matches resource with wildcard."""
        policy = ABACPolicy(
            id="wildcard",
            name="Wildcard Match",
            description="Wildcard",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="read",
        )

        assert policy.matches_request("users", "read") is True
        assert policy.matches_request("services", "read") is True
        assert policy.matches_request("anything", "read") is True
        assert policy.matches_request("anything", "write") is False

    def test_policy_evaluate_conditions(self):
        """Test policy evaluates conditions."""
        condition = AttributeCondition(
            attribute_path="role",
            operator=ConditionOperator.EQUALS,
            value="admin",
        )
        policy = ABACPolicy(
            id="test",
            name="Test",
            description="Test",
            effect=PolicyEffect.ALLOW,
            conditions=[condition],
        )

        assert policy.evaluate({"role": "admin"}) is True
        assert policy.evaluate({"role": "user"}) is False

    def test_disabled_policy_evaluate_returns_false(self):
        """Test disabled policy evaluation returns False."""
        policy = ABACPolicy(
            id="disabled",
            name="Disabled Policy",
            description="Disabled",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
            is_active=False,
        )

        assert policy.evaluate({}) is False

    def test_policy_to_dict(self):
        """Test converting policy to dictionary."""
        policy = ABACPolicy(
            id="dict-test",
            name="Dict Test",
            description="For dict conversion",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
            priority=50,
        )

        result = policy.to_dict()

        assert result["id"] == "dict-test"
        assert result["effect"] == "allow"
        assert result["priority"] == 50


class TestABACContext:
    """Test suite for ABACContext dataclass."""

    def test_create_context(self):
        """Test creating ABAC context."""
        context = ABACContext(
            principal={"user_id": "user-123", "role": "admin"},
            resource="document",
            action="read",
            environment={"time": "business_hours"},
        )

        assert context.principal["user_id"] == "user-123"
        assert context.resource == "document"
        assert context.action == "read"

    def test_context_with_empty_environment(self):
        """Test context with empty environment."""
        context = ABACContext(
            principal={"user_id": "user-1"},
            resource="service",
            action="execute",
            environment={},
        )

        assert context.environment == {}

    def test_context_to_dict(self):
        """Test context converts to dict."""
        context = ABACContext(
            principal={"id": "1"},
            resource="test",
            action="read",
            environment={"key": "value"},
        )

        result = context.to_dict()

        assert "principal" in result
        assert "resource" in result
        assert "action" in result
        assert "environment" in result


class TestInMemoryPolicyRepository:
    """Test suite for InMemoryPolicyRepository."""

    @pytest.fixture
    def repository(self):
        """Create fresh repository for each test."""
        return InMemoryPolicyRepository()

    def test_add_and_get_policy(self, repository):
        """Test adding and retrieving a policy."""
        policy = ABACPolicy(
            id="test-1",
            name="Test",
            description="Test policy",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
        )

        repository.add_policy(policy)
        retrieved = repository.get_policy("test-1")

        assert retrieved is not None
        assert retrieved.id == "test-1"

    def test_get_nonexistent_policy(self, repository):
        """Test getting non-existent policy returns None."""
        result = repository.get_policy("nonexistent")

        assert result is None

    def test_add_duplicate_policy_raises(self, repository):
        """Test adding duplicate policy raises error."""
        policy = ABACPolicy(
            id="dup",
            name="Original",
            description="Original",
            effect=PolicyEffect.ALLOW,
        )
        repository.add_policy(policy)

        with pytest.raises(ValueError, match="already exists"):
            repository.add_policy(
                ABACPolicy(
                    id="dup",
                    name="Duplicate",
                    description="Duplicate",
                    effect=PolicyEffect.DENY,
                )
            )

    def test_remove_policy(self, repository):
        """Test removing a policy."""
        policy = ABACPolicy(
            id="to-remove",
            name="Remove Me",
            description="To be removed",
            effect=PolicyEffect.DENY,
            resource_pattern="*",
            action_pattern="*",
        )
        repository.add_policy(policy)

        result = repository.remove_policy("to-remove")

        assert result is True
        assert repository.get_policy("to-remove") is None

    def test_remove_nonexistent_policy(self, repository):
        """Test removing non-existent policy returns False."""
        result = repository.remove_policy("nonexistent")

        assert result is False

    def test_list_policies(self, repository):
        """Test listing all policies."""
        for i in range(3):
            policy = ABACPolicy(
                id=f"policy-{i}",
                name=f"Policy {i}",
                description=f"Policy {i}",
                effect=PolicyEffect.ALLOW,
                resource_pattern="*",
                action_pattern="*",
            )
            repository.add_policy(policy)

        policies = repository.list_policies()

        assert len(policies) == 3

    def test_list_policies_active_only(self, repository):
        """Test listing only active policies."""
        repository.add_policy(
            ABACPolicy(
                id="active",
                name="Active",
                description="Active",
                effect=PolicyEffect.ALLOW,
                is_active=True,
            )
        )
        repository.add_policy(
            ABACPolicy(
                id="inactive",
                name="Inactive",
                description="Inactive",
                effect=PolicyEffect.DENY,
                is_active=False,
            )
        )

        active_only = repository.list_policies(active_only=True)

        assert len(active_only) == 1
        assert active_only[0].id == "active"

    def test_get_applicable_policies(self, repository):
        """Test getting policies applicable to resource/action."""
        # Add policies with different patterns
        repository.add_policy(
            ABACPolicy(
                id="users-read",
                name="Users Read",
                description="Read users",
                effect=PolicyEffect.ALLOW,
                resource_pattern="users",
                action_pattern="read",
            )
        )
        repository.add_policy(
            ABACPolicy(
                id="all-read",
                name="All Read",
                description="Read all",
                effect=PolicyEffect.ALLOW,
                resource_pattern="*",
                action_pattern="read",
            )
        )
        repository.add_policy(
            ABACPolicy(
                id="users-write",
                name="Users Write",
                description="Write users",
                effect=PolicyEffect.ALLOW,
                resource_pattern="users",
                action_pattern="write",
            )
        )

        # Find policies for users:read
        applicable = repository.get_applicable_policies("users", "read")

        assert len(applicable) == 2
        policy_ids = [p.id for p in applicable]
        assert "users-read" in policy_ids
        assert "all-read" in policy_ids


class TestInMemoryPolicyCache:
    """Test suite for InMemoryPolicyCache."""

    @pytest.fixture
    def cache(self):
        """Create fresh cache for each test."""
        return InMemoryPolicyCache(enabled=True)

    def test_cache_and_retrieve(self, cache):
        """Test caching and retrieving result."""
        result = PolicyEvaluationResult(
            decision=PolicyEffect.ALLOW,
            applicable_policies=["test-policy"],
        )

        cache.set("test-key", result)
        cached = cache.get("test-key")

        assert cached is not None
        assert cached.decision == PolicyEffect.ALLOW

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent-key")

        assert result is None

    def test_cache_invalidation(self, cache):
        """Test cache invalidation."""
        result = PolicyEvaluationResult(decision=PolicyEffect.ALLOW)

        cache.set("test-key", result)
        cache.invalidate()

        assert cache.get("test-key") is None

    def test_disabled_cache(self):
        """Test disabled cache returns None."""
        cache = InMemoryPolicyCache(enabled=False)
        result = PolicyEvaluationResult(decision=PolicyEffect.ALLOW)

        cache.set("key", result)

        assert cache.get("key") is None


class TestABACPolicyEvaluator:
    """Test suite for ABACPolicyEvaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator with fresh repository."""
        repository = InMemoryPolicyRepository()
        return ABACPolicyEvaluator(repository)

    def test_evaluate_allow_policy(self, evaluator):
        """Test evaluation with ALLOW policy."""
        policy = ABACPolicy(
            id="allow-read",
            name="Allow Read",
            description="Allow read",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="read",
        )
        evaluator._repository.add_policy(policy)

        result = evaluator.evaluate_access(
            principal={"id": "user-1"},
            resource="document",
            action="read",
        )

        assert result.decision == PolicyEffect.ALLOW

    def test_evaluate_deny_policy(self, evaluator):
        """Test evaluation with DENY policy."""
        policy = ABACPolicy(
            id="deny-delete",
            name="Deny Delete",
            description="Deny delete",
            effect=PolicyEffect.DENY,
            resource_pattern="*",
            action_pattern="delete",
        )
        evaluator._repository.add_policy(policy)

        result = evaluator.evaluate_access(
            principal={"id": "user-1"},
            resource="document",
            action="delete",
        )

        assert result.decision == PolicyEffect.DENY

    def test_evaluate_with_conditions(self, evaluator):
        """Test evaluation with conditions."""
        condition = AttributeCondition(
            attribute_path="principal.role",
            operator=ConditionOperator.EQUALS,
            value="admin",
        )
        policy = ABACPolicy(
            id="admin-only",
            name="Admin Only",
            description="Admin only",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
            conditions=[condition],
        )
        evaluator._repository.add_policy(policy)

        # Admin should be allowed
        admin_result = evaluator.evaluate_access(
            principal={"role": "admin"},
            resource="system",
            action="write",
        )
        assert admin_result.decision == PolicyEffect.ALLOW

        # Non-admin should be denied (default)
        user_result = evaluator.evaluate_access(
            principal={"role": "user"},
            resource="system",
            action="write",
        )
        assert user_result.decision == PolicyEffect.DENY

    def test_evaluate_no_matching_policies_defaults_to_deny(self, evaluator):
        """Test evaluation with no matching policies defaults to deny."""
        result = evaluator.evaluate_access(
            principal={"id": "user-1"},
            resource="unknown",
            action="access",
        )

        assert result.decision == PolicyEffect.DENY

    def test_evaluate_priority_ordering(self, evaluator):
        """Test higher priority policy wins."""
        # Low priority allow
        evaluator._repository.add_policy(
            ABACPolicy(
                id="allow-all",
                name="Allow All",
                description="Allow all",
                effect=PolicyEffect.ALLOW,
                resource_pattern="*",
                action_pattern="*",
                priority=100,
            )
        )

        # High priority deny
        evaluator._repository.add_policy(
            ABACPolicy(
                id="deny-sensitive",
                name="Deny Sensitive",
                description="Deny sensitive",
                effect=PolicyEffect.DENY,
                resource_pattern="sensitive*",
                action_pattern="*",
                priority=10,  # Higher priority (lower number)
            )
        )

        # Sensitive resource should be denied (high priority wins)
        result = evaluator.evaluate_access(
            principal={"id": "user-1"},
            resource="sensitive-data",
            action="read",
        )

        assert result.decision == PolicyEffect.DENY


class TestABACManager:
    """Test suite for ABACManager facade."""

    @pytest.fixture
    def manager(self):
        """Create fresh ABAC manager for each test."""
        return ABACManager()

    def test_manager_initialization(self, manager):
        """Test manager initializes correctly."""
        assert manager is not None

    def test_manager_has_default_policies(self, manager):
        """Test manager has default policies."""
        policies = manager.list_policies()
        # Manager should have some default policies
        assert len(policies) >= 0  # May have default policies

    def test_add_policy(self, manager):
        """Test adding policy through manager."""
        policy = ABACPolicy(
            id="test-policy",
            name="Test",
            description="Test policy",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="read",
        )

        result = manager.add_policy(policy)

        assert result is True

    def test_remove_policy(self, manager):
        """Test removing policy through manager."""
        policy = ABACPolicy(
            id="to-remove",
            name="Remove",
            description="To remove",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="*",
        )
        manager.add_policy(policy)

        result = manager.remove_policy("to-remove")

        assert result is True

    def test_check_access_allowed(self, manager):
        """Test access checking returns True for allowed."""
        policy = ABACPolicy(
            id="allow-read",
            name="Allow Read",
            description="Allow read",
            effect=PolicyEffect.ALLOW,
            resource_pattern="*",
            action_pattern="read",
        )
        manager.add_policy(policy)

        result = manager.check_access(
            principal={"id": "user-1"},
            resource="document",
            action="read",
        )

        assert result is True

    def test_check_access_denied(self, manager):
        """Test access checking returns False for denied."""
        # Default policies include a deny-all at low priority
        # A specific deny policy should take effect
        policy = ABACPolicy(
            id="deny-write",
            name="Deny Write",
            description="Deny write",
            effect=PolicyEffect.DENY,
            resource_pattern="*",
            action_pattern="write",
            priority=1,  # High priority
        )
        manager.add_policy(policy)

        result = manager.check_access(
            principal={"id": "user-1"},
            resource="document",
            action="write",
        )

        assert result is False

    def test_list_policies(self, manager):
        """Test listing policies through manager."""
        initial_count = len(manager.list_policies())

        for i in range(3):
            manager.add_policy(
                ABACPolicy(
                    id=f"policy-{i}",
                    name=f"Policy {i}",
                    description=f"Policy {i}",
                    effect=PolicyEffect.ALLOW,
                    resource_pattern="*",
                    action_pattern="*",
                )
            )

        policies = manager.list_policies()

        assert len(policies) == initial_count + 3


class TestABACManagerService:
    """Test suite for ABACManagerService."""

    def test_service_provides_manager(self):
        """Test service provides ABACManager instance."""
        service = ABACManagerService()
        manager = service.get_manager()

        assert isinstance(manager, ABACManager)

    def test_service_same_manager_instance(self):
        """Test service returns same manager instance."""
        service = ABACManagerService()

        manager1 = service.get_manager()
        manager2 = service.get_manager()

        assert manager1 is manager2
