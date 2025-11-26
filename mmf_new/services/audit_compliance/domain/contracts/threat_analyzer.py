"""Threat analyzer contract."""

from datetime import datetime
from typing import Any, Protocol

from ..models import ThreatPattern


class IThreatAnalyzer(Protocol):
    """Interface for threat analysis operations."""

    async def get_pattern(self, pattern_id: str) -> ThreatPattern | None:
        """Get a specific threat pattern."""
        ...

    async def get_patterns(
        self,
        resource: str | None,
        start_time: datetime,
        end_time: datetime,
        include_recent_only: bool = False,
    ) -> list[ThreatPattern]:
        """Get threat patterns matching criteria."""
        ...

    async def analyze_pattern(
        self,
        pattern: ThreatPattern,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Analyze a specific threat pattern."""
        ...
