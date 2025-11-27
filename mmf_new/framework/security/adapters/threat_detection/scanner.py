"""
Vulnerability Scanner Adapter

Vulnerability scanner adapter implementing IVulnerabilityScanner.
"""

import builtins
import re
import uuid
from collections import defaultdict, deque
from typing import Any

from mmf_new.core.domain.audit_types import SecurityThreatLevel
from mmf_new.core.security.domain.models.vulnerability import SecurityVulnerability
from mmf_new.core.security.ports.threat_detection import IVulnerabilityScanner


class VulnerabilityScanner(IVulnerabilityScanner):
    """Security vulnerability scanner."""

    def __init__(self, service_name: str):
        """Initialize security scanner."""
        self.service_name = service_name
        self.vulnerabilities: builtins.list[SecurityVulnerability] = []

        # Scanning patterns and rules
        self.vulnerability_patterns = self._load_vulnerability_patterns()

        # Scan history
        self.scan_history: deque = deque(maxlen=100)

    def _load_vulnerability_patterns(
        self,
    ) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Load vulnerability detection patterns."""
        return {
            "sql_injection": {
                "pattern": r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)\b|--\s)",
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential SQL injection vulnerability",
            },
            "xss": {
                "pattern": r"(<script|javascript:|on\w+\s*=)",
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Potential Cross-Site Scripting (XSS) vulnerability",
            },
            "path_traversal": {
                "pattern": r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)",
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential path traversal vulnerability",
            },
            "hardcoded_secret": {
                "pattern": r'(password|secret|key|token)\s*[:=]\s*["\'][\w\d]+["\']',
                "severity": SecurityThreatLevel.CRITICAL,
                "description": "Hardcoded secret detected",
            },
        }

    def scan_code(self, code: str, file_path: str = "") -> builtins.list[SecurityVulnerability]:
        """Scan code for security vulnerabilities."""
        vulnerabilities = []

        for vuln_type, pattern_info in self.vulnerability_patterns.items():
            pattern = pattern_info["pattern"]
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                line_number = code.count("\n", 0, match.start()) + 1

                vulnerability = SecurityVulnerability(
                    vulnerability_id=str(uuid.uuid4()),
                    title=f"{vuln_type.replace('_', ' ').title()} in {file_path or 'code'}",
                    description=pattern_info["description"],
                    severity=pattern_info["severity"],
                    affected_component=f"{file_path}:{line_number}"
                    if file_path
                    else f"line:{line_number}",
                    remediation=self._get_remediation_advice(vuln_type),
                )

                vulnerabilities.append(vulnerability)
                self.vulnerabilities.append(vulnerability)

        return vulnerabilities

    def scan_configuration(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan configuration for security issues."""
        vulnerabilities = []

        # Check for insecure configurations
        insecure_configs = {
            "debug": {
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Debug mode enabled in production",
            },
            "ssl_verify": {
                "severity": SecurityThreatLevel.HIGH,
                "description": "SSL verification disabled",
            },
            "allow_origins": {
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Permissive CORS configuration",
            },
        }

        def check_config_recursively(cfg, path=""):
            for key, value in cfg.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, dict):
                    check_config_recursively(value, current_path)
                else:
                    # Check for insecure values
                    if key in insecure_configs:
                        config_info = insecure_configs[key]

                        if (
                            (key == "debug" and value is True)
                            or (key == "ssl_verify" and value is False)
                            or (key == "allow_origins" and value == "*")
                        ):
                            vulnerability = SecurityVulnerability(
                                vulnerability_id=str(uuid.uuid4()),
                                title=f"Insecure Configuration: {current_path}",
                                description=config_info["description"],
                                severity=config_info["severity"],
                                affected_component=current_path,
                                remediation=f"Review and secure configuration for {key}",
                            )

                            vulnerabilities.append(vulnerability)
                            self.vulnerabilities.append(vulnerability)

        check_config_recursively(config)
        return vulnerabilities

    def scan_dependencies(
        self, dependencies: builtins.list[builtins.dict[str, Any]]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan dependencies for known vulnerabilities."""
        vulnerabilities = []

        # Simplified vulnerability database
        known_vulns = {
            "requests": {
                "versions": ["< 2.20.0"],
                "cve": "CVE-2018-18074",
                "description": "HTTP request smuggling vulnerability",
                "severity": SecurityThreatLevel.HIGH,
            },
            "urllib3": {
                "versions": ["< 1.24.2"],
                "cve": "CVE-2019-11324",
                "description": "Certificate verification bypass",
                "severity": SecurityThreatLevel.MEDIUM,
            },
        }

        for dep in dependencies:
            package_name = dep.get("name", "")
            version = dep.get("version", "")

            if package_name in known_vulns:
                vuln_info = known_vulns[package_name]

                # Simplified version checking
                if any(version.startswith(v.replace("< ", "")) for v in vuln_info["versions"]):
                    vulnerability = SecurityVulnerability(
                        vulnerability_id=str(uuid.uuid4()),
                        title=f"Vulnerable Dependency: {package_name}",
                        description=vuln_info["description"],
                        severity=vuln_info["severity"],
                        cve_id=vuln_info["cve"],
                        affected_component=f"{package_name}@{version}",
                        remediation=f"Update {package_name} to latest version",
                    )

                    vulnerabilities.append(vulnerability)
                    self.vulnerabilities.append(vulnerability)

        return vulnerabilities

    def get_vulnerability_summary(self) -> builtins.dict[str, Any]:
        """Get vulnerability scan summary."""
        by_severity = defaultdict(int)
        by_component = defaultdict(int)

        for vuln in self.vulnerabilities:
            by_severity[vuln.severity.value] += 1
            by_component[vuln.affected_component] += 1

        return {
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": dict(by_severity),
            "by_component": dict(by_component),
            "open_vulnerabilities": len([v for v in self.vulnerabilities if v.status == "open"]),
            "fixed_vulnerabilities": len([v for v in self.vulnerabilities if v.status == "fixed"]),
        }

    def _get_remediation_advice(self, vulnerability_type: str) -> str:
        """Get remediation advice for vulnerability type."""
        remediation_map = {
            "sql_injection": "Use parameterized queries and input validation",
            "xss": "Implement proper input sanitization and output encoding",
            "path_traversal": "Validate and sanitize file paths, use allowlists",
            "hardcoded_secret": "Move secrets to secure configuration or vault",
        }

        return remediation_map.get(vulnerability_type, "Review and fix security issue")
