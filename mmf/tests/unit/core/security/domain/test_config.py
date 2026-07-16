import pytest

from mmf.core.security.domain.config import (
    APIKeyConfig,
    JWTConfig,
    MTLSConfig,
    RateLimitConfig,
    SecretProviderType,
    SecurityConfig,
    SecurityLevel,
    ServiceMeshConfig,
    SessionConfig,
    ThreatDetectionConfig,
    VaultAuthMethod,
    VaultConfig,
)


class TestSecurityConfigEnums:
    def test_security_level_values(self):
        assert SecurityLevel.LOW.value == "low"
        assert SecurityLevel.MEDIUM.value == "medium"
        assert SecurityLevel.HIGH.value == "high"
        assert SecurityLevel.CRITICAL.value == "critical"

    def test_secret_provider_type_values(self):
        assert SecretProviderType.ENVIRONMENT.value == "environment"
        assert SecretProviderType.VAULT.value == "vault"
        assert SecretProviderType.KUBERNETES.value == "kubernetes"
        assert SecretProviderType.FILE.value == "file"

    def test_vault_auth_method_values(self):
        assert VaultAuthMethod.TOKEN.value == "token"
        assert VaultAuthMethod.AWS_IAM.value == "aws"
        assert VaultAuthMethod.KUBERNETES.value == "kubernetes"
        assert VaultAuthMethod.USERPASS.value == "userpass"
        assert VaultAuthMethod.APPROLE.value == "approle"


class TestSecurityConfigDataclasses:
    def test_vault_config_defaults(self):
        config = VaultConfig()
        assert config.url == "http://localhost:8200"
        assert config.auth_method == VaultAuthMethod.TOKEN
        assert config.verify_ssl is True

    def test_jwt_config_validation(self):
        # Test missing secret key
        with pytest.raises(ValueError, match="JWT secret key is required"):
            JWTConfig(secret_key="")

        # Test valid config
        config = JWTConfig(secret_key="secret")
        assert config.algorithm == "HS256"

    def test_mtls_config_validation(self):
        # Test missing CA cert when verification enabled
        with pytest.raises(ValueError, match="CA certificate path required"):
            MTLSConfig(verify_client_cert=True, ca_cert_path=None)

        # Test valid config
        config = MTLSConfig(verify_client_cert=True, ca_cert_path="/path/to/ca.pem")
        assert config.verify_client_cert is True

    def test_api_key_config_defaults(self):
        config = APIKeyConfig()
        assert config.header_name == "X-API-Key"
        assert config.allow_header is True
        assert config.allow_query_param is False

    def test_rate_limit_config_defaults(self):
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.default_rate == "100/minute"
        assert config.istio_safety_multiplier == 2.0

    def test_session_config_defaults(self):
        config = SessionConfig()
        assert config.enabled is True
        assert config.default_timeout_minutes == 30
        assert config.secure_cookies is True

    def test_service_mesh_config_defaults(self):
        config = ServiceMeshConfig()
        assert config.enabled is False
        assert config.mesh_type == "istio"
        assert config.mtls_mode == "STRICT"

    def test_threat_detection_config_defaults(self):
        config = ThreatDetectionConfig()
        assert config.enabled is True
        assert config.anomaly_threshold == 0.7
        assert config.sql_injection_detection is True

    def test_security_config_defaults(self):
        config = SecurityConfig()
        assert config.security_level == SecurityLevel.MEDIUM
        assert config.secret_provider_type == SecretProviderType.ENVIRONMENT
        assert config.enable_audit_logging is True

        # Check default headers
        assert "X-Content-Type-Options" in config.security_headers
        assert config.security_headers["X-Frame-Options"] == "DENY"
