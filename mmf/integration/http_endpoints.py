"""
JWT-based HTTP endpoints for authentication.

Provides REST API endpoints for JWT token operations following
FastAPI conventions and hexagonal architecture principles.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from marty_msf.core.di_container import get_service

from .configuration import IntegrationConfig


# Request/Response models
class LoginRequest(BaseModel):
    """Request model for user login."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Response model for token operations."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    """User information from token."""
    user_id: str
    username: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []


@dataclass
class AuthenticatedUser:
    """Simple user model for integration layer."""
    user_id: str
    username: str
    email: str | None = None
    roles: set[str] | None = None
    permissions: set[str] | None = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = set()
        if self.permissions is None:
            self.permissions = set()


class JWTService:
    """Simplified JWT service for integration layer."""

    def __init__(self, config: IntegrationConfig):
        self.config = config

    def create_token(self, user: AuthenticatedUser) -> dict[str, Any]:
        """Create JWT token for user."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.config.jwt_access_token_expire_minutes)

        payload = {
            "sub": user.user_id,
            "username": user.username,
            "iat": now,
            "exp": expires_at,
        }

        if user.email:
            payload["email"] = user.email
        if user.roles:
            payload["roles"] = list(user.roles)
        if user.permissions:
            payload["permissions"] = list(user.permissions)

        token = jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": self.config.jwt_access_token_expire_minutes * 60
        }

    def validate_token(self, token: str) -> AuthenticatedUser:
        """Validate JWT token and return user."""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm]
            )

            return AuthenticatedUser(
                user_id=payload["sub"],
                username=payload["username"],
                email=payload.get("email"),
                roles=set(payload.get("roles", [])),
                permissions=set(payload.get("permissions", []))
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )


# Dependency injection for clean architecture
def get_config() -> IntegrationConfig:
    """Get configuration instance from DI container."""
    return get_service(IntegrationConfig)


def get_jwt_service() -> JWTService:
    """Get JWT service instance from DI container."""
    return get_service(JWTService)


# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    jwt_service: JWTService = Depends(get_jwt_service)
) -> TokenResponse:
    """
    Authenticate user and return JWT token.

    For demo purposes, accepts any username/password combination.
    In production, this would validate against a user store.
    """
    # Simple demo authentication - accept any non-empty credentials
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Create demo user
    user = AuthenticatedUser(
        user_id=f"user_{request.username}",
        username=request.username,
        email=f"{request.username}@example.com",
        roles={"user"},
        permissions={"read", "write"}
    )

    # Generate token
    token_data = jwt_service.create_token(user)

    return TokenResponse(**token_data)


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    token: str,
    jwt_service: JWTService = Depends(get_jwt_service)
) -> UserInfo:
    """Get current user information from JWT token."""
    user = jwt_service.validate_token(token)

    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        roles=list(user.roles) if user.roles else [],
        permissions=list(user.permissions) if user.permissions else []
    )


@router.post("/validate")
async def validate_token(
    token: str,
    jwt_service: JWTService = Depends(get_jwt_service)
) -> dict[str, str]:
    """Validate a JWT token."""
    try:
        user = jwt_service.validate_token(token)
        return {"status": "valid", "user_id": user.user_id}
    except HTTPException:
        return {"status": "invalid"}


# Public endpoints that don't require authentication
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/public")
async def public_endpoint() -> dict[str, str]:
    """Public endpoint accessible without authentication."""
    return {"message": "This is a public endpoint"}


@router.get("/protected")
async def protected_endpoint() -> dict[str, str]:
    """Protected endpoint that requires authentication."""
    return {"message": "This is a protected endpoint"}


@router.get("/optional")
async def optional_endpoint() -> dict[str, str]:
    """Endpoint with optional authentication."""
    return {"message": "This endpoint works with or without authentication"}
