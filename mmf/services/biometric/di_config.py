"""Dependency injection wiring for the biometric service."""

from mmf.services.biometric.application.ports_out import BiometricProvider
from mmf.services.biometric.application.use_cases import VerifyBiometricUseCase
from mmf.services.biometric.config import BiometricConfig, BiometricProviderType
from mmf.services.biometric.infrastructure.adapters.biometric_adapter import (
    MockBiometricAdapter,
    RustBiometricAdapter,
)


class BiometricDIContainer:
    """Wire biometric dependencies from config."""

    def __init__(self, config: BiometricConfig) -> None:
        self._config = config
        self._provider: BiometricProvider | None = None
        self._use_case: VerifyBiometricUseCase | None = None

    def initialize(self) -> None:
        cfg = self._config
        if cfg.provider_type == BiometricProviderType.LOCAL_ONNX:
            self._provider = RustBiometricAdapter(models_dir=cfg.models_dir)
        else:
            self._provider = MockBiometricAdapter()

        self._use_case = VerifyBiometricUseCase(
            provider=self._provider,
            quality_min_score=cfg.quality_min_score,
            default_threshold=cfg.default_threshold,
        )

    def cleanup(self) -> None:
        self._provider = None
        self._use_case = None

    @property
    def verify_use_case(self) -> VerifyBiometricUseCase:
        assert self._use_case is not None, "Container not initialized"
        return self._use_case
