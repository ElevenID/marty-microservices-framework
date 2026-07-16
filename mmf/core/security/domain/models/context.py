"""
Security Context Models

This module defines context models for security operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .user import SecurityPrincipal, User


@dataclass
class AuthorizationContext:
    """Context for authorization decisions."""

    user: User
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SecurityContext:
    """Context for security decisions."""

    principal: SecurityPrincipal
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
