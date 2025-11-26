"""
Threat Management Implementations

Threat detection, scanning, and security tools implementations.
"""

import builtins
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ThreatDetector:
    """Basic threat detection service."""

    def __init__(self):
        """Initialize threat detector."""
        self.threat_patterns = {
            "sql_injection": [
                r"(?i)(union\s+select)",
                r"(?i)(select.*from.*where)",
                r"(?i)(\'\s*or\s*\'\s*=\s*\')",
                r"(?i)(drop\s+table)",
                r"(?i)(insert\s+into)",
                r"(?i)(delete\s+from)",
            ],
            "xss": [
                r"(?i)(<script[^>]*>)",
                r"(?i)(javascript:)",
                r"(?i)(on\w+\s*=)",
                r"(?i)(<iframe[^>]*>)",
                r"(?i)(eval\s*\()",
                r"(?i)(document\.cookie)",
            ],
            "path_traversal": [
                r"(\.\.\/)",
                r"(\.\.\\)",
                r"(%2e%2e%2f)",
                r"(%2e%2e%5c)",
                r"(\.\./.*etc/passwd)",
                r"(\.\./.*windows/system32)",
            ],
            "command_injection": [
                r"(?i)(\|\s*cat\s)",
                r"(?i)(\|\s*ls\s)",
                r"(?i)(\|\s*dir\s)",
                r"(?i)(\|\s*rm\s)",
                r"(?i)(\|\s*del\s)",
                r"(?i)(;\s*cat\s)",
                r"(?i)(&&\s*cat\s)",
            ],
            "ldap_injection": [
                r"(\*\)\(.*=)",
                r"(\)\(\|.*=)",
                r"(\)\(&.*=)",
                r"(\*\)\(.*\|)",
                r"(\*\)\(.*&)",
            ],
        }

    def scan_request(self, request_data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """
        Scan a request for threats.

        Args:
            request_data: Dictionary containing request data to scan

        Returns:
            Dictionary with scan results
        """
        threats_found = []

        # Scan all string values in the request
        for key, value in request_data.items():
            if isinstance(value, str):
                threats = self._scan_string(value)
                if threats:
                    threats_found.extend(
                        [
                            {
                                "field": key,
                                "threat_type": threat_type,
                                "pattern": pattern,
                                "value": value[:100],  # Truncate for logging
                            }
                            for threat_type, pattern in threats
                        ]
                    )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "threats_found": threats_found,
            "threat_count": len(threats_found),
            "risk_level": self._calculate_risk_level(threats_found),
        }

    def _scan_string(self, text: str) -> builtins.list[tuple[str, str]]:
        """
        Scan a string for threat patterns.

        Args:
            text: String to scan

        Returns:
            List of (threat_type, pattern) tuples for matches found
        """
        threats = []

        for threat_type, patterns in self.threat_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    threats.append((threat_type, pattern))

        return threats

    def _calculate_risk_level(self, threats: builtins.list[builtins.dict[str, Any]]) -> str:
        """Calculate risk level based on threats found."""
        if not threats:
            return "low"

        high_risk_threats = ["sql_injection", "command_injection", "path_traversal"]

        for threat in threats:
            if threat["threat_type"] in high_risk_threats:
                return "high"

        if len(threats) > 3:
            return "medium"

        return "low"


class VulnerabilityScanner:
    """Basic vulnerability scanner."""

    def __init__(self):
        """Initialize vulnerability scanner."""
        self.vulnerability_checks = {
            "weak_passwords": self._check_weak_passwords,
            "insecure_protocols": self._check_insecure_protocols,
            "missing_encryption": self._check_missing_encryption,
            "default_credentials": self._check_default_credentials,
            "outdated_dependencies": self._check_outdated_dependencies,
        }

    def scan_configuration(self, config: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """
        Scan configuration for vulnerabilities.

        Args:
            config: Configuration dictionary to scan

        Returns:
            Dictionary with scan results
        """
        vulnerabilities = []

        for check_name, check_func in self.vulnerability_checks.items():
            try:
                result = check_func(config)
                if result:
                    vulnerabilities.extend(result)
            except Exception as e:
                logger.warning("Failed to run vulnerability check %s: %s", check_name, e)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "severity_summary": self._summarize_severity(vulnerabilities),
        }

    def _check_weak_passwords(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check for weak password configurations."""
        vulnerabilities = []

        # Check password policy settings
        password_policy = config.get("password_policy", {})

        min_length = password_policy.get("min_length", 0)
        if min_length < 8:
            vulnerabilities.append(
                {
                    "type": "weak_passwords",
                    "severity": "medium",
                    "description": f"Minimum password length is {min_length}, should be at least 8",
                    "recommendation": "Set minimum password length to at least 8 characters",
                }
            )

        require_special = password_policy.get("require_special_chars", False)
        if not require_special:
            vulnerabilities.append(
                {
                    "type": "weak_passwords",
                    "severity": "low",
                    "description": "Password policy does not require special characters",
                    "recommendation": "Require special characters in passwords",
                }
            )

        return vulnerabilities

    def _check_insecure_protocols(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check for insecure protocol configurations."""
        vulnerabilities = []

        # Check SSL/TLS configuration
        ssl_config = config.get("ssl", {})

        min_tls_version = ssl_config.get("min_tls_version", "1.0")
        if min_tls_version in ["1.0", "1.1"]:
            vulnerabilities.append(
                {
                    "type": "insecure_protocols",
                    "severity": "high",
                    "description": f"Minimum TLS version is {min_tls_version}, should be 1.2 or higher",
                    "recommendation": "Set minimum TLS version to 1.2 or 1.3",
                }
            )

        # Check for HTTP without HTTPS redirect
        http_config = config.get("http", {})
        force_https = http_config.get("force_https", False)
        if not force_https:
            vulnerabilities.append(
                {
                    "type": "insecure_protocols",
                    "severity": "medium",
                    "description": "HTTP traffic is not redirected to HTTPS",
                    "recommendation": "Enable HTTPS redirect for all HTTP traffic",
                }
            )

        return vulnerabilities

    def _check_missing_encryption(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check for missing encryption configurations."""
        vulnerabilities = []

        # Check database encryption
        database_config = config.get("database", {})
        encryption_enabled = database_config.get("encryption_at_rest", False)
        if not encryption_enabled:
            vulnerabilities.append(
                {
                    "type": "missing_encryption",
                    "severity": "high",
                    "description": "Database encryption at rest is not enabled",
                    "recommendation": "Enable database encryption at rest",
                }
            )

        # Check session encryption
        session_config = config.get("session", {})
        secure_cookies = session_config.get("secure_cookies", False)
        if not secure_cookies:
            vulnerabilities.append(
                {
                    "type": "missing_encryption",
                    "severity": "medium",
                    "description": "Session cookies are not marked as secure",
                    "recommendation": "Enable secure flag for session cookies",
                }
            )

        return vulnerabilities

    def _check_default_credentials(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check for default credentials."""
        vulnerabilities = []

        default_credentials = [
            ("admin", "admin"),
            ("admin", "password"),
            ("root", "root"),
            ("user", "user"),
            ("guest", "guest"),
            ("test", "test"),
        ]

        # Check various configuration sections for default credentials
        for section_name, section_config in config.items():
            if isinstance(section_config, dict):
                username = section_config.get("username", "")
                password = section_config.get("password", "")

                for default_user, default_pass in default_credentials:
                    if username == default_user and password == default_pass:
                        vulnerabilities.append(
                            {
                                "type": "default_credentials",
                                "severity": "critical",
                                "description": f"Default credentials found in {section_name} section",
                                "recommendation": "Change default credentials immediately",
                            }
                        )

        return vulnerabilities

    def _check_outdated_dependencies(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check for outdated dependencies (placeholder implementation)."""
        vulnerabilities = []

        # This would integrate with actual dependency checking tools
        dependencies = config.get("dependencies", {})

        # Placeholder check - in real implementation, this would check against
        # vulnerability databases and version information
        if "flask" in dependencies:
            version = dependencies["flask"]
            if version and version < "2.0.0":
                vulnerabilities.append(
                    {
                        "type": "outdated_dependencies",
                        "severity": "medium",
                        "description": f"Flask version {version} may have known vulnerabilities",
                        "recommendation": "Update Flask to the latest stable version",
                    }
                )

        return vulnerabilities

    def _summarize_severity(
        self, vulnerabilities: builtins.list[builtins.dict[str, Any]]
    ) -> builtins.dict[str, int]:
        """Summarize vulnerabilities by severity."""
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for vuln in vulnerabilities:
            severity = vuln.get("severity", "low")
            if severity in summary:
                summary[severity] += 1

        return summary


class SecurityScanner:
    """Comprehensive security scanner combining multiple detection methods."""

    def __init__(self):
        """Initialize security scanner."""
        self.threat_detector = ThreatDetector()
        self.vulnerability_scanner = VulnerabilityScanner()

    def comprehensive_scan(self, target: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """
        Perform comprehensive security scan.

        Args:
            target: Target data to scan (configuration, request data, etc.)

        Returns:
            Dictionary with comprehensive scan results
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scan_type": "comprehensive",
            "target_type": target.get("type", "unknown"),
        }

        # Perform threat detection on request data
        request_data = target.get("request_data", {})
        if request_data:
            threat_results = self.threat_detector.scan_request(request_data)
            results["threat_detection"] = threat_results

        # Perform vulnerability scanning on configuration
        config_data = target.get("configuration", {})
        if config_data:
            vuln_results = self.vulnerability_scanner.scan_configuration(config_data)
            results["vulnerability_scan"] = vuln_results

        # Calculate overall risk score
        results["overall_risk"] = self._calculate_overall_risk(results)

        return results

    def _calculate_overall_risk(
        self, scan_results: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Calculate overall risk score from scan results."""
        risk_score = 0
        risk_factors = []

        # Factor in threat detection results
        threat_results = scan_results.get("threat_detection", {})
        threat_count = threat_results.get("threat_count", 0)
        threat_risk = threat_results.get("risk_level", "low")

        if threat_risk == "high":
            risk_score += 40
            risk_factors.append("High-risk threats detected")
        elif threat_risk == "medium":
            risk_score += 20
            risk_factors.append("Medium-risk threats detected")
        elif threat_count > 0:
            risk_score += 10
            risk_factors.append("Low-risk threats detected")

        # Factor in vulnerability scan results
        vuln_results = scan_results.get("vulnerability_scan", {})
        severity_summary = vuln_results.get("severity_summary", {})

        risk_score += severity_summary.get("critical", 0) * 25
        risk_score += severity_summary.get("high", 0) * 15
        risk_score += severity_summary.get("medium", 0) * 8
        risk_score += severity_summary.get("low", 0) * 3

        if severity_summary.get("critical", 0) > 0:
            risk_factors.append("Critical vulnerabilities found")
        if severity_summary.get("high", 0) > 0:
            risk_factors.append("High severity vulnerabilities found")

        # Determine overall risk level
        if risk_score >= 50:
            risk_level = "critical"
        elif risk_score >= 30:
            risk_level = "high"
        elif risk_score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "score": min(100, risk_score),
            "level": risk_level,
            "factors": risk_factors,
            "recommendation": self._get_risk_recommendation(risk_level),
        }

    def _get_risk_recommendation(self, risk_level: str) -> str:
        """Get recommendation based on risk level."""
        recommendations = {
            "critical": "Immediate action required. Address critical vulnerabilities and threats before proceeding.",
            "high": "High priority remediation needed. Address security issues as soon as possible.",
            "medium": "Moderate security concerns. Plan remediation in next maintenance window.",
            "low": "Minor security issues identified. Address during regular maintenance cycles.",
        }

        return recommendations.get(
            risk_level, "Review security scan results and take appropriate action."
        )
