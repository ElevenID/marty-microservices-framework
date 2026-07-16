from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path


class HostingEnvironment(Enum):
    """Supported hosting environments."""

    LOCAL = "local"
    SELF_HOSTED = "self_hosted"
    AWS = "aws"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    UNKNOWN = "unknown"


class SecretBackend(Enum):
    """Available secret management backends."""

    VAULT = "vault"  # pragma: allowlist secret
    AWS_SECRETS_MANAGER = "aws_secrets_manager"  # pragma: allowlist secret
    AZURE_KEY_VAULT = "azure_key_vault"  # pragma: allowlist secret
    GCP_SECRET_MANAGER = "gcp_secret_manager"  # pragma: allowlist secret
    KUBERNETES = "kubernetes"
    ENVIRONMENT = "environment"
    FILE = "file"
    MEMORY = "memory"


class ConfigurationStrategy(Enum):
    """Configuration loading strategies."""

    HIERARCHICAL = "hierarchical"  # base -> env -> secrets
    EXPLICIT = "explicit"  # only specified sources
    FALLBACK = "fallback"  # try backends in order until success
    AUTO_DETECT = "auto_detect"  # automatically detect best backends for environment


@dataclass
class SecretMetadata:
    """Metadata for secrets."""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    rotation_interval: timedelta | None = None
    last_rotated: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict)
    backend: SecretBackend = SecretBackend.VAULT
    encrypted: bool = True


from mmf.framework.infrastructure.config_manager import Environment


@dataclass
class ConfigurationContext:
    """Context for configuration loading."""

    service_name: str
    environment: Environment
    config_dir: Path | None = None
    plugins_dir: Path | None = None
    enable_secrets: bool = True
    enable_hot_reload: bool = False
    enable_plugins: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=15))
    strategy: ConfigurationStrategy = ConfigurationStrategy.HIERARCHICAL
