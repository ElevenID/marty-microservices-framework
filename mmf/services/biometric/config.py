"""Biometric service configuration."""

from dataclasses import dataclass, field
from enum import Enum


class BiometricProviderType(Enum):
    """Available biometric provider implementations."""

    MOCK = "mock"
    LOCAL_ONNX = "local_onnx"


@dataclass
class BiometricConfig:
    """Configuration for the biometric verification service."""

    provider_type: BiometricProviderType = BiometricProviderType.MOCK
    """Which biometric backend to use."""

    models_dir: str = ""
    """Path to ONNX model files (required for LOCAL_ONNX provider)."""

    default_threshold: float = 0.7
    """Default similarity threshold for face verification."""

    quality_min_score: float = 0.4
    """Minimum quality score to accept an image for verification."""

    max_image_size_bytes: int = 10 * 1024 * 1024
    """Maximum allowed image payload (10 MB default)."""


def create_development_config() -> BiometricConfig:
    """Development: mock provider, permissive thresholds."""
    return BiometricConfig(
        provider_type=BiometricProviderType.MOCK,
        default_threshold=0.5,
        quality_min_score=0.2,
    )


def create_production_config(models_dir: str) -> BiometricConfig:
    """Production: real ONNX inference with strict thresholds."""
    return BiometricConfig(
        provider_type=BiometricProviderType.LOCAL_ONNX,
        models_dir=models_dir,
        default_threshold=0.7,
        quality_min_score=0.4,
    )


def create_testing_config() -> BiometricConfig:
    """Test: mock provider, deterministic behaviour."""
    return BiometricConfig(
        provider_type=BiometricProviderType.MOCK,
        default_threshold=0.5,
        quality_min_score=0.1,
    )
