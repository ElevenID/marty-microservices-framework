"""
Security Event Models

This module defines event models for security operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditEvent:
    """Security audit event."""

    event_type: str
    principal_id: str | None
    resource: str | None
    action: str | None
    result: str  # success, failure, error
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str | None = None
