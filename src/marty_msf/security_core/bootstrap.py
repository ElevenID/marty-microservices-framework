"""
Security Hardening Framework

Modern security framework integration layer that coordinates multiple security components
while respecting the level contract architecture.
"""

import uuid
import warnings
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .api import (
    AuthorizationContext,
    ComplianceFramework,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
    SecurityDecision,
    SecurityPrincipal,
    User,
)
from .models import SecurityThreatLevel
from .monitoring import SecurityEvent, SecurityEventSeverity, SecurityEventType


class SecurityHardeningFramework:
    """
    Modern security hardening framework that integrates all security components
    while maintaining separation of concerns through the level contract architecture.
    """

    def __init__(self, service_name: str, config: dict[str, Any] | None = None):
        """Initialize security hardening framework."""
        self.service_name = service_name
        self.config = config or {}

        # Initialize bootstrap system (placeholder)
        # TODO: Implement bootstrap system initialization
        # self.bootstrap = SecurityBootstrap(self.config)

        # Lazy-loaded security components
        self._authenticator: IAuthenticator | None = None
        self._authorizer: IAuthorizer | None = None
        self._secret_manager: ISecretManager | None = None
        self._auditor: IAuditor | None = None
        self._cache_manager: ICacheManager | None = None
        self._session_manager: ISessionManager | None = None

        # Security monitoring
        self.security_events: deque = deque(maxlen=10000)
        self.threat_detection_enabled = True

        # Compliance tracking
        self.compliance_standards: set[ComplianceFramework] = set()
        self.compliance_status: dict[str, bool] = {}

        # Metrics tracking
        self.metrics = {
            "authentication_attempts": 0,
            "authorization_checks": 0,
            "security_events": 0,
            "compliance_scans": 0,
            "threats_detected": 0,
        }

    @property
    def authenticator(self) -> IAuthenticator:
        """Get the authenticator instance."""
        if self._authenticator is None:
            self._authenticator = self.bootstrap.get_authenticator()
        return self._authenticator

    @property
    def authorizer(self) -> IAuthorizer:
        """Get the authorizer instance."""
        if self._authorizer is None:
            self._authorizer = self.bootstrap.get_authorizer()
        return self._authorizer

    @property
    def secret_manager(self) -> ISecretManager:
        """Get the secret manager instance."""
        if self._secret_manager is None:
            self._secret_manager = self.bootstrap.get_secret_manager()
        return self._secret_manager

    @property
    def auditor(self) -> IAuditor:
        """Get the auditor instance."""
        if self._auditor is None:
            self._auditor = self.bootstrap.get_auditor()
        return self._auditor

    @property
    def cache_manager(self) -> ICacheManager:
        """Get the cache manager instance."""
        if self._cache_manager is None:
            self._cache_manager = self.bootstrap.get_cache_manager()
        return self._cache_manager

    @property
    def session_manager(self) -> ISessionManager:
        """Get the session manager instance."""
        if self._session_manager is None:
            self._session_manager = self.bootstrap.get_session_manager()
        return self._session_manager

    def initialize_security(self, config: dict[str, Any] | None = None) -> None:
        """Initialize security framework with configuration."""
        if config:
            self.config.update(config)

        # Initialize the bootstrap system (placeholder)
        # self.bootstrap = SecurityBootstrap(self.config)  # TODO: Implement

        # Set up compliance standards
        if "compliance_standards" in self.config:
            for standard in self.config["compliance_standards"]:
                try:
                    self.compliance_standards.add(ComplianceFramework(standard))
                except ValueError:
                    self._log_security_event(
                        event_type="configuration_error",
                        principal_id=None,
                        resource="compliance_config",
                        action="add_standard",
                        result="failure",
                        threat_level=SecurityThreatLevel.LOW,
                        details={"reason": f"Unknown compliance standard: {standard}"},
                    )

        # Initialize threat detection if configured
        self.threat_detection_enabled = self.config.get("threat_detection", {}).get("enabled", True)

    def authenticate_principal(
        self, credentials: dict[str, Any], provider: str | None = None
    ) -> SecurityPrincipal | None:
        """Authenticate a principal and create security context."""
        self.metrics["authentication_attempts"] += 1

        try:
            # Use the modular authenticator
            auth_result = self.authenticator.authenticate(credentials)

            if auth_result.success and auth_result.user:
                # Convert User to SecurityPrincipal
                principal = SecurityPrincipal(
                    id=auth_result.user.id,
                    type="user",
                    roles=set(auth_result.user.roles),
                    attributes=auth_result.user.attributes,
                    identity_provider=provider or "local",
                )

                # Create session
                session_id = self.session_manager.create_session(principal)
                principal.session_id = session_id

                # Log successful authentication
                self._log_security_event(
                    event_type="authentication",
                    principal_id=principal.id,
                    resource="auth_system",
                    action="authenticate",
                    result="success",
                    threat_level=SecurityThreatLevel.LOW,
                    details={"provider": provider or "local"},
                )

                return principal
            else:
                # Log failed authentication
                self._log_security_event(
                    event_type="authentication",
                    principal_id=credentials.get("username", "unknown"),
                    resource="auth_system",
                    action="authenticate",
                    result="failure",
                    threat_level=SecurityThreatLevel.MEDIUM,
                    details={
                        "reason": auth_result.error_message or "Authentication failed",
                        "provider": provider or "local",
                    },
                )
                return None

        except (ValueError, KeyError, AttributeError) as e:
            self._log_security_event(
                event_type="authentication",
                principal_id=credentials.get("username", "unknown"),
                resource="auth_system",
                action="authenticate",
                result="error",
                threat_level=SecurityThreatLevel.HIGH,
                details={"error": str(e)},
            )
            return None

    def authorize_action(
        self,
        principal: SecurityPrincipal,
        resource: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> SecurityDecision:
        """Authorize an action for a principal."""
        self.metrics["authorization_checks"] += 1

        try:
            # Convert SecurityPrincipal to User for authorization
            user = User(
                id=principal.id,
                username=principal.id,
                roles=list(principal.roles),
                attributes=principal.attributes,
            )

            # Create authorization context
            auth_context = AuthorizationContext(
                user=user, resource=resource, action=action, environment=context or {}
            )

            # Perform authorization
            auth_result = self.authorizer.authorize(auth_context)

            # Create security decision
            decision = SecurityDecision(
                allowed=auth_result.allowed,
                reason=auth_result.reason,
                policies_evaluated=auth_result.policies_evaluated,
                metadata=auth_result.metadata,
            )

            # Log authorization event
            self._log_security_event(
                event_type="authorization",
                principal_id=principal.id,
                resource=resource,
                action=action,
                result="success" if decision.allowed else "blocked",
                threat_level=SecurityThreatLevel.LOW
                if decision.allowed
                else SecurityThreatLevel.MEDIUM,
                details={
                    "reason": decision.reason,
                    "policies_evaluated": decision.policies_evaluated,
                },
            )

            return decision

        except (ValueError, KeyError, AttributeError) as e:
            # Log authorization error
            self._log_security_event(
                event_type="authorization",
                principal_id=principal.id,
                resource=resource,
                action=action,
                result="error",
                threat_level=SecurityThreatLevel.HIGH,
                details={"error": str(e)},
            )

            return SecurityDecision(
                allowed=False,
                reason=f"Authorization error: {str(e)}",
                policies_evaluated=[],
                metadata={"error": True},
            )

    def get_security_status(self) -> dict[str, Any]:
        """Get comprehensive security status across all components."""
        try:
            # Component status
            component_status = {
                "authenticator": {
                    "type": type(self.authenticator).__name__,
                    "initialized": self._authenticator is not None,
                },
                "authorizer": {
                    "type": type(self.authorizer).__name__,
                    "initialized": self._authorizer is not None,
                },
                "secret_manager": {
                    "type": type(self.secret_manager).__name__,
                    "initialized": self._secret_manager is not None,
                },
                "auditor": {
                    "type": type(self.auditor).__name__,
                    "initialized": self._auditor is not None,
                },
                "cache_manager": {
                    "type": type(self.cache_manager).__name__,
                    "initialized": self._cache_manager is not None,
                },
                "session_manager": {
                    "type": type(self.session_manager).__name__,
                    "initialized": self._session_manager is not None,
                },
            }

            # Security metrics
            security_metrics = self.metrics.copy()
            security_metrics["active_events"] = len(self.security_events)

            # Recent security events summary
            recent_events = list(self.security_events)[-10:]
            event_summary = {}
            for event in recent_events:
                event_type = event.event_type
                if event_type not in event_summary:
                    event_summary[event_type] = {"count": 0, "last_seen": None}
                event_summary[event_type]["count"] += 1
                if (
                    event_summary[event_type]["last_seen"] is None
                    or event.timestamp > event_summary[event_type]["last_seen"]
                ):
                    event_summary[event_type]["last_seen"] = event.timestamp

            # Compliance status
            compliance_info = {
                "standards": [s.value for s in self.compliance_standards],
                "status": self.compliance_status.copy(),
            }

            return {
                "service": self.service_name,
                "framework_status": "active",
                "components": component_status,
                "metrics": security_metrics,
                "recent_events_summary": event_summary,
                "compliance": compliance_info,
                "threat_detection_enabled": self.threat_detection_enabled,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except (ValueError, KeyError, AttributeError) as e:
            return {
                "service": self.service_name,
                "framework_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_security_events(
        self, event_type: str | None = None, limit: int = 100, since: datetime | None = None
    ) -> list[SecurityEvent]:
        """Get security events with optional filtering."""
        events = list(self.security_events)

        # Filter by event type
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Filter by timestamp
        if since:
            events = [e for e in events if e.timestamp >= since]

        # Apply limit
        return events[-limit:] if limit else events

    def clear_security_events(self, before: datetime | None = None) -> int:
        """Clear security events, optionally before a specific timestamp."""
        if before:
            original_count = len(self.security_events)
            self.security_events = deque(
                [e for e in self.security_events if e.timestamp >= before],
                maxlen=self.security_events.maxlen,
            )
            return original_count - len(self.security_events)
        else:
            count = len(self.security_events)
            self.security_events.clear()
            return count

    def scan_compliance(self, framework: ComplianceFramework) -> dict[str, Any]:
        """Perform compliance scan for a specific framework."""
        self.metrics["compliance_scans"] += 1

        # Basic compliance check based on current security configuration
        checks = {
            "authentication_enabled": self._authenticator is not None,
            "authorization_enabled": self._authorizer is not None,
            "secret_management_enabled": self._secret_manager is not None,
            "audit_logging_enabled": self._auditor is not None,
            "session_management_enabled": self._session_manager is not None,
            "threat_detection_enabled": self.threat_detection_enabled,
        }

        passed_checks = sum(checks.values())
        total_checks = len(checks)
        compliance_score = passed_checks / total_checks

        result = {
            "framework": framework.value,
            "score": compliance_score,
            "passed": compliance_score >= 0.8,  # 80% threshold
            "checks": checks,
            "summary": f"{passed_checks}/{total_checks} checks passed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Update compliance status
        self.compliance_status[framework.value] = result["passed"]

        # Log compliance scan
        self._log_security_event(
            event_type="compliance_scan",
            principal_id=None,
            resource="compliance_system",
            action="scan",
            result="completed",
            threat_level=SecurityThreatLevel.LOW,
            details={
                "framework": framework.value,
                "score": compliance_score,
                "passed": result["passed"],
            },
        )

        return result

    def _log_security_event(
        self,
        event_type: str,
        principal_id: str | None,
        resource: str,
        action: str,
        result: str,
        threat_level: SecurityThreatLevel,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log security event for audit and monitoring."""
        # Map threat level to severity
        severity_mapping = {
            SecurityThreatLevel.LOW: SecurityEventSeverity.LOW,
            SecurityThreatLevel.MEDIUM: SecurityEventSeverity.MEDIUM,
            SecurityThreatLevel.HIGH: SecurityEventSeverity.HIGH,
            SecurityThreatLevel.CRITICAL: SecurityEventSeverity.CRITICAL,
        }

        # Map event types
        event_type_mapping = {
            "authentication": SecurityEventType.AUTHENTICATION_SUCCESS
            if result == "success"
            else SecurityEventType.AUTHENTICATION_FAILURE,
            "authorization": SecurityEventType.AUTHORIZATION_FAILURE
            if result == "blocked"
            else SecurityEventType.POLICY_VIOLATION,
            "compliance_scan": SecurityEventType.CONFIGURATION_CHANGE,
            "configuration_error": SecurityEventType.CONFIGURATION_CHANGE,
        }

        mapped_event_type = event_type_mapping.get(event_type, SecurityEventType.SYSTEM_ANOMALY)

        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            event_type=mapped_event_type,
            severity=severity_mapping.get(threat_level, SecurityEventSeverity.MEDIUM),
            timestamp=datetime.now(timezone.utc),
            user_id=principal_id,
            resource=resource,
            action=action,
            raw_data={"result": result, "threat_level": threat_level.value, **(details or {})},
        )

        self.security_events.append(event)
        self.metrics["security_events"] += 1

        # Increment threat counter for medium/high threats
        if threat_level in (SecurityThreatLevel.MEDIUM, SecurityThreatLevel.HIGH):
            self.metrics["threats_detected"] += 1

        # Also log to auditor if available
        try:
            if self._auditor:
                self.auditor.audit_event(
                    event_type,
                    {
                        "event_id": event.event_id,
                        "principal_id": principal_id,
                        "resource": resource,
                        "action": action,
                        "result": result,
                        "threat_level": threat_level.value,
                        "details": details or {},
                        "service": self.service_name,
                    },
                )
        except (ValueError, KeyError, AttributeError):
            # Don't fail if audit logging fails
            pass


def create_security_framework(
    service_name: str, config: dict[str, Any] | None = None
) -> SecurityHardeningFramework:
    """
    Create security hardening framework instance.

    Args:
        service_name: Name of the service
        config: Optional security configuration

    Returns:
        Configured SecurityHardeningFramework instance
    """
    framework = SecurityHardeningFramework(service_name, config)
    framework.initialize_security(config)
    return framework
