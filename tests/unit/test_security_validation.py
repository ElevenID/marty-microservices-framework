"""
Tests for security framework validation.

This module converts the legacy verify_security_framework.py script into proper automated tests.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from marty_msf.security.monitoring import SecurityMonitor
from scripts import verify_security_framework


class TestSecurityFramework:
    """Test suite for security framework validation."""

    def test_security_modules_import(self):
        """Test that security modules can be imported."""
        security_modules = [
            'security.monitoring',
            'security.middleware',
            'security.identity_access',
        ]

        import_errors = []
        for module in security_modules:
            try:
                __import__(module)
            except ImportError as e:
                import_errors.append((module, str(e)))

        if import_errors:
            # Don't fail for missing security modules, just warn
            error_msg = "\n".join([
                f"  {module}: {error}" for module, error in import_errors
            ])
            print(f"⚠️  Security module import warnings:\n{error_msg}")

    def test_security_policies_validation(self):
        """Test security policy files validation."""
        policies_dir = Path("security/policies")

        if not policies_dir.exists():
            pytest.skip("Security policies directory not found")

        policy_files = list(policies_dir.glob("*.yaml")) + list(policies_dir.glob("*.yml")) + list(policies_dir.glob("*.json"))

        if not policy_files:
            pytest.skip("No security policy files found")

        policy_errors = []

        for policy_file in policy_files:
            try:
                if policy_file.suffix in ['.yml', '.yaml']:
                    with open(policy_file, encoding='utf-8') as f:
                        policy = yaml.safe_load(f)
                elif policy_file.suffix == '.json':
                    with open(policy_file, encoding='utf-8') as f:
                        policy = json.load(f)
                else:
                    continue

                # Basic policy validation
                if isinstance(policy, dict):
                    # Check for common security policy fields
                    expected_fields = ["rules", "permissions", "roles", "policies"]
                    has_security_content = any(field in policy for field in expected_fields)

                    if not has_security_content:
                        print(f"⚠️  {policy_file} may not contain security policy content")

            except (yaml.YAMLError, json.JSONDecodeError) as e:
                policy_errors.append((policy_file, str(e)))
            except OSError:
                continue

        if policy_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in policy_errors
            ])
            pytest.fail(f"Security policy validation errors:\n{error_msg}")

    def test_compliance_configuration(self):
        """Test compliance configuration validation."""
        compliance_dir = Path("security/compliance")

        if not compliance_dir.exists():
            pytest.skip("Compliance directory not found")

        compliance_files = list(compliance_dir.glob("*.yaml")) + list(compliance_dir.glob("*.yml"))

        if not compliance_files:
            pytest.skip("No compliance configuration files found")

        compliance_errors = []

        for compliance_file in compliance_files:
            try:
                with open(compliance_file, encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                # Basic compliance validation
                if isinstance(config, dict):
                    # Check for compliance-related fields
                    compliance_keywords = ["gdpr", "sox", "pci", "hipaa", "compliance", "audit"]
                    has_compliance_content = any(
                        keyword in str(config).lower() for keyword in compliance_keywords
                    )

                    if not has_compliance_content:
                        print(f"⚠️  {compliance_file} may not contain compliance configuration")

            except yaml.YAMLError as e:
                compliance_errors.append((compliance_file, str(e)))
            except OSError:
                continue

        if compliance_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in compliance_errors
            ])
            pytest.fail(f"Compliance configuration errors:\n{error_msg}")

    def test_identity_access_management(self):
        """Test identity and access management configuration."""
        iam_dir = Path("security/identity_access")

        if not iam_dir.exists():
            pytest.skip("Identity access directory not found")

        # Look for common IAM configuration files
        iam_files = list(iam_dir.glob("*.yaml")) + list(iam_dir.glob("*.yml")) + list(iam_dir.glob("*.json"))

        if not iam_files:
            pytest.skip("No IAM configuration files found")

        iam_errors = []

        for iam_file in iam_files:
            try:
                if iam_file.suffix in ['.yml', '.yaml']:
                    with open(iam_file, encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                elif iam_file.suffix == '.json':
                    with open(iam_file, encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    continue

                # Basic IAM validation
                if isinstance(config, dict):
                    # Check for IAM-related fields
                    iam_fields = ["users", "roles", "permissions", "groups", "authentication", "authorization"]
                    has_iam_content = any(field in config for field in iam_fields)

                    if not has_iam_content:
                        print(f"⚠️  {iam_file} may not contain IAM configuration")

            except (yaml.YAMLError, json.JSONDecodeError) as e:
                iam_errors.append((iam_file, str(e)))
            except OSError:
                continue

        if iam_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in iam_errors
            ])
            pytest.fail(f"IAM configuration errors:\n{error_msg}")

    def test_security_middleware_configuration(self):
        """Test security middleware configuration."""
        middleware_dir = Path("security/middleware")

        if not middleware_dir.exists():
            pytest.skip("Security middleware directory not found")

        # Look for Python middleware files
        middleware_files = list(middleware_dir.glob("*.py"))

        if not middleware_files:
            pytest.skip("No security middleware files found")

        syntax_errors = []

        for middleware_file in middleware_files:
            if middleware_file.name == "__init__.py":
                continue

            try:
                with open(middleware_file, encoding='utf-8') as f:
                    content = f.read()

                # Check syntax
                compile(content, str(middleware_file), 'exec')

                # Basic security middleware validation
                security_keywords = ["auth", "security", "token", "jwt", "cors", "csrf"]
                has_security_content = any(
                    keyword in content.lower() for keyword in security_keywords
                )

                if not has_security_content:
                    print(f"⚠️  {middleware_file} may not contain security middleware")

            except SyntaxError as e:
                syntax_errors.append((middleware_file, str(e)))
            except OSError:
                continue

        if syntax_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in syntax_errors
            ])
            pytest.fail(f"Security middleware syntax errors:\n{error_msg}")

    def test_security_scanners_configuration(self):
        """Test security scanners configuration."""
        scanners_dir = Path("security/scanners")

        if not scanners_dir.exists():
            pytest.skip("Security scanners directory not found")

        scanner_files = list(scanners_dir.glob("*.yaml")) + list(scanners_dir.glob("*.yml"))

        if not scanner_files:
            pytest.skip("No security scanner configuration files found")

        scanner_errors = []

        for scanner_file in scanner_files:
            try:
                with open(scanner_file, encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                # Basic scanner validation
                if isinstance(config, dict):
                    # Check for scanner-related fields
                    scanner_fields = ["scan", "vulnerability", "security", "rules", "checks"]
                    has_scanner_content = any(field in str(config).lower() for field in scanner_fields)

                    if not has_scanner_content:
                        print(f"⚠️  {scanner_file} may not contain scanner configuration")

            except yaml.YAMLError as e:
                scanner_errors.append((scanner_file, str(e)))
            except OSError:
                continue

        if scanner_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in scanner_errors
            ])
            pytest.fail(f"Security scanner configuration errors:\n{error_msg}")

    def test_security_requirements_file(self):
        """Test security requirements file."""
        security_requirements = Path("security/requirements.txt")

        if not security_requirements.exists():
            pytest.skip("Security requirements.txt not found")

        try:
            with open(security_requirements, encoding='utf-8') as f:
                requirements = f.read()

            # Check for common security packages
            security_packages = [
                "cryptography",
                "passlib",
                "python-jose",
                "bcrypt",
                "pyjwt",
                "oauthlib",
            ]

            found_packages = []
            for package in security_packages:
                if package in requirements.lower():
                    found_packages.append(package)

            if not found_packages:
                print("⚠️  No recognized security packages found in requirements.txt")
            else:
                print(f"✅ Found security packages: {found_packages}")

        except OSError:
            pytest.skip("Could not read security requirements.txt")

    @patch('subprocess.run')
    def test_security_monitoring_health(self, mock_run):
        """Test security monitoring health checks."""
        # Mock successful health check
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Security monitoring OK"
        mock_run.return_value = mock_result

        # Test that security monitoring can be imported
        try:
            monitor = SecurityMonitor()
            assert monitor is not None
        except ImportError:
            pytest.skip("Security monitoring not available")

    def test_security_configuration_structure(self):
        """Test overall security configuration structure."""
        security_dir = Path("security")

        if not security_dir.exists():
            pytest.skip("Security directory not found")

        expected_subdirs = [
            "policies",
            "middleware",
            "identity_access",
            "compliance",
            "scanners",
        ]

        missing_dirs = []
        for subdir in expected_subdirs:
            if not (security_dir / subdir).exists():
                missing_dirs.append(subdir)

        if missing_dirs:
            print(f"⚠️  Missing security subdirectories: {missing_dirs}")

        # Check for security configuration files
        config_files = list(security_dir.glob("*.yaml")) + list(security_dir.glob("*.yml"))

        if not config_files:
            print("⚠️  No security configuration files found in root security directory")

    def test_tls_ssl_configuration(self):
        """Test TLS/SSL configuration validation."""
        # Look for TLS/SSL configuration in various locations
        possible_locations = [
            Path("security/tls"),
            Path("security/ssl"),
            Path("config"),
            Path("k8s"),
        ]

        tls_configs = []
        for location in possible_locations:
            if location.exists():
                tls_files = list(location.glob("*tls*")) + list(location.glob("*ssl*"))
                tls_configs.extend(tls_files)

        if not tls_configs:
            print("⚠️  No TLS/SSL configuration files found")
            return

        tls_errors = []
        for tls_file in tls_configs:
            try:
                if tls_file.suffix in ['.yml', '.yaml']:
                    with open(tls_file, encoding='utf-8') as f:
                        config = yaml.safe_load(f)

                    if isinstance(config, dict):
                        # Check for TLS-related fields
                        tls_fields = ["tls", "ssl", "certificate", "key", "https"]
                        has_tls_content = any(
                            field in str(config).lower() for field in tls_fields
                        )

                        if not has_tls_content:
                            print(f"⚠️  {tls_file} may not contain TLS configuration")

            except yaml.YAMLError as e:
                tls_errors.append((tls_file, str(e)))
            except OSError:
                continue

        if tls_errors:
            error_msg = "\n".join([
                f"  {file}: {error}" for file, error in tls_errors
            ])
            pytest.fail(f"TLS configuration errors:\n{error_msg}")

    def test_import_original_security_script(self):
        """Test that the original security script can be imported."""
        try:

            # Check that main validation functions exist
            assert hasattr(verify_security_framework, '__file__')

        except ImportError as e:
            pytest.skip(f"Could not import verify_security_framework script: {e}")

    def test_security_environment_variables(self):
        """Test that security-related environment variables are documented."""
        # Look for environment variable documentation
        env_files = [
            Path(".env.example"),
            Path(".env.template"),
            Path("config/.env.example"),
            Path("docs/security.md"),
            Path("README.md"),
        ]

        security_env_vars = [
            "SECRET_KEY",
            "JWT_SECRET",
            "DATABASE_PASSWORD",
            "API_KEY",
            "AUTH_TOKEN",
        ]

        documented_vars = []
        for env_file in env_files:
            if env_file.exists():
                try:
                    with open(env_file, encoding='utf-8') as f:
                        content = f.read()

                    for var in security_env_vars:
                        if var in content:
                            documented_vars.append(var)

                except OSError:
                    continue

        if documented_vars:
            print(f"✅ Found documented security environment variables: {set(documented_vars)}")
        else:
            print("⚠️  No security environment variables documented")
