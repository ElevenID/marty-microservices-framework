"""Verify biometric use case."""

from dataclasses import dataclass
from typing import Optional

from mmf.services.biometric.application.ports_out import (
    BiometricProvider,
    FaceMatchRequest,
    FaceMatchResult,
    QualityResult,
)


@dataclass
class VerifyBiometricRequest:
    """Input for the verify-biometric use case."""
    reference_image: str
    probe_image: str
    threshold: float | None = None


class VerifyBiometricUseCase:
    """
    Perform a 1:1 face verification through the configured provider.

    Optionally gates on image quality before running the match.
    """

    def __init__(
        self,
        provider: BiometricProvider,
        quality_min_score: float = 0.4,
        default_threshold: float = 0.7,
    ) -> None:
        self._provider = provider
        self._quality_min = quality_min_score
        self._default_threshold = default_threshold

    async def execute(self, request: VerifyBiometricRequest) -> FaceMatchResult:
        threshold = request.threshold or self._default_threshold
        return await self._provider.verify(
            FaceMatchRequest(
                reference_image=request.reference_image,
                probe_image=request.probe_image,
                threshold=threshold,
            )
        )

    async def assess_quality(self, image_b64: str) -> QualityResult:
        return await self._provider.assess_quality(image_b64)
