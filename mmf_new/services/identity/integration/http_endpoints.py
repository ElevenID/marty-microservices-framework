"""
FastAPI HTTP endpoints for JWT authentication.

This module provides RESTful API endpoints for JWT authentication operations
including token authentication and validation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from mmf_new.services.identity.application.use_cases import (
    AuthenticateWithJWTRequest,
    AuthenticateWithJWTUseCase,
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf_new.services.identity.domain.models import (
    AuthenticationErrorCode,
    AuthenticationStatus,
)
from mmf_new.services.identity.infrastructure.adapters import (
    JWTConfig,
    JWTTokenProvider,
)


# Request/Response Models
class AuthenticateJWTRequestModel(BaseModel):
    """Request model for JWT authentication."""

    token: str = Field(..., description="JWT token to authenticate")


class ValidateTokenRequestModel(BaseModel):
    """Request model for token validation."""

    token: str = Field(..., description="JWT token to validate")


class AuthenticatedUserResponse(BaseModel):
    """Response model for authenticated user information."""

    user_id: str
    username: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    created_at: datetime
    expires_at: datetime | None = None
    user_metadata: dict = {}


class AuthenticationResponse(BaseModel):
    """Response model for authentication operations."""

    status: str
    user: AuthenticatedUserResponse | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict = {}


class TokenValidationResponse(BaseModel):
    """Response model for token validation operations."""

    is_valid: bool
    user: AuthenticatedUserResponse | None = None
    error_message: str | None = None


# Dependency Injection
def get_jwt_config() -> JWTConfig:
    """Get JWT configuration."""
    return JWTConfig(
        secret_key="your-secret-key-here",  # Should come from environment
        algorithm="HS256",
        issuer="marty-microservices-framework",
        audience="marty-api",
    )


def get_jwt_token_provider(
    config: JWTConfig = Depends(get_jwt_config),
) -> JWTTokenProvider:
    """Get JWT token provider."""
    return JWTTokenProvider(config)


def get_authenticate_use_case(
    token_provider: JWTTokenProvider = Depends(get_jwt_token_provider),
) -> AuthenticateWithJWTUseCase:
    """Get authentication use case."""
    return AuthenticateWithJWTUseCase(token_provider)


def get_validate_token_use_case(
    token_provider: JWTTokenProvider = Depends(get_jwt_token_provider),
) -> ValidateTokenUseCase:
    """Get token validation use case."""
    return ValidateTokenUseCase(token_provider)


# Router
router = APIRouter(prefix="/auth/jwt", tags=["JWT Authentication"])


@router.post("/authenticate", response_model=AuthenticationResponse)
async def authenticate_with_jwt(
    request: AuthenticateJWTRequestModel,
    use_case: AuthenticateWithJWTUseCase = Depends(get_authenticate_use_case),
) -> AuthenticationResponse:
    """
    Authenticate a user using a JWT token.

    Args:
        request: Authentication request containing JWT token
        use_case: Authentication use case dependency

    Returns:
        Authentication response with user information or error

    Raises:
        HTTPException: For various authentication failures
    """
    try:
        # Execute authentication use case
        auth_request = AuthenticateWithJWTRequest(token=request.token)
        result = await use_case.execute(auth_request)

        # Convert result to response model
        if result.status == AuthenticationStatus.SUCCESS and result.authenticated_user:
            user_response = AuthenticatedUserResponse(
                user_id=result.authenticated_user.user_id,
                username=result.authenticated_user.username
                or result.authenticated_user.user_id,  # fallback to user_id if username is None
                email=result.authenticated_user.email,
                roles=list(result.authenticated_user.roles),
                permissions=list(result.authenticated_user.permissions),
                created_at=result.authenticated_user.created_at,
                expires_at=result.authenticated_user.expires_at,
                user_metadata=result.authenticated_user.metadata,
            )

            return AuthenticationResponse(
                status=result.status.value, user=user_response, metadata=result.metadata
            )
        else:
            # Authentication failed
            # Map to appropriate HTTP status
            if result.error_code == AuthenticationErrorCode.TOKEN_INVALID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Authentication failed: {result.error_message}",
                )
            elif result.error_code == AuthenticationErrorCode.TOKEN_EXPIRED:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Authentication failed: {result.error_message}",
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal authentication error: {str(e)}",
        ) from e


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(
    request: ValidateTokenRequestModel,
    use_case: ValidateTokenUseCase = Depends(get_validate_token_use_case),
) -> TokenValidationResponse:
    """
    Validate a JWT token and extract user information.

    Args:
        request: Token validation request
        use_case: Token validation use case dependency

    Returns:
        Token validation response with user information if valid

    Raises:
        HTTPException: For validation errors
    """
    try:
        # Execute validation use case
        validation_request = ValidateTokenRequest(token=request.token)
        result = await use_case.execute(validation_request)

        # Convert result to response model
        if result.is_valid and result.user:
            user_response = AuthenticatedUserResponse(
                user_id=result.user.user_id,
                username=result.user.username
                or result.user.user_id,  # fallback to user_id if username is None
                email=result.user.email,
                roles=list(result.user.roles),
                permissions=list(result.user.permissions),
                created_at=result.user.created_at,
                expires_at=result.user.expires_at,
                user_metadata=result.user.metadata,
            )

            return TokenValidationResponse(is_valid=True, user=user_response)
        else:
            return TokenValidationResponse(
                is_valid=False, error_message=result.error_message
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token validation error: {str(e)}",
        ) from e


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint for JWT authentication service."""
    return {"status": "healthy", "service": "jwt-authentication"}
