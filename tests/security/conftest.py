"""
Security Test Configuration

This module provides pytest configuration and fixtures for security testing.
Security tests include authentication, authorization, vulnerability scanning, and penetration testing.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest


class SecurityTestLevel(Enum):
    """Security test severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityVulnerability:
    """Container for security vulnerability information."""
    name: str
    description: str
    severity: SecurityTestLevel
    cve_id: str | None = None
    mitigation: str | None = None


@pytest.fixture
def security_test_credentials():
    """Provides test credentials for security testing."""
    return {
        'valid_user': {
            'username': 'security_test_user',
            'password': 'SecureTestPass123!'
        },
        'admin_user': {
            'username': 'admin',
            'password': 'admin123'
        },
        'weak_passwords': [
            'password',
            '123456',
            'admin',
            '',
            ' ',
            'a' * 100,  # Too long
        ],
        'sql_injection_attempts': [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin' --",
            "' UNION SELECT * FROM users --"
        ],
        'xss_payloads': [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//"
        ]
    }


@pytest.fixture
def jwt_test_tokens():
    """Provides JWT tokens for security testing."""
    import jwt

    secret = "test_secret_key"

    valid_payload = {
        'user_id': 'test_user',
        'exp': 9999999999,  # Far future
        'iat': 1000000000   # Past
    }

    expired_payload = {
        'user_id': 'test_user',
        'exp': 1000000000,  # Past
        'iat': 1000000000
    }

    return {
        'valid_token': jwt.encode(valid_payload, secret, algorithm='HS256'),
        'expired_token': jwt.encode(expired_payload, secret, algorithm='HS256'),
        'invalid_signature': jwt.encode(valid_payload, "wrong_secret", algorithm='HS256'),
        'malformed_token': 'not.a.jwt.token',
        'empty_token': '',
        'none_algorithm': jwt.encode(valid_payload, '', algorithm='none')
    }


@pytest.fixture
def rate_limiting_config():
    """Configuration for rate limiting security tests."""
    return {
        'max_requests_per_minute': 60,
        'max_requests_per_hour': 1000,
        'blocked_duration': 300,  # 5 minutes
        'test_endpoints': [
            '/authenticate',
            '/users',
            '/health'
        ]
    }


@pytest.fixture
def penetration_test_vectors():
    """Common penetration testing attack vectors."""
    return {
        'path_traversal': [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '....//....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'
        ],
        'command_injection': [
            '; cat /etc/passwd',
            '| whoami',
            '&& ls -la',
            '`cat /etc/passwd`',
            '$(cat /etc/passwd)'
        ],
        'ldap_injection': [
            '*)(uid=*',
            '*)(|(uid=*))',
            '*)(&(uid=*))',
            '*)(!(&(uid=*)))'
        ],
        'nosql_injection': [
            '{"$ne": ""}',
            '{"$gt": ""}',
            '{"$regex": ".*"}',
            '{"$where": "this.username == this.password"}'
        ]
    }


@pytest.fixture
def vulnerability_scanner():
    """Provides vulnerability scanning capabilities."""

    def scan_headers(response) -> list[SecurityVulnerability]:
        """Scan HTTP response headers for security issues."""
        vulnerabilities = []
        headers = response.headers

        # Check for security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000',
            'Content-Security-Policy': None  # Should be present
        }

        for header, expected in security_headers.items():
            if header not in headers:
                vulnerabilities.append(SecurityVulnerability(
                    name=f"Missing {header} header",
                    description=f"Response lacks {header} security header",
                    severity=SecurityTestLevel.MEDIUM
                ))

        # Check for information disclosure
        if 'Server' in headers:
            vulnerabilities.append(SecurityVulnerability(
                name="Server header disclosure",
                description="Server header reveals server information",
                severity=SecurityTestLevel.LOW,
                mitigation="Remove or obfuscate Server header"
            ))

        return vulnerabilities

    def scan_authentication(auth_response) -> list[SecurityVulnerability]:
        """Scan authentication response for security issues."""
        vulnerabilities = []

        # Check for timing attacks
        if hasattr(auth_response, 'elapsed'):
            if auth_response.elapsed.total_seconds() < 0.1:
                vulnerabilities.append(SecurityVulnerability(
                    name="Potential timing attack vulnerability",
                    description="Authentication response time too fast, may allow timing attacks",
                    severity=SecurityTestLevel.MEDIUM,
                    mitigation="Implement constant-time comparison"
                ))

        return vulnerabilities

    return {
        'scan_headers': scan_headers,
        'scan_authentication': scan_authentication
    }


@pytest.fixture
def crypto_test_utils():
    """Cryptographic utilities for security testing."""

    def generate_weak_hash(password: str) -> str:
        """Generate a weak hash for testing purposes."""
        return hashlib.md5(password.encode()).hexdigest()

    def generate_strong_hash(password: str) -> str:
        """Generate a strong hash for comparison."""
        salt = secrets.token_bytes(32)
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return base64.b64encode(salt + key).decode()

    def check_password_strength(password: str) -> dict[str, Any]:
        """Check password strength and return recommendations."""
        checks = {
            'length': len(password) >= 8,
            'uppercase': any(c.isupper() for c in password),
            'lowercase': any(c.islower() for c in password),
            'digit': any(c.isdigit() for c in password),
            'special': any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password),
            'not_common': password.lower() not in ['password', '123456', 'admin']
        }

        score = sum(checks.values())
        strength = 'weak' if score < 4 else 'medium' if score < 6 else 'strong'

        return {
            'score': score,
            'strength': strength,
            'checks': checks,
            'recommendations': [
                key for key, passed in checks.items() if not passed
            ]
        }

    return {
        'weak_hash': generate_weak_hash,
        'strong_hash': generate_strong_hash,
        'check_password_strength': check_password_strength
    }


# Security test markers
pytest.mark.security = pytest.mark.security
pytest.mark.authentication = pytest.mark.authentication
pytest.mark.authorization = pytest.mark.authorization
pytest.mark.vulnerability = pytest.mark.vulnerability
pytest.mark.penetration = pytest.mark.penetration
pytest.mark.crypto = pytest.mark.crypto
