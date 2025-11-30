"""HTTP adapter for the identity service."""

import os
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from mmf_new.application.services.plugin_manager import PluginManager
from mmf_new.framework.plugins.models import PluginContext
from mmf_new.services.identity.application.ports_out import (
    AuthenticationCredentials,
    AuthenticationMethod,
)
from mmf_new.services.identity.application.use_cases import (
    AuthenticateUserRequest,
    AuthenticateUserUseCase,
)
from mmf_new.services.identity.domain.models import AuthenticationStatus, Credentials
from mmf_new.services.identity.infrastructure.adapters import (
    BasicAuthAdapter,
    BasicAuthConfig,
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


class UserResponse(BaseModel):
    """HTTP response model for user details."""

    user_id: str
    username: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    auth_method: str | None = None
    created_at: str
    expires_at: str | None = None


class ValidateTokenResponse(BaseModel):
    """HTTP response model for token validation."""

    valid: bool
    user_id: str | None = None


class IdentityServiceApp:
    """FastAPI application for the identity service."""

    def __init__(self):
        self.app = FastAPI(
            title="Identity Service",
            description="Minimal example of hexagonal architecture identity service",
            version="1.0.0",
        )

        # Initialize infrastructure adapters
        self.plugin_manager = PluginManager()

        # Initialize Basic Auth Adapter
        self.basic_auth_adapter = BasicAuthAdapter(BasicAuthConfig())

        # Initialize use case with providers
        self.auth_usecase = AuthenticateUserUseCase([self.basic_auth_adapter])

        self._setup_routes()

    def _setup_routes(self):
        """Set up HTTP routes."""

        @self.app.on_event("startup")
        async def startup_event():
            """Initialize plugins on startup."""
            # Discover plugins
            plugin_dir = os.getenv("PLUGIN_DIR", "/app/platform_plugins")
            if os.path.exists(plugin_dir):
                await self.plugin_manager.discover_plugins([plugin_dir])

                # Load Vault plugin if configured
                vault_url = os.getenv("VAULT_ADDR")
                vault_token = os.getenv("VAULT_TOKEN")

                if vault_url and vault_token:
                    plugin_id = "secrets.vault"
                    if await self.plugin_manager.load_plugin(plugin_id):
                        plugin = self.plugin_manager.registry.get_plugin(plugin_id)
                        if plugin:
                            context = PluginContext(
                                plugin_id=plugin_id,
                                config={
                                    "vault": {
                                        "url": vault_url,
                                        "token": vault_token,
                                        "mount_path": os.getenv("VAULT_MOUNT_POINT", "secret"),
                                    }
                                },
                            )
                            try:
                                await plugin.initialize(context)
                                await self.plugin_manager.start_plugin(plugin_id)
                                print(f"Vault plugin loaded and started. URL: {vault_url}")
                            except Exception as e:
                                print(f"Failed to initialize/start Vault plugin: {e}")
                    else:
                        print(f"Failed to load plugin {plugin_id}")

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "identity"}

        @self.app.post("/authenticate", response_model=AuthenticationResponse)
        async def authenticate(request: AuthenticationRequest):
            """Authenticate a user."""
            try:
                # Create credentials domain object
                credentials = AuthenticationCredentials(
                    method=AuthenticationMethod.BASIC,
                    credentials={"username": request.username, "password": request.password},
                )

                # Execute use case
                auth_request = AuthenticateUserRequest(credentials=credentials)
                result = await self.auth_usecase.execute(auth_request)

                if result.success and result.user:
                    return AuthenticationResponse(
                        success=True,
                        user_id=result.user.user_id,
                        username=result.user.username or result.user.user_id,
                        authenticated_at=result.user.created_at.isoformat(),
                        expires_at=(
                            result.user.expires_at.isoformat() if result.user.expires_at else None
                        ),
                    )
                else:
                    error_msg = result.error.message if result.error else "Authentication failed"
                    return AuthenticationResponse(success=False, error_message=error_msg)

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.get("/auth/me", response_model=UserResponse)
        async def get_current_user(authorization: str | None = Header(None)):
            """Get current user details."""
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Invalid authorization header")

            # In this minimal example, the token IS the user_id (e.g. "user_admin")
            # or username (e.g. "admin"). The BasicAuthAdapter stores users by username.
            # Let's try to find the user.
            token = authorization.split(" ")[1]

            # Hack: Access internal user store of BasicAuthAdapter for demo purposes
            # In a real app, we would use a GetUserUseCase or TokenValidationUseCase

            # Try to find by user_id or username
            user_data = None
            for username, data in self.basic_auth_adapter._users.items():
                if data["user_id"] == token or username == token:
                    user_data = data
                    user_data["username"] = username  # Ensure username is set
                    break

            if not user_data:
                raise HTTPException(status_code=401, detail="User not found or invalid token")

            return UserResponse(
                user_id=user_data["user_id"],
                username=user_data["username"],
                email=user_data.get("email"),
                roles=user_data.get("roles", []),
                permissions=user_data.get("permissions", []),
                auth_method="basic",
                created_at=user_data["created_at"],
                expires_at=None,
            )

        @self.app.post("/auth/validate", response_model=ValidateTokenResponse)
        async def validate_token(authorization: str | None = Header(None)):
            """Validate token."""
            if not authorization or not authorization.startswith("Bearer "):
                return ValidateTokenResponse(valid=False)

            token = authorization.split(" ")[1]

            # Check if user exists (simple validation for demo)
            for username, data in self.basic_auth_adapter._users.items():
                if data["user_id"] == token or username == token:
                    return ValidateTokenResponse(valid=True, user_id=data["user_id"])

            return ValidateTokenResponse(valid=False)

        @self.app.get("/plugins")
        async def list_plugins():
            """List loaded plugins."""
            plugins = {}
            # Access internal status dict since there's no public accessor for all statuses
            # This is a bit hacky but works for now. Ideally PluginManager should expose this.
            for plugin_id, status in self.plugin_manager._plugin_status.items():
                plugin = self.plugin_manager.registry.get_plugin(plugin_id)
                version = "unknown"
                if plugin:
                    try:
                        version = plugin.get_metadata().version
                    except Exception:
                        pass

                plugins[plugin_id] = {"status": status.name, "version": version}
            return {"plugins": plugins}


# Create the FastAPI app instance
identity_app = IdentityServiceApp()
app = identity_app.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
