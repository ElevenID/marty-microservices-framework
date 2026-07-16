"""
FastAPI router for biometric verification endpoints.

Mount this router in the gateway or run standalone::

    uvicorn mmf.services.biometric.infrastructure.adapters.web_router:create_app --reload
"""

from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mmf.services.biometric.application.use_cases import VerifyBiometricRequest
from mmf.services.biometric.config import create_development_config
from mmf.services.biometric.di_config import BiometricDIContainer


# ── Pydantic request / response models ──────────────────────────────────

class VerifyRequest(BaseModel):
    reference_image: str = Field(..., description="Base64-encoded reference image")
    probe_image: str = Field(..., description="Base64-encoded probe image")
    threshold: float | None = Field(None, ge=0.0, le=1.0)


class VerifyResponse(BaseModel):
    verified: bool
    similarity: float
    threshold: float
    provider: str
    reference_quality: float | None = None
    probe_quality: float | None = None
    processing_time_ms: int = 0


class QualityRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded face image")


class QualityResponse(BaseModel):
    overall_score: float
    face_detected: bool
    face_count: int
    sharpness: float
    brightness: float
    contrast: float
    face_size: float
    pose: float


# ── App factory ─────────────────────────────────────────────────────────

def create_app(container: BiometricDIContainer | None = None) -> FastAPI:
    """Create the biometric FastAPI app."""
    app = FastAPI(
        title="Marty Biometric Service",
        version="0.1.0",
        description="Face verification, quality assessment, and liveness endpoints",
    )

    if container is None:
        container = BiometricDIContainer(create_development_config())
        container.initialize()

    @app.post("/v1/biometrics/verify", response_model=VerifyResponse)
    async def verify(body: VerifyRequest) -> VerifyResponse:
        uc = container.verify_use_case
        result = await uc.execute(
            VerifyBiometricRequest(
                reference_image=body.reference_image,
                probe_image=body.probe_image,
                threshold=body.threshold,
            )
        )
        return VerifyResponse(**asdict(result))

    @app.post("/v1/biometrics/quality", response_model=QualityResponse)
    async def quality(body: QualityRequest) -> QualityResponse:
        uc = container.verify_use_case
        result = await uc.assess_quality(body.image)
        return QualityResponse(**asdict(result))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
