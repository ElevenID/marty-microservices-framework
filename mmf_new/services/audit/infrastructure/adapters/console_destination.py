"""Console destination adapter for audit logging."""

import json
import logging
from datetime import datetime

try:
    from colorama import Fore, Style, init

    COLORAMA_AVAILABLE = True
    init(autoreset=True)
except ImportError:
    COLORAMA_AVAILABLE = False

    # Fallback no-op classes if colorama not available
    class Fore:  # noqa: N801
        RED = ""
        YELLOW = ""
        GREEN = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""

    class Style:  # noqa: N801
        RESET_ALL = ""


from mmf_new.core.domain.audit_types import AuditSeverity
from mmf_new.services.audit.domain.contracts import IAuditDestination
from mmf_new.services.audit.domain.entities import RequestAuditEvent

logger = logging.getLogger(__name__)


class ConsoleAuditDestination(IAuditDestination):
    """Console destination adapter for development and debugging."""

    def __init__(
        self,
        use_colors: bool = True,
        format_style: str = "pretty",  # pretty or json
        detail_level: str = "full",  # full, compact, minimal
    ):
        """Initialize console destination.

        Args:
            use_colors: Whether to use colored output
            format_style: Output format (pretty or json)
            detail_level: Level of detail (full, compact, minimal)
        """
        self.use_colors = use_colors and COLORAMA_AVAILABLE
        self.format_style = format_style
        self.detail_level = detail_level

    async def write_event(self, event: RequestAuditEvent) -> None:
        """Write a single audit event to console.

        Args:
            event: The audit event to write
        """
        if self.format_style == "json":
            output = json.dumps(event.to_dict(), indent=2, default=str)
            print(output)
        else:
            output = self._format_pretty(event)
            print(output)

    async def write_batch(self, events: list[RequestAuditEvent]) -> None:
        """Write a batch of audit events to console.

        Args:
            events: List of audit events to write
        """
        for event in events:
            await self.write_event(event)
            print("-" * 80)

    async def flush(self) -> None:
        """Flush any buffered events (no-op for console)."""
        pass

    async def close(self) -> None:
        """Close the destination (no-op for console)."""
        pass

    async def health_check(self) -> bool:
        """Check if the destination is healthy.

        Returns:
            True (console is always available)
        """
        return True

    def _format_pretty(self, event: RequestAuditEvent) -> str:
        """Format event as pretty text.

        Args:
            event: The audit event

        Returns:
            Formatted string
        """
        severity_color = self._get_severity_color(event.severity)
        reset = Style.RESET_ALL if self.use_colors else ""

        lines = []

        # Header
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        header = f"{severity_color}[{event.severity.value.upper()}]{reset} {timestamp}"
        lines.append(header)

        # Event type and ID
        lines.append(f"Event: {event.event_type.value} (ID: {event.id})")

        # Message
        if event.message:
            lines.append(f"Message: {event.message}")

        # Request context
        if event.request_context and self.detail_level in ("full", "compact"):
            lines.append(
                f"Request: {event.request_context.method} {event.request_context.endpoint}"
            )
            if event.request_context.source_ip:
                lines.append(f"Source IP: {event.request_context.source_ip}")

        # Actor info
        if event.actor_info and self.detail_level in ("full", "compact"):
            if event.actor_info.user_id:
                lines.append(f"User: {event.actor_info.username or event.actor_info.user_id}")

        # Performance
        if event.performance_metrics and self.detail_level == "full":
            lines.append(f"Duration: {event.performance_metrics.duration_ms:.2f}ms")

        # Response
        if event.response_metadata:
            status_color = self._get_status_color(event.response_metadata.status_code)
            lines.append(f"Status: {status_color}{event.response_metadata.status_code}{reset}")

        # Details (only in full mode)
        if event.details and self.detail_level == "full":
            lines.append("Details:")
            for key, value in event.details.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _get_severity_color(self, severity: AuditSeverity) -> str:
        """Get color for severity level.

        Args:
            severity: Severity level

        Returns:
            Color code or empty string
        """
        if not self.use_colors:
            return ""

        return {
            AuditSeverity.INFO: Fore.GREEN,
            AuditSeverity.LOW: Fore.CYAN,
            AuditSeverity.MEDIUM: Fore.YELLOW,
            AuditSeverity.HIGH: Fore.MAGENTA,
            AuditSeverity.CRITICAL: Fore.RED,
        }.get(severity, Fore.WHITE)

    def _get_status_color(self, status_code: int) -> str:
        """Get color for HTTP status code.

        Args:
            status_code: HTTP status code

        Returns:
            Color code or empty string
        """
        if not self.use_colors:
            return ""

        if 200 <= status_code < 300:
            return Fore.GREEN
        elif 300 <= status_code < 400:
            return Fore.CYAN
        elif 400 <= status_code < 500:
            return Fore.YELLOW
        else:
            return Fore.RED
