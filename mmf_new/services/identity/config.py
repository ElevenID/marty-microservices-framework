"""
Authentication and Identity Service Configuration.

This module provides configuration management for the authentication system,
integrating with the MMF configuration patterns and supporting multiple
authentication providers and methods.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, dict, list

import yaml

from mmf_new.infrastructure.config_manager import BaseSettings, Environment


class AuthenticationProviderType(Enum):
    """Supported authentication provider types."""

    BASIC = "basic"
    API_KEY = "api_key"  # pragma: allowlist secret
    JWT = "jwt"
    OAUTH2 = "oauth2"
    SAML = "saml"
    MFA = "mfa"
    LDAP = "ldap"


class HashingAlgorithm(Enum):
    """Password hashing algorithms."""

    BCRYPT = "bcrypt"
    SCRYPT = "scrypt"
    ARGON2 = "argon2"


@dataclass
class BasicAuthConfig:
    """Configuration for basic (username/password) authentication."""

    # Password hashing
    password_hash_algorithm: HashingAlgorithm = HashingAlgorithm.BCRYPT
    password_hash_rounds: int = 12

    # Password policy
    password_min_length: int = 8
    password_max_length: int = 128
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special_chars: bool = True
    password_special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Account security
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    password_expiry_days: int = 90

    # Default users
    create_default_users: bool = True
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"  # Change in production!


@dataclass
class APIKeyConfig:
    """Configuration for API key authentication."""

    # Key generation
    key_length: int = 32  # bytes (will be hex encoded)
    key_prefix: str = "mmf_"

    # Key management
    default_expiry_days: int = 365
    max_keys_per_user: int = 10
    enable_key_rotation: bool = True
    rotation_warning_days: int = 30

    # Key validation
    rate_limit_requests_per_minute: int = 1000
    enable_usage_tracking: bool = True

    # Demo keys
    create_demo_keys: bool = True


@dataclass
class JWTConfig:
    """Configuration for JWT authentication."""

    # Token settings
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Token validation
    verify_signature: bool = True
    verify_exp: bool = True
    verify_iat: bool = True
    verify_nbf: bool = True

    # Token claims
    issuer: str = "mmf-identity-service"
    audience: str = "mmf-services"

    # Security
    allow_token_refresh: bool = True
    max_refresh_count: int = 3


@dataclass
class OAuth2Config:
    """Configuration for OAuth2 authentication."""

    # Provider settings
    provider_name: str = "oauth2"
    client_id: str = ""
    client_secret: str = ""

    # Endpoints
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    jwks_url: str = ""

    # Scopes and claims
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    user_id_claim: str = "sub"
    username_claim: str = "preferred_username"
    email_claim: str = "email"

    # Security
    pkce_enabled: bool = True
    state_validation: bool = True
    nonce_validation: bool = True


@dataclass
class SAMLConfig:
    """Configuration for SAML authentication."""

    # Identity Provider settings
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_x509_cert: str = ""

    # Service Provider settings
    sp_entity_id: str = "mmf-identity-service"
    sp_acs_url: str = ""
    sp_sls_url: str = ""

    # Assertion settings
    name_id_format: str = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
    attribute_mapping: dict[str, str] = field(
        default_factory=lambda: {
            "user_id": "uid",
            "username": "username",
            "email": "email",
            "first_name": "givenName",
            "last_name": "sn",
        }
    )

    # Security
    want_assertions_signed: bool = True
    want_response_signed: bool = True


@dataclass
class MFAConfig:
    """Configuration for Multi-Factor Authentication."""

    # TOTP settings
    totp_issuer: str = "MMF Identity Service"
    totp_algorithm: str = "SHA1"
    totp_digits: int = 6
    totp_period: int = 30
    totp_window: int = 1

    # SMS settings
    sms_provider: str = "twilio"  # twilio, aws_sns, azure_communication
    sms_from_number: str = ""
    sms_template: str = "Your MMF verification code is: {code}"

    # Email settings
    email_provider: str = "smtp"
    email_from_address: str = "noreply@mmf.local"
    email_template: str = "Your MMF verification code is: {code}"

    # Backup codes
    backup_codes_count: int = 10
    backup_code_length: int = 8

    # Security
    max_attempts: int = 3
    lockout_duration_minutes: int = 5
    require_mfa_for_admin: bool = True


@dataclass
class SessionConfig:
    """Configuration for session management."""

    # Session settings
    session_timeout_minutes: int = 60
    max_concurrent_sessions: int = 5
    enable_session_refresh: bool = True

    # Storage
    session_storage: str = "redis"  # redis, database, memory
    session_key_prefix: str = "mmf:session:"

    # Security
    secure_cookies: bool = True
    httponly_cookies: bool = True
    samesite_policy: str = "Strict"

    # Cleanup
    cleanup_interval_minutes: int = 30
    cleanup_batch_size: int = 1000


@dataclass
class SecurityConfig:
    """Security configuration for authentication."""

    # Rate limiting
    enable_rate_limiting: bool = True
    login_rate_limit: int = 5  # attempts per minute per IP
    api_rate_limit: int = 100  # requests per minute per user

    # IP restrictions
    allowed_ips: list[str] = field(default_factory=list)
    blocked_ips: list[str] = field(default_factory=list)

    # Audit logging
    enable_audit_logging: bool = True
    log_successful_logins: bool = True
    log_failed_logins: bool = True
    log_logout_events: bool = True

    # Security headers
    enable_security_headers: bool = True
    csrf_protection: bool = True

    # Encryption
    enable_at_rest_encryption: bool = False
    encryption_key: str = ""


@dataclass
class AuthenticationConfig:
    """Main authentication configuration."""

    # Service identification
    service_name: str = "mmf-identity-service"
    service_version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT

    # Enabled providers
    enabled_providers: list[AuthenticationProviderType] = field(
        default_factory=lambda: [
            AuthenticationProviderType.BASIC,
            AuthenticationProviderType.API_KEY,
            AuthenticationProviderType.JWT,
        ]
    )

    # Default authentication method
    default_provider: AuthenticationProviderType = AuthenticationProviderType.JWT

    # Provider configurations
    basic_auth: BasicAuthConfig = field(default_factory=BasicAuthConfig)
    api_key: APIKeyConfig = field(default_factory=APIKeyConfig)
    jwt: JWTConfig = field(default_factory=JWTConfig)
    oauth2: OAuth2Config = field(default_factory=OAuth2Config)
    saml: SAMLConfig = field(default_factory=SAMLConfig)
    mfa: MFAConfig = field(default_factory=MFAConfig)

    # Session and security
    session: SessionConfig = field(default_factory=SessionConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Integration settings
    enable_user_registration: bool = True
    enable_password_reset: bool = True
    enable_account_lockout: bool = True

    # Database settings
    user_table_name: str = "users"
    session_table_name: str = "user_sessions"
    api_key_table_name: str = "api_keys"
    audit_table_name: str = "audit_log"


class AuthenticationSettings(BaseSettings):
    """Pydantic-based authentication settings that integrate with MMF configuration."""

    # Service configuration
    service_name: str = "mmf-identity-service"
    environment: str = "development"
    debug: bool = False

    # Authentication providers
    auth_enabled_providers: list[str] = ["basic", "api_key", "jwt"]
    auth_default_provider: str = "jwt"

    # Basic Authentication
    auth_basic_password_min_length: int = 8
    auth_basic_hash_rounds: int = 12
    auth_basic_max_login_attempts: int = 5
    auth_basic_create_defaults: bool = True

    # API Key Authentication
    auth_apikey_length: int = 32
    auth_apikey_prefix: str = "mmf_"
    auth_apikey_default_expiry_days: int = 365
    auth_apikey_max_per_user: int = 10

    # JWT Authentication
    auth_jwt_secret_key: str = "your-secret-key-change-in-production"
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_access_token_expire_minutes: int = 15
    auth_jwt_refresh_token_expire_days: int = 7

    # OAuth2 Configuration
    auth_oauth2_client_id: str | None = None
    auth_oauth2_client_secret: str | None = None
    auth_oauth2_authorization_url: str | None = None
    auth_oauth2_token_url: str | None = None

    # Security
    auth_security_rate_limiting: bool = True
    auth_security_login_rate_limit: int = 5
    auth_security_audit_logging: bool = True
    auth_security_csrf_protection: bool = True

    # Session Management
    auth_session_timeout_minutes: int = 60
    auth_session_storage: str = "redis"
    auth_session_max_concurrent: int = 5

    class Config:
        """Pydantic configuration."""

        env_prefix = "MMF_"
        env_file = ".env"
        case_sensitive = False


def create_authentication_config(
    environment: Environment = Environment.DEVELOPMENT, **overrides: Any
) -> AuthenticationConfig:
    """
    Create authentication configuration for the specified environment.

    Args:
        environment: Target environment
        **overrides: Configuration overrides

    Returns:
        Configured AuthenticationConfig instance
    """
    # Environment-specific defaults
    env_defaults = {
        Environment.DEVELOPMENT: {
            "debug": True,
            "basic_auth.create_default_users": True,
            "api_key.create_demo_keys": True,
            "security.enable_rate_limiting": False,
            "jwt.access_token_expire_minutes": 60,  # Longer for dev
        },
        Environment.TESTING: {
            "debug": True,
            "basic_auth.create_default_users": False,
            "api_key.create_demo_keys": False,
            "security.enable_rate_limiting": False,
            "jwt.access_token_expire_minutes": 5,  # Short for tests
        },
        Environment.STAGING: {
            "debug": False,
            "basic_auth.create_default_users": False,
            "api_key.create_demo_keys": False,
            "security.enable_rate_limiting": True,
        },
        Environment.PRODUCTION: {
            "debug": False,
            "basic_auth.create_default_users": False,
            "api_key.create_demo_keys": False,
            "security.enable_rate_limiting": True,
            "security.enable_audit_logging": True,
            "jwt.verify_signature": True,
            "basic_auth.default_admin_password": os.getenv("ADMIN_PASSWORD", "CHANGE_ME"),
            "jwt.secret_key": os.getenv("JWT_SECRET_KEY", "CHANGE_ME"),
        },
    }

    # Start with base config
    config = AuthenticationConfig(environment=environment)

    # Apply environment-specific defaults
    env_config = env_defaults.get(environment, {})
    for key, value in env_config.items():
        if "." in key:
            # Handle nested configuration
            parts = key.split(".")
            obj = config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        else:
            setattr(config, key, value)

    # Apply overrides
    for key, value in overrides.items():
        if "." in key:
            # Handle nested configuration
            parts = key.split(".")
            obj = config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        else:
            setattr(config, key, value)

    return config


def get_authentication_settings() -> AuthenticationSettings:
    """Get authentication settings from environment variables."""
    return AuthenticationSettings()


# Configuration factory functions for different environments
def create_development_config(**overrides: Any) -> AuthenticationConfig:
    """Create development authentication configuration."""
    return create_authentication_config(Environment.DEVELOPMENT, **overrides)


def create_testing_config(**overrides: Any) -> AuthenticationConfig:
    """Create testing authentication configuration."""
    return create_authentication_config(Environment.TESTING, **overrides)


def create_staging_config(**overrides: Any) -> AuthenticationConfig:
    """Create staging authentication configuration."""
    return create_authentication_config(Environment.STAGING, **overrides)


def create_production_config(**overrides: Any) -> AuthenticationConfig:
    """Create production authentication configuration."""
    return create_authentication_config(Environment.PRODUCTION, **overrides)


def load_config_from_file(file_path: str | Path) -> AuthenticationConfig:
    """
    Load authentication configuration from a YAML or JSON file.

    Args:
        file_path: Path to configuration file

    Returns:
        Loaded AuthenticationConfig instance
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path) as f:
        if file_path.suffix.lower() in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    # Convert to environment enum
    if "environment" in data:
        data["environment"] = Environment(data["environment"])

    return AuthenticationConfig(**data)


def create_sample_config_file(
    file_path: str | Path = "auth_config.yaml", environment: Environment = Environment.DEVELOPMENT
) -> None:
    """
    Create a sample authentication configuration file.

    Args:
        file_path: Path for the configuration file
        environment: Target environment
    """

    config = create_authentication_config(environment)

    # Convert to dict for serialization
    config_dict = {
        "service_name": config.service_name,
        "service_version": config.service_version,
        "environment": config.environment.value,
        "enabled_providers": [p.value for p in config.enabled_providers],
        "default_provider": config.default_provider.value,
        "basic_auth": {
            "password_min_length": config.basic_auth.password_min_length,
            "password_hash_rounds": config.basic_auth.password_hash_rounds,
            "create_default_users": config.basic_auth.create_default_users,
        },
        "api_key": {
            "key_length": config.api_key.key_length,
            "key_prefix": config.api_key.key_prefix,
            "default_expiry_days": config.api_key.default_expiry_days,
        },
        "jwt": {
            "algorithm": config.jwt.algorithm,
            "access_token_expire_minutes": config.jwt.access_token_expire_minutes,
            "refresh_token_expire_days": config.jwt.refresh_token_expire_days,
        },
        "security": {
            "enable_rate_limiting": config.security.enable_rate_limiting,
            "enable_audit_logging": config.security.enable_audit_logging,
        },
    }

    with open(file_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    print(f"Sample configuration created: {file_path}")


if __name__ == "__main__":
    # Create sample configuration files
    environments = [
        Environment.DEVELOPMENT,
        Environment.TESTING,
        Environment.STAGING,
        Environment.PRODUCTION,
    ]

    for env in environments:
        create_sample_config_file(f"auth_config_{env.value}.yaml", env)

    # Display current configuration
    settings = get_authentication_settings()
    print("\nCurrent Authentication Configuration:")
    print(f"Service: {settings.service_name}")
    print(f"Environment: {settings.environment}")
    print(f"Enabled Providers: {settings.auth_enabled_providers}")
    print(f"Default Provider: {settings.auth_default_provider}")
