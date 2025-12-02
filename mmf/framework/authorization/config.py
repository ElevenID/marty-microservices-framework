"""
Authorization Configuration

Configuration dataclasses and enums for authorization system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthorizationConfig:
    """Main authorization configuration."""

    # Cache settings
    cache_ttl: int = 300  # 5 minutes
    cache_enabled: bool = True

    # RBAC settings
    rbac_enabled: bool = True
    default_roles: list[str] = field(default_factory=list)

    # ABAC settings
    abac_enabled: bool = False
    policy_file_path: str | None = None

    # Policy engine settings
    policy_engine: str = "builtin"  # "builtin", "opa", "oso", "acl"
    opa_url: str | None = None
    opa_policy_path: str | None = None

    # General settings
    strict_mode: bool = True  # Deny by default
    audit_enabled: bool = True
    metrics_enabled: bool = True

    # Custom configuration
    custom: dict[str, Any] = field(default_factory=dict)


def get_default_config() -> AuthorizationConfig:
    """
    Get default authorization configuration.

    Returns:
        Default AuthorizationConfig instance
    """
    return AuthorizationConfig(
        cache_ttl=300,
        cache_enabled=True,
        rbac_enabled=True,
        abac_enabled=False,
        policy_engine="builtin",
        strict_mode=True,
        audit_enabled=True,
        metrics_enabled=True,
    )
