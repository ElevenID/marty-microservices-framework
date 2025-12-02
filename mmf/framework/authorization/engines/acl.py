"""
Access Control List (ACL) Policy Engine Implementation

Provides resource-level access control with fine-grained permissions
for specific resources and resource types. Supports:
- Resource pattern matching with wildcards
- Principal types: users, roles, groups
- Allow and deny rules with precedence
- Conditional access based on time, IP, request method
- Resource type definitions with default permissions
- Conflict detection

ACL Entry Format:
    {
        "resource_pattern": "/api/v1/documents/*",
        "principal": "role:editor",
        "permissions": ["read", "write"],
        "allow": true,
        "conditions": {
            "time_range": {"start": "09:00", "end": "17:00"},
            "ip_range": ["10.0.0.0/8"]
        }
    }
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .base import AbstractPolicyEngine, SecurityContext, SecurityDecision

logger = logging.getLogger(__name__)

__all__ = ["ACLPolicyEngine", "ACLPermission", "ACLEntry"]


class ACLPermission(Enum):
    """Standard ACL permissions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CREATE = "create"
    LIST = "list"
    UPDATE = "update"


class ACLEntry:
    """
    Represents a single ACL entry.

    An ACL entry specifies what permissions a principal has on resources
    matching a pattern, optionally with additional conditions.

    Attributes:
        resource_pattern: Pattern for matching resources (supports wildcards)
        principal: Principal identifier (user ID, role:name, group:name, or *)
        permissions: Set of permission strings
        allow: True for allow rule, False for deny rule
        conditions: Additional conditions for access (time, IP, etc.)
        compiled_pattern: Compiled regex for resource matching
    """

    def __init__(
        self,
        resource_pattern: str,
        principal: str,
        permissions: set[str],
        allow: bool = True,
        conditions: dict[str, Any] | None = None,
    ):
        """
        Initialize ACL entry.

        Args:
            resource_pattern: Pattern for matching resources
            principal: Principal identifier
            permissions: Set of permission strings
            allow: True for allow rule, False for deny rule
            conditions: Optional conditions for access
        """
        self.resource_pattern = resource_pattern
        self.principal = principal
        self.permissions = permissions
        self.allow = allow
        self.conditions = conditions or {}

        # Compile regex pattern for resource matching
        regex_pattern = resource_pattern.replace("*", ".*").replace("?", ".")
        self.compiled_pattern = re.compile(f"^{regex_pattern}$")

    def matches_resource(self, resource: str) -> bool:
        """
        Check if this ACL entry applies to the resource.

        Args:
            resource: Resource identifier

        Returns:
            True if pattern matches resource
        """
        return bool(self.compiled_pattern.match(resource))

    def matches_principal(self, principal_id: str, roles: set[str], groups: set[str]) -> bool:
        """
        Check if this ACL entry applies to the principal.

        Supports:
        - Direct user match: "user123"
        - Role match: "role:admin"
        - Group match: "group:engineering"
        - Wildcard: "*"

        Args:
            principal_id: User ID
            roles: User's roles
            groups: User's groups

        Returns:
            True if entry applies to principal
        """
        # Direct user match
        if self.principal == principal_id:
            return True

        # Role match (prefixed with role:)
        if self.principal.startswith("role:"):
            role_name = self.principal[5:]
            return role_name in roles

        # Group match (prefixed with group:)
        if self.principal.startswith("group:"):
            group_name = self.principal[6:]
            return group_name in groups

        # Wildcard match
        if self.principal == "*":
            return True

        return False

    def evaluate_conditions(self, context: SecurityContext) -> bool:
        """
        Evaluate additional conditions for this ACL entry.

        Args:
            context: Security context

        Returns:
            True if all conditions are satisfied
        """
        if not self.conditions:
            return True

        for condition_type, condition_value in self.conditions.items():
            if condition_type == "time_range":
                if not self._check_time_range(condition_value):
                    return False
            elif condition_type == "ip_range":
                if not self._check_ip_range(condition_value, context):
                    return False
            elif condition_type == "request_method":
                if not self._check_request_method(condition_value, context):
                    return False
            elif condition_type == "resource_attributes":
                if not self._check_resource_attributes(condition_value, context):
                    return False

        return True

    def _check_time_range(self, time_range: dict[str, str]) -> bool:
        """Check if current time is within allowed range."""
        try:
            current_time = datetime.now(timezone.utc).time()
            start_time = datetime.strptime(time_range["start"], "%H:%M").time()
            end_time = datetime.strptime(time_range["end"], "%H:%M").time()
            return start_time <= current_time <= end_time
        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid time range condition: {e}")
            return False

    def _check_ip_range(self, ip_ranges: list[str], context: SecurityContext) -> bool:
        """Check if client IP is in allowed ranges."""
        client_ip = context.request_metadata.get("client_ip")
        if not client_ip:
            return False

        try:
            client_addr = ipaddress.ip_address(client_ip)
            for ip_range in ip_ranges:
                if client_addr in ipaddress.ip_network(ip_range):
                    return True
        except (ValueError, ipaddress.AddressValueError) as e:
            logger.warning(f"Invalid IP address or range: {e}")

        return False

    def _check_request_method(self, allowed_methods: list[str], context: SecurityContext) -> bool:
        """Check if request method is allowed."""
        request_method = context.request_metadata.get("request_method", "").upper()
        return request_method in [method.upper() for method in allowed_methods]

    def _check_resource_attributes(
        self, required_attrs: dict[str, Any], context: SecurityContext
    ) -> bool:
        """Check if resource has required attributes."""
        resource_attrs = context.request_metadata.get("resource_attributes", {})

        for attr_name, expected_value in required_attrs.items():
            if attr_name not in resource_attrs:
                return False

            actual_value = resource_attrs[attr_name]
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False

        return True


class ACLPolicyEngine(AbstractPolicyEngine):
    """
    ACL-based policy engine for fine-grained resource access control.

    Provides resource-level access control with support for:
    - Resource patterns with wildcards
    - User, role, and group principals
    - Allow and deny rules (deny takes precedence)
    - Conditional access
    - Resource types with default permissions

    Attributes:
        config: Engine configuration
        acl_entries: List of ACL entries
        resource_types: Resource type definitions
        default_permissions: Default permissions by role
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize ACL policy engine.

        Args:
            config: Optional configuration with initial policies
        """
        self.config = config or {}
        self.acl_entries: list[ACLEntry] = []
        self.resource_types: dict[str, dict[str, Any]] = {}
        self.default_permissions: dict[str, set[str]] = {}

        # Load initial ACL policies
        self._load_initial_acls()

    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """
        Evaluate ACL policies against security context.

        Process:
        1. Find applicable ACL entries
        2. Check for deny rules (takes precedence)
        3. Check for allow rules
        4. Fall back to default permissions

        Args:
            context: Security context

        Returns:
            SecurityDecision indicating if access is allowed
        """
        start_time = datetime.now(timezone.utc)

        try:
            resource = context.resource
            action = context.action
            principal = context.principal

            if not principal:
                return SecurityDecision(
                    allowed=False,
                    reason="No principal provided",
                    metadata={"engine": "acl", "confidence": 1.0},
                )

            # Get principal's roles and groups
            principal_roles = set(principal.roles)
            principal_groups = set(getattr(principal, "groups", []))

            # Find applicable ACL entries
            applicable_entries = []
            for entry in self.acl_entries:
                if (
                    entry.matches_resource(resource)
                    and entry.matches_principal(principal.id, principal_roles, principal_groups)
                    and action in entry.permissions
                    and entry.evaluate_conditions(context)
                ):
                    applicable_entries.append(entry)

            # Evaluate ACL entries (deny takes precedence)
            has_allow = False
            has_deny = False
            deny_reasons = []
            allow_reasons = []

            for entry in applicable_entries:
                if entry.allow:
                    has_allow = True
                    allow_reasons.append(
                        f"Allow rule for {entry.principal} on {entry.resource_pattern}"
                    )
                else:
                    has_deny = True
                    deny_reasons.append(
                        f"Deny rule for {entry.principal} on {entry.resource_pattern}"
                    )

            # Determine final decision
            if has_deny:
                decision = SecurityDecision(
                    allowed=False,
                    reason=f"Access denied: {', '.join(deny_reasons)}",
                    metadata={"engine": "acl", "confidence": 1.0},
                )
            elif has_allow:
                decision = SecurityDecision(
                    allowed=True,
                    reason=f"Access granted: {', '.join(allow_reasons)}",
                    metadata={"engine": "acl", "confidence": 1.0},
                )
            else:
                # Check default permissions
                default_allowed = self._check_default_permissions(resource, action, principal_roles)
                decision = SecurityDecision(
                    allowed=default_allowed,
                    reason="No explicit ACL rules found, using default permissions"
                    if default_allowed
                    else "No ACL rules grant access",
                    metadata={"engine": "acl", "confidence": 0.8 if default_allowed else 1.0},
                )

            # Add evaluation metadata
            decision.policies_evaluated = [f"acl:{len(applicable_entries)}_entries"]
            decision.metadata.update(
                {
                    "applicable_entries": len(applicable_entries),
                    "resource_type": self._get_resource_type(resource),
                    "principal_roles": list(principal_roles),
                    "principal_groups": list(principal_groups),
                }
            )

            end_time = datetime.now(timezone.utc)
            decision.evaluation_time_ms = (end_time - start_time).total_seconds() * 1000

            logger.debug(
                f"ACL evaluation: {decision.allowed} for {principal.id} on {resource}:{action}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error evaluating ACL policy: {e}", exc_info=True)
            return SecurityDecision(
                allowed=False,
                reason=f"ACL evaluation error: {str(e)}",
                metadata={"engine": "acl", "confidence": 1.0, "error": str(e)},
            )

    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """
        Load ACL policies from configuration.

        Supports:
        - type: "acl" - ACL entries
        - type: "resource_type" - Resource type definitions
        - type: "default_permissions" - Default permissions by role

        Args:
            policies: List of policy definitions

        Returns:
            True if policies loaded successfully
        """
        try:
            self.acl_entries.clear()

            for policy in policies:
                policy_type = policy.get("type")
                if policy_type == "acl":
                    self._load_acl_policy(policy)
                elif policy_type == "resource_type":
                    self._load_resource_type(policy)
                elif policy_type == "default_permissions":
                    self._load_default_permissions(policy)

            logger.info(f"Loaded {len(self.acl_entries)} ACL entries")
            return True

        except Exception as e:
            logger.error(f"Failed to load ACL policies: {e}", exc_info=True)
            return False

    async def validate_policies(self) -> list[str]:
        """
        Validate loaded ACL policies.

        Checks:
        - Resource pattern validity
        - Permission validity
        - Principal format
        - Conflicting rules

        Returns:
            List of validation error messages
        """
        errors = []

        # Validate ACL entries
        for i, entry in enumerate(self.acl_entries):
            try:
                # Test regex compilation
                re.compile(entry.resource_pattern)
            except re.error as e:
                errors.append(
                    f"ACL entry {i}: Invalid resource pattern '{entry.resource_pattern}': {e}"
                )

            # Validate permissions
            for perm in entry.permissions:
                if not isinstance(perm, str) or not perm:
                    errors.append(f"ACL entry {i}: Invalid permission '{perm}'")

            # Validate principal format
            if not entry.principal:
                errors.append(f"ACL entry {i}: Empty principal")
            elif (
                entry.principal.startswith(("role:", "group:"))
                and len(entry.principal.split(":", 1)) != 2
            ):
                errors.append(f"ACL entry {i}: Invalid principal format '{entry.principal}'")

        # Check for conflicting rules
        conflicts = self._detect_conflicts()
        errors.extend(conflicts)

        return errors

    def add_acl_entry(
        self,
        resource_pattern: str,
        principal: str,
        permissions: set[str],
        allow: bool = True,
        conditions: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a new ACL entry.

        Args:
            resource_pattern: Resource pattern with wildcards
            principal: Principal identifier
            permissions: Set of permissions
            allow: True for allow rule, False for deny rule
            conditions: Optional access conditions

        Returns:
            True if entry added successfully
        """
        try:
            entry = ACLEntry(resource_pattern, principal, permissions, allow, conditions)
            self.acl_entries.append(entry)
            logger.info(f"Added ACL entry: {principal} -> {resource_pattern} ({permissions})")
            return True
        except Exception as e:
            logger.error(f"Failed to add ACL entry: {e}", exc_info=True)
            return False

    def remove_acl_entries(self, resource_pattern: str, principal: str) -> int:
        """
        Remove ACL entries matching resource pattern and principal.

        Args:
            resource_pattern: Resource pattern to match
            principal: Principal to match

        Returns:
            Number of entries removed
        """
        original_count = len(self.acl_entries)
        self.acl_entries = [
            entry
            for entry in self.acl_entries
            if not (entry.resource_pattern == resource_pattern and entry.principal == principal)
        ]
        removed_count = original_count - len(self.acl_entries)
        logger.info(f"Removed {removed_count} ACL entries for {principal} on {resource_pattern}")
        return removed_count

    def list_acl_entries(self, resource_pattern: str | None = None) -> list[dict[str, Any]]:
        """
        List ACL entries, optionally filtered by resource pattern.

        Args:
            resource_pattern: Optional pattern to filter by

        Returns:
            List of ACL entry dictionaries
        """
        entries = []
        for entry in self.acl_entries:
            if resource_pattern is None or entry.resource_pattern == resource_pattern:
                entries.append(
                    {
                        "resource_pattern": entry.resource_pattern,
                        "principal": entry.principal,
                        "permissions": list(entry.permissions),
                        "allow": entry.allow,
                        "conditions": entry.conditions,
                    }
                )
        return entries

    def get_effective_permissions(
        self, resource: str, principal_id: str, roles: set[str], groups: set[str]
    ) -> set[str]:
        """
        Get effective permissions for a principal on a resource.

        Considers allow rules, deny rules, and default permissions.

        Args:
            resource: Resource identifier
            principal_id: User ID
            roles: User's roles
            groups: User's groups

        Returns:
            Set of effective permissions
        """
        effective_permissions = set()
        denied_permissions = set()

        for entry in self.acl_entries:
            if entry.matches_resource(resource) and entry.matches_principal(
                principal_id, roles, groups
            ):
                if entry.allow:
                    effective_permissions.update(entry.permissions)
                else:
                    denied_permissions.update(entry.permissions)

        # Remove denied permissions
        effective_permissions -= denied_permissions

        # Add default permissions if no explicit ACL
        if not effective_permissions and resource:
            default_perms = self._get_default_permissions_for_resource(resource, roles)
            effective_permissions.update(default_perms)

        return effective_permissions

    def _load_initial_acls(self) -> None:
        """Load initial ACL configuration."""
        initial_policies = self.config.get("initial_policies", [])
        if initial_policies:
            # Run async load_policies in sync context
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.load_policies(initial_policies))
            except RuntimeError:
                # Create new event loop if none exists
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.load_policies(initial_policies))

    def _load_acl_policy(self, policy: dict[str, Any]) -> None:
        """Load a single ACL policy."""
        entries = policy.get("entries", [])
        for entry_data in entries:
            entry = ACLEntry(
                resource_pattern=entry_data["resource_pattern"],
                principal=entry_data["principal"],
                permissions=set(entry_data["permissions"]),
                allow=entry_data.get("allow", True),
                conditions=entry_data.get("conditions"),
            )
            self.acl_entries.append(entry)

    def _load_resource_type(self, policy: dict[str, Any]) -> None:
        """Load resource type definition."""
        resource_type = policy.get("name")
        if resource_type:
            self.resource_types[resource_type] = {
                "pattern": policy.get("pattern", f"{resource_type}:*"),
                "default_permissions": set(policy.get("default_permissions", [])),
                "attributes": policy.get("attributes", {}),
            }

    def _load_default_permissions(self, policy: dict[str, Any]) -> None:
        """Load default permissions configuration."""
        for role, permissions in policy.get("permissions", {}).items():
            self.default_permissions[role] = set(permissions)

    def _check_default_permissions(self, resource: str, action: str, roles: set[str]) -> bool:
        """Check if action is allowed by default permissions."""
        for role in roles:
            if role in self.default_permissions:
                if action in self.default_permissions[role]:
                    return True
        return False

    def _get_default_permissions_for_resource(self, resource: str, roles: set[str]) -> set[str]:
        """Get default permissions for a resource based on roles."""
        permissions = set()

        # Check resource type defaults
        resource_type = self._get_resource_type(resource)
        if resource_type in self.resource_types:
            permissions.update(self.resource_types[resource_type]["default_permissions"])

        # Check role-based defaults
        for role in roles:
            if role in self.default_permissions:
                permissions.update(self.default_permissions[role])

        return permissions

    def _get_resource_type(self, resource: str) -> str:
        """Extract resource type from resource identifier."""
        if ":" in resource:
            return resource.split(":", 1)[0]
        return "unknown"

    def _detect_conflicts(self) -> list[str]:
        """Detect conflicting ACL rules."""
        conflicts = []

        # Group entries by resource pattern and principal
        groups = {}
        for entry in self.acl_entries:
            key = (entry.resource_pattern, entry.principal)
            if key not in groups:
                groups[key] = []
            groups[key].append(entry)

        # Check for conflicts within each group
        for (resource_pattern, principal), entries in groups.items():
            allow_entries = [e for e in entries if e.allow]
            deny_entries = [e for e in entries if not e.allow]

            # Check for overlapping permissions between allow and deny rules
            if allow_entries and deny_entries:
                for allow_entry in allow_entries:
                    for deny_entry in deny_entries:
                        overlap = allow_entry.permissions & deny_entry.permissions
                        if overlap:
                            conflicts.append(
                                f"Conflicting rules for {principal} on {resource_pattern}: "
                                f"permissions {overlap} are both allowed and denied"
                            )

        return conflicts
