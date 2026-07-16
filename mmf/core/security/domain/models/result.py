"""
Security Result Models

This module defines result models for security operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .user import AuthenticatedUser


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""

    success: bool
    user: AuthenticatedUser | None = None
    error: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationResult:
    """Result of an authorization decision."""

    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityDecision:
    """Result of a security policy evaluation."""

    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    required_attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0
    cache_key: str | None = None


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""

    decision: bool
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time: float = 0.0


@dataclass
class ComplianceResult:
    """Result of a compliance scan."""

    framework: str
    passed: bool
    score: float
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
