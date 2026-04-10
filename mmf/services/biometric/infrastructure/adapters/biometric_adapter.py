"""
Rust FFI adapter — wraps the maturin-built ``_marty_biometrics`` extension.

Install the wheel first::

    cd marty-core/marty-biometrics
    maturin develop --features python          # mock + local stubs
    maturin develop --features python,onnx     # full ONNX inference
"""

from mmf.services.biometric.application.ports_out import (
    BiometricProvider,
    FaceMatchRequest,
    FaceMatchResult,
    QualityResult,
)


def _get_rust_module():
    try:
        import _marty_biometrics
        return _marty_biometrics
    except ImportError:
        raise RuntimeError(
            "marty-biometrics Rust bindings not installed. "
            "Run: cd marty-core/marty-biometrics && maturin develop --features python"
        )


class RustBiometricAdapter(BiometricProvider):
    """Adapter that delegates to the Rust ``_marty_biometrics`` FFI layer."""

    def __init__(self, models_dir: str | None = None) -> None:
        rust = _get_rust_module()
        if models_dir and hasattr(rust.FaceVerifier, "onnx"):
            self._verifier = rust.FaceVerifier.onnx(models_dir)
        else:
            self._verifier = rust.FaceVerifier.mock()

    async def verify(self, request: FaceMatchRequest) -> FaceMatchResult:
        rust = _get_rust_module()
        rust_req = rust.FaceVerificationRequest(
            reference_image=request.reference_image,
            probe_image=request.probe_image,
            threshold=request.threshold,
        )
        r = self._verifier.verify(rust_req)
        return FaceMatchResult(
            verified=r.verified,
            similarity=r.similarity,
            threshold=r.threshold,
            provider=r.provider,
            reference_quality=r.reference_quality,
            probe_quality=r.probe_quality,
            processing_time_ms=r.processing_time_ms,
        )

    async def assess_quality(self, image_b64: str) -> QualityResult:
        r = self._verifier.assess_quality(image_b64)
        return QualityResult(
            overall_score=r.overall_score,
            face_detected=r.face_detected,
            face_count=r.face_count,
            sharpness=r.sharpness,
            brightness=r.brightness,
            contrast=r.contrast,
            face_size=r.face_size,
            pose=r.pose,
        )


class MockBiometricAdapter(BiometricProvider):
    """Pure-Python mock for testing without the Rust extension."""

    def __init__(self, similarity: float = 0.95) -> None:
        self._similarity = similarity

    async def verify(self, request: FaceMatchRequest) -> FaceMatchResult:
        threshold = request.threshold or 0.7
        return FaceMatchResult(
            verified=self._similarity >= threshold,
            similarity=self._similarity,
            threshold=threshold,
            provider="python-mock",
            reference_quality=0.95,
            probe_quality=0.9,
            processing_time_ms=1,
        )

    async def assess_quality(self, image_b64: str) -> QualityResult:
        return QualityResult(
            overall_score=0.95,
            face_detected=True,
            face_count=1,
            sharpness=0.95,
            brightness=0.5,
            contrast=0.85,
            face_size=0.65,
            pose=0.98,
        )
