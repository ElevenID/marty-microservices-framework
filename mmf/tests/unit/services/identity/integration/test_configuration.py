import pytest

from mmf.services.identity.infrastructure.adapters import JWTConfig
from mmf.services.identity.integration.configuration import (
    JWTAuthConfig,
    create_development_config,
    create_production_config,
    load_config_from_env,
)


class TestJWTAuthConfig:
    def test_init_success(self):
        config = JWTAuthConfig(secret_key="test-secret")  # pragma: allowlist secret
        assert config.secret_key == "test-secret"
        assert config.algorithm == "HS256"
        assert config.issuer == "marty-microservices"
        assert config.audience == "marty-services"
        assert config.expires_delta_minutes == 30
        assert "/health" in config.excluded_paths

    def test_init_missing_secret(self):
        with pytest.raises(ValueError, match="JWT secret_key is required"):
            JWTAuthConfig(secret_key="")

    def test_init_invalid_expiry(self):
        with pytest.raises(ValueError, match="expires_delta_minutes must be positive"):
            JWTAuthConfig(secret_key="test-secret", expires_delta_minutes=0)

    def test_to_jwt_config(self):
        config = JWTAuthConfig(secret_key="test-secret")  # pragma: allowlist secret
        jwt_config = config.to_jwt_config()
        assert isinstance(jwt_config, JWTConfig)
        assert jwt_config.secret_key == "test-secret"
        assert jwt_config.algorithm == "HS256"
        assert jwt_config.issuer == "marty-microservices"
        assert jwt_config.audience == "marty-services"
        assert jwt_config.access_token_expire_minutes == 30


class TestFactoryFunctions:
    def test_create_development_config(self):
        config = create_development_config(secret_key="dev-secret")  # pragma: allowlist secret
        assert config.secret_key == "dev-secret"
        assert config.verify_signature is True

    def test_create_development_config_default_secret(self):
        config = create_development_config()
        assert (
            config.secret_key == "dev-secret-key-change-in-production"
        )  # pragma: allowlist secret

    def test_create_production_config(self):
        config = create_production_config(secret_key="prod-secret")  # pragma: allowlist secret
        assert config.secret_key == "prod-secret"
        assert config.verify_signature is True

    def test_create_production_config_missing_secret(self):
        with pytest.raises(ValueError, match="Production secret_key is required"):
            create_production_config(secret_key="")

    def test_load_config_from_env(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "env-secret")
        monkeypatch.setenv("JWT_ALGORITHM", "RS256")
        monkeypatch.setenv("JWT_ISSUER", "env-issuer")
        monkeypatch.setenv("JWT_AUDIENCE", "env-audience")
        monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")

        config = load_config_from_env()
        assert config.secret_key == "env-secret"
        assert config.algorithm == "RS256"
        assert config.issuer == "env-issuer"
        assert config.audience == "env-audience"
        assert config.expires_delta_minutes == 60
