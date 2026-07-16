"""Biometric provider port (outbound interface)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceMatchRequest:
    """Inbound request DTO for face verification."""
    reference_image: str
    probe_image: str
    threshold: float | None = None


@dataclass
class FaceMatchResult:
    """Result of a face verification."""
    verified: bool
    similarity: float
    threshold: float
    provider: str
    reference_quality: float | None = None
    probe_quality: float | None = None
    processing_time_ms: int = 0


@dataclass
class QualityResult:
    """Result of a face quality assessment."""
    overall_score: float
    face_detected: bool
    face_count: int
    sharpness: float
    brightness: float
    contrast: float
    face_size: float
    pose: float


class BiometricProvider(ABC):
    """Abstract biometric verification provider."""

    @abstractmethod
    async def verify(self, request: FaceMatchRequest) -> FaceMatchResult:
        """1:1 face verification."""
        ...

    @abstractmethod
    async def assess_quality(self, image_b64: str) -> QualityResult:
        """Assess face image quality."""
        ...
