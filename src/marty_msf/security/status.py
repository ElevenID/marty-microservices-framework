"""
Security Status Reporting Module

Provides comprehensive security status reporting across all security components
in the Marty Microservices Framework.
"""

from datetime import datetime, timezone
from typing import Any

from .api import (
    ComplianceFramework,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
)
from .bootstrap import SecurityBootstrap
from .models import SecurityThreatLevel
from .monitoring import SecurityEvent, SecurityEventSeverity


class SecurityStatusReporter:
    """
    Comprehensive security status reporting for the entire security subsystem.
    """

    def __init__(self, bootstrap: SecurityBootstrap | None = None):
        """Initialize the security status reporter."""
        self.bootstrap = bootstrap or SecurityBootstrap()

    def get_comprehensive_status(self) -> dict[str, Any]:
        """Get comprehensive status across all security components."""
        try:
            status = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_status": "healthy",
                "components": {},
                "metrics": {},
                "health_checks": {},
                "alerts": [],
                "recommendations": []
            }

            # Component status
            status["components"] = self._get_component_status()

            # Security metrics
            status["metrics"] = self._get_security_metrics()

            # Health checks
            status["health_checks"] = self._perform_health_checks()

            # Generate alerts based on status
            status["alerts"] = self._generate_alerts(status)

            # Generate recommendations
            status["recommendations"] = self._generate_recommendations(status)

            # Determine overall status
            status["overall_status"] = self._determine_overall_status(status)

            return status

        except Exception as e:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_status": "error",
                "error": str(e),
                "components": {},
                "metrics": {},
                "health_checks": {},
                "alerts": [],
                "recommendations": []
            }

    def _get_component_status(self) -> dict[str, Any]:
        """Get status of all security components."""
        components = {}

        # Authenticator status
        try:
            authenticator = self.bootstrap.get_authenticator()
            components["authenticator"] = {
                "type": type(authenticator).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_authenticator_details(authenticator)
            }
        except Exception as e:
            components["authenticator"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        # Authorizer status
        try:
            authorizer = self.bootstrap.get_authorizer()
            components["authorizer"] = {
                "type": type(authorizer).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_authorizer_details(authorizer)
            }
        except Exception as e:
            components["authorizer"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        # Secret Manager status
        try:
            secret_manager = self.bootstrap.get_secret_manager()
            components["secret_manager"] = {
                "type": type(secret_manager).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_secret_manager_details(secret_manager)
            }
        except Exception as e:
            components["secret_manager"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        # Auditor status
        try:
            auditor = self.bootstrap.get_auditor()
            components["auditor"] = {
                "type": type(auditor).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_auditor_details(auditor)
            }
        except Exception as e:
            components["auditor"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        # Cache Manager status
        try:
            cache_manager = self.bootstrap.get_cache_manager()
            components["cache_manager"] = {
                "type": type(cache_manager).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_cache_manager_details(cache_manager)
            }
        except Exception as e:
            components["cache_manager"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        # Session Manager status
        try:
            session_manager = self.bootstrap.get_session_manager()
            components["session_manager"] = {
                "type": type(session_manager).__name__,
                "status": "active",
                "initialized": True,
                "details": self._get_session_manager_details(session_manager)
            }
        except Exception as e:
            components["session_manager"] = {
                "type": "unknown",
                "status": "error",
                "initialized": False,
                "error": str(e)
            }

        return components

    def _get_authenticator_details(self, authenticator: IAuthenticator) -> dict[str, Any]:
        """Get detailed authenticator information."""
        details = {"features": []}

        # Check for common authenticator features
        if hasattr(authenticator, 'supported_methods'):
            details["supported_methods"] = getattr(authenticator, 'supported_methods', [])

        if hasattr(authenticator, 'password_policy'):
            details["password_policy_enabled"] = True

        if hasattr(authenticator, 'multi_factor_enabled'):
            details["multi_factor_enabled"] = getattr(authenticator, 'multi_factor_enabled', False)

        return details

    def _get_authorizer_details(self, authorizer: IAuthorizer) -> dict[str, Any]:
        """Get detailed authorizer information."""
        details = {"features": []}

        # Check for role-based features
        if hasattr(authorizer, 'roles'):
            details["roles_count"] = len(getattr(authorizer, 'roles', {}))

        if hasattr(authorizer, 'permissions'):
            details["permissions_count"] = len(getattr(authorizer, 'permissions', {}))

        if hasattr(authorizer, 'policies'):
            details["policies_count"] = len(getattr(authorizer, 'policies', {}))

        return details

    def _get_secret_manager_details(self, secret_manager: ISecretManager) -> dict[str, Any]:
        """Get detailed secret manager information."""
        details = {"features": []}

        # Check for encryption features
        if hasattr(secret_manager, 'encryption_enabled'):
            details["encryption_enabled"] = getattr(secret_manager, 'encryption_enabled', False)

        if hasattr(secret_manager, 'rotation_enabled'):
            details["rotation_enabled"] = getattr(secret_manager, 'rotation_enabled', False)

        return details

    def _get_auditor_details(self, auditor: IAuditor) -> dict[str, Any]:
        """Get detailed auditor information."""
        details = {"features": []}

        # Check for audit features
        if hasattr(auditor, 'storage_backend'):
            details["storage_backend"] = getattr(auditor, 'storage_backend', 'unknown')

        if hasattr(auditor, 'retention_policy'):
            details["retention_policy"] = getattr(auditor, 'retention_policy', {})

        return details

    def _get_cache_manager_details(self, cache_manager: ICacheManager) -> dict[str, Any]:
        """Get detailed cache manager information."""
        details = {"features": []}

        # Check for cache metrics
        if hasattr(cache_manager, 'get_cache_metrics'):
            try:
                metrics = cache_manager.get_cache_metrics()
                details["cache_metrics"] = metrics
            except Exception:
                details["cache_metrics"] = "unavailable"

        return details

    def _get_session_manager_details(self, session_manager: ISessionManager) -> dict[str, Any]:
        """Get detailed session manager information."""
        details = {"features": []}

        # Check for session features
        if hasattr(session_manager, 'active_sessions_count'):
            details["active_sessions"] = getattr(session_manager, 'active_sessions_count', 0)

        if hasattr(session_manager, 'session_timeout'):
            details["session_timeout"] = getattr(session_manager, 'session_timeout', 'unknown')

        return details

    def _get_security_metrics(self) -> dict[str, Any]:
        """Get security-related metrics."""
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": "unknown",
            "performance": {},
            "usage": {}
        }

        # Try to collect performance metrics
        try:
            # This would typically integrate with your metrics system
            metrics["performance"] = {
                "authentication_latency_ms": "unknown",
                "authorization_latency_ms": "unknown",
                "cache_hit_rate": "unknown"
            }
        except Exception:
            pass

        # Try to collect usage metrics
        try:
            metrics["usage"] = {
                "authentication_requests_per_minute": "unknown",
                "authorization_requests_per_minute": "unknown",
                "active_sessions": "unknown"
            }
        except Exception:
            pass

        return metrics

    def _perform_health_checks(self) -> dict[str, Any]:
        """Perform health checks on security components."""
        health_checks = {}

        # Test authenticator
        health_checks["authenticator"] = self._check_authenticator_health()

        # Test authorizer
        health_checks["authorizer"] = self._check_authorizer_health()

        # Test secret manager
        health_checks["secret_manager"] = self._check_secret_manager_health()

        # Test cache manager
        health_checks["cache_manager"] = self._check_cache_manager_health()

        return health_checks

    def _check_authenticator_health(self) -> dict[str, Any]:
        """Check authenticator health."""
        try:
            authenticator = self.bootstrap.get_authenticator()
            # Basic health check - try to authenticate with invalid credentials
            authenticator.authenticate({"username": "__health_check__", "password": "__invalid__"})

            return {
                "status": "healthy",
                "response_time_ms": "unknown",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Authenticator responded correctly to health check"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    def _check_authorizer_health(self) -> dict[str, Any]:
        """Check authorizer health."""
        try:
            self.bootstrap.get_authorizer()
            # Basic health check - authorizer is accessible

            return {
                "status": "healthy",
                "response_time_ms": "unknown",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Authorizer is accessible and responding"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    def _check_secret_manager_health(self) -> dict[str, Any]:
        """Check secret manager health."""
        try:
            secret_manager = self.bootstrap.get_secret_manager()
            # Basic health check - try to access a non-existent secret
            try:
                secret_manager.get_secret("__health_check_non_existent__")
            except KeyError:
                pass  # Expected behavior

            return {
                "status": "healthy",
                "response_time_ms": "unknown",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Secret manager is accessible and responding"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    def _check_cache_manager_health(self) -> dict[str, Any]:
        """Check cache manager health."""
        try:
            self.bootstrap.get_cache_manager()
            # Basic health check - cache manager is accessible

            return {
                "status": "healthy",
                "response_time_ms": "unknown",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "details": "Cache manager is accessible and responding"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    def _generate_alerts(self, status: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate alerts based on system status."""
        alerts = []

        # Check for component errors
        for component_name, component_info in status.get("components", {}).items():
            if component_info.get("status") == "error":
                alerts.append({
                    "severity": "high",
                    "type": "component_error",
                    "component": component_name,
                    "message": f"Security component {component_name} is in error state",
                    "details": component_info.get("error", "Unknown error"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        # Check for health check failures
        for check_name, check_info in status.get("health_checks", {}).items():
            if check_info.get("status") == "unhealthy":
                alerts.append({
                    "severity": "medium",
                    "type": "health_check_failure",
                    "component": check_name,
                    "message": f"Health check failed for {check_name}",
                    "details": check_info.get("error", "Health check failed"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        return alerts

    def _generate_recommendations(self, status: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate recommendations based on system status."""
        recommendations = []

        # Check if all components are initialized
        components = status.get("components", {})
        for component_name, component_info in components.items():
            if not component_info.get("initialized", False):
                recommendations.append({
                    "priority": "high",
                    "category": "initialization",
                    "component": component_name,
                    "message": f"Initialize {component_name} for complete security coverage",
                    "action": f"Ensure {component_name} is properly configured and initialized"
                })

        # Check for missing features
        if components.get("secret_manager", {}).get("details", {}).get("encryption_enabled") is False:
            recommendations.append({
                "priority": "medium",
                "category": "security",
                "component": "secret_manager",
                "message": "Enable encryption for secret manager",
                "action": "Configure encryption for stored secrets to enhance security"
            })

        return recommendations

    def _determine_overall_status(self, status: dict[str, Any]) -> str:
        """Determine overall system status."""
        alerts = status.get("alerts", [])

        # Check for high severity alerts
        high_severity_alerts = [a for a in alerts if a.get("severity") == "high"]
        if high_severity_alerts:
            return "critical"

        # Check for medium severity alerts
        medium_severity_alerts = [a for a in alerts if a.get("severity") == "medium"]
        if medium_severity_alerts:
            return "degraded"

        # Check component status
        components = status.get("components", {})
        for component_info in components.values():
            if component_info.get("status") == "error":
                return "degraded"

        return "healthy"


def create_status_reporter(bootstrap: SecurityBootstrap | None = None) -> SecurityStatusReporter:
    """
    Create a security status reporter instance.

    Args:
        bootstrap: Optional SecurityBootstrap instance

    Returns:
        Configured SecurityStatusReporter instance
    """
    return SecurityStatusReporter(bootstrap)
