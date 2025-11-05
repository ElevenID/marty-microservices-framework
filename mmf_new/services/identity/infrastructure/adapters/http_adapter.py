"""HTTP adapter for the identity service."""

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mmf_new.services.identity.application.usecases import AuthenticatePrincipalUseCase
from mmf_new.services.identity.domain.models import AuthenticationStatus, Credentials
from mmf_new.services.identity.infrastructure.adapters import (
    InMemoryEventBus,
    InMemoryUserRepository,
)


class AuthenticationRequest(BaseModel):
    """HTTP request model for authentication."""
    username: str
    password: str


class AuthenticationResponse(BaseModel):
    """HTTP response model for authentication."""
    success: bool
    user_id: str | None = None
    username: str | None = None
    authenticated_at: str | None = None
    expires_at: str | None = None
    error_message: str | None = None


class IdentityServiceApp:
    """FastAPI application for the identity service."""

    def __init__(self):
        self.app = FastAPI(
            title="Identity Service",
            description="Minimal example of hexagonal architecture identity service",
            version="1.0.0"
        )

        # Initialize infrastructure adapters
        self.user_repository = InMemoryUserRepository()
        self.event_bus = InMemoryEventBus()

        # Initialize use case
        self.auth_usecase = AuthenticatePrincipalUseCase(
            self.user_repository,
            self.event_bus
        )

        # Add some test users
        self.user_repository.add_user("admin", "admin123")
        self.user_repository.add_user("user", "password")
        self.user_repository.add_user("demo", "demo123")

        self._setup_routes()

    def _setup_routes(self):
        """Set up HTTP routes."""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "identity"}

        @self.app.post("/authenticate", response_model=AuthenticationResponse)
        async def authenticate(request: AuthenticationRequest):
            """Authenticate a user."""
            try:
                # Create credentials domain object
                credentials = Credentials(request.username, request.password)

                # Execute use case
                result = self.auth_usecase.execute(credentials)

                if result.status == AuthenticationStatus.SUCCESS:
                    return AuthenticationResponse(
                        success=True,
                        user_id=result.principal.user_id.value,
                        username=result.principal.username,
                        authenticated_at=result.principal.authenticated_at.isoformat(),
                        expires_at=result.principal.expires_at.isoformat() if result.principal.expires_at else None
                    )
                else:
                    return AuthenticationResponse(
                        success=False,
                        error_message=result.error_message
                    )

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.get("/events")
        async def get_events():
            """Get published events (for testing)."""
            return {"events": self.event_bus.get_published_events()}

        @self.app.get("/users")
        async def list_users():
            """List available test users (for demo purposes)."""
            return {
                "test_users": [
                    {"username": "admin", "password": "admin123"},
                    {"username": "user", "password": "password"},
                    {"username": "demo", "password": "demo123"}
                ]
            }


# Create the FastAPI app instance
identity_app = IdentityServiceApp()
app = identity_app.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
