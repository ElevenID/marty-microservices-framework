"""
FastAPI JWT Authentication Endpoints.

Provides HTTP endpoints for JWT authentication operations including
token creation, validation, and user authentication.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from mmf.services.identity.application.use_cases import (
    AuthenticateWithJWTRequest,
    AuthenticateWithJWTUseCase,
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf.services.identity.application.use_cases.authenticate_with_basic import (
    AuthenticateWithBasicUseCase,
    BasicAuthenticationRequest,
)
from mmf.services.identity.domain.models import AuthenticatedUser, AuthenticationStatus
from mmf.services.identity.infrastructure.adapters import (
    BasicAuthAdapter,
    BasicAuthConfig,
    JWTConfig,
    JWTTokenProvider,
)
from mmf.services.identity.infrastructure.adapters.out.config.config_integration import (
    get_basic_auth_config_from_yaml,
    get_jwt_config_from_yaml,
)


# Request/Response Models
class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    """Response model for token operations."""

    token: str = Field(..., description="JWT token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")


class ValidateTokenResponse(BaseModel):
    """Response model for token validation."""

    valid: bool = Field(..., description="Whether token is valid")
    user_id: str | None = Field(None, description="User ID if valid")
    username: str | None = Field(None, description="Username if valid")
    email: str | None = Field(None, description="Email if valid")
    roles: list[str] = Field(default_factory=list, description="User roles")
    permissions: list[str] = Field(default_factory=list, description="User permissions")
    expires_at: str | None = Field(None, description="Token expiration")


class UserResponse(BaseModel):
    """Response model for user information."""

    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str | None = Field(None, description="Email")
    roles: list[str] = Field(default_factory=list, description="User roles")
    permissions: list[str] = Field(default_factory=list, description="User permissions")
    auth_method: str | None = Field(None, description="Authentication method")
    created_at: str = Field(..., description="Account creation timestamp")
    expires_at: str | None = Field(None, description="Session expiration")


class ErrorResponse(BaseModel):
    """Response model for error cases."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Error code")


# Dependencies
def get_jwt_config() -> JWTConfig:
    """Get JWT configuration from YAML files."""
    return get_jwt_config_from_yaml()


def get_basic_auth_config() -> BasicAuthConfig:
    """Get Basic Auth configuration from YAML files."""
    return get_basic_auth_config_from_yaml()


def get_token_provider(config: JWTConfig = Depends(get_jwt_config)) -> JWTTokenProvider:
    """Get JWT token provider."""
    return JWTTokenProvider(config)


def get_basic_auth_provider(
    config: BasicAuthConfig = Depends(get_basic_auth_config),
) -> BasicAuthAdapter:
    """Get Basic Auth provider."""
    return BasicAuthAdapter(config)


def get_auth_use_case(
    token_provider: JWTTokenProvider = Depends(get_token_provider),
) -> AuthenticateWithJWTUseCase:
    """Get JWT authentication use case."""
    return AuthenticateWithJWTUseCase(token_provider)


def get_basic_auth_use_case(
    auth_provider: BasicAuthAdapter = Depends(get_basic_auth_provider),
) -> AuthenticateWithBasicUseCase:
    """Get Basic Auth use case."""
    return AuthenticateWithBasicUseCase(auth_provider)


def get_validate_use_case(
    token_provider: JWTTokenProvider = Depends(get_token_provider),
) -> ValidateTokenUseCase:
    """Get token validation use case."""
    return ValidateTokenUseCase(token_provider)


async def extract_token_from_header(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract JWT token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    return authorization[7:]  # Remove "Bearer " prefix


# Router
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    token_provider: JWTTokenProvider = Depends(get_token_provider),
    auth_use_case: AuthenticateWithBasicUseCase = Depends(get_basic_auth_use_case),
) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    This endpoint handles user login by validating credentials
    and returning a JWT token for authenticated access.
    """
    # Authenticate user
    auth_request = BasicAuthenticationRequest(
        username=request.username,
        password=request.password,
    )

    result = await auth_use_case.execute(auth_request)

    if result.status != AuthenticationStatus.SUCCESS or not result.authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error_message or "Invalid credentials",
        )

    authenticated_user = result.authenticated_user

    try:
        token = await token_provider.create_token(authenticated_user)

        return TokenResponse(
            token=token,
            expires_in=3600,  # 1 hour in seconds
            user_id=authenticated_user.user_id,
            username=authenticated_user.username or request.username,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create token: {str(e)}",
        ) from e


@router.post("/validate", response_model=ValidateTokenResponse)
async def validate_token(
    token: Annotated[str, Depends(extract_token_from_header)],
    validate_use_case: ValidateTokenUseCase = Depends(get_validate_use_case),
) -> ValidateTokenResponse:
    """
    Validate JWT token and return user information.

    This endpoint validates a JWT token and returns user information
    if the token is valid and not expired.
    """
    try:
        request = ValidateTokenRequest(token=token)
        result = await validate_use_case.execute(request)

        if result.is_valid and result.user:
            return ValidateTokenResponse(
                valid=True,
                user_id=result.user.user_id,
                username=result.user.username,
                email=result.user.email,
                roles=list(result.user.roles),
                permissions=list(result.user.permissions),
                expires_at=(result.user.expires_at.isoformat() if result.user.expires_at else None),
            )
        else:
            return ValidateTokenResponse(valid=False)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token validation failed: {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: Annotated[str, Depends(extract_token_from_header)],
    auth_use_case: AuthenticateWithJWTUseCase = Depends(get_auth_use_case),
) -> UserResponse:
    """
    Get current authenticated user information.

    This endpoint returns detailed information about the currently
    authenticated user based on the provided JWT token.
    """
    try:
        request = AuthenticateWithJWTRequest(token=token)
        result = await auth_use_case.execute(request)

        if result.status == AuthenticationStatus.SUCCESS and result.authenticated_user:
            user = result.authenticated_user
            return UserResponse(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                roles=list(user.roles),
                permissions=list(user.permissions),
                auth_method=user.auth_method,
                created_at=user.created_at.isoformat(),
                expires_at=user.expires_at.isoformat() if user.expires_at else None,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.error_message or "Authentication failed",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user information: {str(e)}",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token: Annotated[str, Depends(extract_token_from_header)],
    token_provider: JWTTokenProvider = Depends(get_token_provider),
) -> TokenResponse:
    """
    Refresh JWT token.

    This endpoint allows refreshing an existing JWT token,
    extending its expiration time.
    """
    try:
        new_token = await token_provider.refresh_token(token)

        # Validate the new token to get user info
        authenticated_user = await token_provider.validate_token(new_token)

        return TokenResponse(
            token=new_token,
            expires_in=3600,  # 1 hour in seconds
            user_id=authenticated_user.user_id,
            username=authenticated_user.username,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )


@router.post("/logout")
async def logout() -> dict[str, str]:
    """
    Logout user and invalidate token.

    This endpoint handles user logout. In a production system,
    this would typically blacklist the token or mark it as invalid.
    """
    return {"message": "Successfully logged out"}
