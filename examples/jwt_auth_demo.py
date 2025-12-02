"""
JWT Authentication Integration Demo.

This module demonstrates how to use the JWT authentication integration
components in a FastAPI application.
"""

import os

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mmf.services.identity.integration import (
    JWTAuthenticationMiddleware,
    create_development_config,
    create_production_config,
    get_current_user,
    require_authenticated_user,
)
from mmf.services.identity.integration import (
    router as jwt_router,  # Router and endpoints; Middleware; Configuration
)


def create_app_with_jwt_auth(environment: str = "development") -> FastAPI:
    """
    Create a FastAPI application with JWT authentication.

    Args:
        environment: Environment name (development, testing, production)

    Returns:
        Configured FastAPI application
    """
    application = FastAPI(title="JWT Authentication Demo")

    # Configure JWT based on environment
    if environment == "production":
        # In production, get secret from environment variables
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable required for production")
        jwt_config = create_production_config(secret_key)
    else:
        # Development/testing with default settings
        jwt_config = create_development_config()

    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add JWT authentication middleware
    application.add_middleware(
        JWTAuthenticationMiddleware,
        jwt_config=jwt_config.to_jwt_config(),
        excluded_paths=jwt_config.excluded_paths,
        optional_paths=jwt_config.optional_paths,
    )

    # Include JWT authentication endpoints
    application.include_router(jwt_router)

    # Example protected endpoint
    @application.get("/protected")
    async def protected_endpoint(user: dict = Depends(require_authenticated_user)):
        """Protected endpoint that requires authentication."""
        return {
            "message": "This is a protected endpoint",
            "user": {
                "user_id": user["user_id"],
                "username": user["username"],
                "roles": user["roles"],
                "permissions": user["permissions"],
            }
        }

    # Example optional authentication endpoint
    @application.get("/optional")
    async def optional_endpoint(user: dict | None = Depends(get_current_user)):
        """Endpoint with optional authentication."""
        if user:
            return {
                "message": "Hello authenticated user!",
                "user_id": user["user_id"],
                "username": user["username"],
            }
        else:
            return {"message": "Hello anonymous user!"}

    # Public endpoint
    @application.get("/public")
    async def public_endpoint():
        """Public endpoint accessible without authentication."""
        return {"message": "This is a public endpoint"}

    return application


# Example usage
if __name__ == "__main__":

    # Create application
    app = create_app_with_jwt_auth("development")

    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
