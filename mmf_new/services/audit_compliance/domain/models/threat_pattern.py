"""Threat pattern domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from mmf_new.core.domain import (
    Entity,
    SecurityEventType,
    SecurityThreatLevel,
)


@dataclass
class ThreatIndicator:
    """A single threat indicator within a pattern."""

    indicator_type: str  # "ip", "user_agent", "endpoint", "time_pattern", etc.
    value: str
    weight: float  # 0.0 to 1.0 - importance of this indicator
    description: str = ""


@dataclass
class ThreatPattern(Entity):
    """Domain entity representing a security threat pattern."""

    pattern_name: str
    pattern_type: str  # "brute_force", "anomalous_access", "privilege_escalation", etc.
    threat_level: SecurityThreatLevel
    confidence_threshold: float  # 0.0 to 1.0 - threshold for pattern match
    indicators: list[ThreatIndicator] = field(default_factory=list)
    associated_event_types: list[SecurityEventType] = field(default_factory=list)
    time_window_minutes: int = 60  # Time window for pattern detection
    minimum_events: int = 3  # Minimum events needed to trigger pattern
    description: str = ""
    remediation_steps: list[str] = field(default_factory=list)
    is_active: bool = True
    created_by: str | None = None
    last_triggered: datetime | None = None
    trigger_count: int = 0
    false_positive_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure entity is properly initialized."""
        if not hasattr(self, "id") or not self.id:
            super().__init__()

    def to_dict(self) -> dict[str, Any]:
        """Convert threat pattern to dictionary."""
        base_dict = super().to_dict()
        pattern_dict = {
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "threat_level": self.threat_level.value,
            "confidence_threshold": self.confidence_threshold,
            "indicators": [
                {
                    "indicator_type": i.indicator_type,
                    "value": i.value,
                    "weight": i.weight,
                    "description": i.description,
                }
                for i in self.indicators
            ],
            "associated_event_types": [et.value for et in self.associated_event_types],
            "time_window_minutes": self.time_window_minutes,
            "minimum_events": self.minimum_events,
            "description": self.description,
            "remediation_steps": self.remediation_steps,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count,
            "false_positive_count": self.false_positive_count,
            "metadata": self.metadata,
        }

        return {**base_dict, **pattern_dict}

    def add_indicator(
        self,
        indicator_type: str,
        value: str,
        weight: float,
        description: str = "",
    ) -> None:
        """Add a threat indicator to the pattern."""
        indicator = ThreatIndicator(
            indicator_type=indicator_type,
            value=value,
            weight=weight,
            description=description,
        )
        self.indicators.append(indicator)
        self.mark_updated()

    def add_event_type(self, event_type: SecurityEventType) -> None:
        """Add an associated security event type."""
        if event_type not in self.associated_event_types:
            self.associated_event_types.append(event_type)
            self.mark_updated()

    def record_trigger(self) -> None:
        """Record that this pattern was triggered."""
        self.last_triggered = datetime.now(timezone.utc)
        self.trigger_count += 1
        self.mark_updated()

    def record_false_positive(self) -> None:
        """Record a false positive detection."""
        self.false_positive_count += 1
        self.mark_updated()

    def get_accuracy_rate(self) -> float:
        """Calculate the accuracy rate of this pattern."""
        total_triggers = self.trigger_count + self.false_positive_count
        if total_triggers == 0:
            return 1.0  # No data yet, assume perfect

        return self.trigger_count / total_triggers

    def is_high_confidence(self) -> bool:
        """Check if this pattern has high confidence based on accuracy."""
        return self.get_accuracy_rate() >= 0.8

    def deactivate(self, reason: str = "") -> None:
        """Deactivate the threat pattern."""
        self.is_active = False
        if reason:
            self.metadata["deactivation_reason"] = reason
        self.mark_updated()

    def activate(self) -> None:
        """Activate the threat pattern."""
        self.is_active = True
        if "deactivation_reason" in self.metadata:
            del self.metadata["deactivation_reason"]
        self.mark_updated()
