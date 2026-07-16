"""
Basic security integration example using the new modular security architecture.
This example demonstrates proper usage of the level contract architecture.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBearer

# Import new modular security architecture
from mmf.framework.security import (  # Bootstrap functions; Core interfaces; Data models
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationResult,
    IAuthenticator,
    IAuthorizer,
    ISecretManager,
    User,
    create_default_security_system,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BasicSecurityExample:
    """Basic security integration example using modular security architecture"""

    def __init__(self):
        self.app = FastAPI(title="Basic Secure Service")
        self.authenticator: IAuthenticator | None = None
        self.authorizer: IAuthorizer | None = None
        self.secret_manager: ISecretManager | None = None

    async def initialize_security(self) -> None:
        """Initialize security system using the new modular architecture"""

        # Initialize security components using the bootstrap
        self.authenticator, self.authorizer, self.secret_manager = create_default_security_system()

        logger.info("Security system initialized with:")
        logger.info(f"  Authenticator: {type(self.authenticator).__name__}")
        logger.info(f"  Authorizer: {type(self.authorizer).__name__}")
        logger.info(f"  Secret Manager: {type(self.secret_manager).__name__}")

        # Setup test user credentials
        test_user_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # "password"
        self.secret_manager.store_secret("user.test_user.password_hash", test_user_hash)

        logger.info("Test user 'test_user' configured with password 'password'")

    def setup_routes(self) -> None:
        """Setup API routes with security enforcement"""

        security = HTTPBearer()

        @self.app.get("/api/v1/users")
        async def list_users():
            """List users - requires user or admin role"""
            # For demo purposes, create a test user
            user = User(
                id="demo_user",
                username="demo_user",
                roles=["user"]
            )

            # Demonstrate authorization check
            context = AuthorizationContext(
                user=user,
                resource="users",
                action="read"
            )

            result = self.authorizer.authorize(context)

            if not result.allowed:
                raise HTTPException(status_code=403, detail=f"Access denied: {result.reason}")

            return {"users": ["alice", "bob"], "authorized": True}

        @self.app.get("/api/v1/admin/stats")
        async def get_admin_stats():
            """Get admin statistics - requires admin role"""
            # For demo purposes, create a test admin user
            admin_user = User(
                id="admin_user",
                username="admin_user",
                roles=["admin"]
            )

            # Demonstrate authorization check for admin-only resource
            context = AuthorizationContext(
                user=admin_user,
                resource="admin",
                action="read"
            )

            result = self.authorizer.authorize(context)

            if not result.allowed:
                raise HTTPException(status_code=403, detail=f"Access denied: {result.reason}")

            return {
                "total_users": 42,
                "active_sessions": 10,
                "authorized": True
            }

        @self.app.post("/api/v1/auth/login")
        async def login(request: Request):
            """Authenticate user with credentials"""
            body = await request.json()
            username = body.get("username")
            password = body.get("password")

            if not username or not password:
                raise HTTPException(status_code=400, detail="Username and password required")

            # Attempt authentication
            auth_result = self.authenticator.authenticate({
                "username": username,
                "password": password
            })

            if auth_result.success:
                return {
                    "success": True,
                    "user": {
                        "id": auth_result.user.id,
                        "username": auth_result.user.username,
                        "roles": auth_result.user.roles
                    }
                }
            else:
                raise HTTPException(status_code=401, detail=auth_result.error_message)

        @self.app.get("/api/v1/security/status")
        async def get_security_status():
            """Get security framework status"""
            return {
                "security_initialized": all([
                    self.authenticator is not None,
                    self.authorizer is not None,
                    self.secret_manager is not None
                ]),
                "authenticator": type(self.authenticator).__name__ if self.authenticator else None,
                "authorizer": type(self.authorizer).__name__ if self.authorizer else None,
                "secret_manager": type(self.secret_manager).__name__ if self.secret_manager else None
            }

        @self.app.get("/health")
        async def health():
            """Health check"""
            return {
                "status": "healthy",
                "security_initialized": all([
                    self.authenticator is not None,
                    self.authorizer is not None,
                    self.secret_manager is not None
                ])
            }

async def main():
    """Run the basic example"""

    global example_instance
    example_instance = BasicSecurityExample()

    try:
        await example_instance.initialize_security()
        example_instance.setup_routes()

        logger.info("Basic security example ready!")
        logger.info("Available endpoints:")
        logger.info("  POST /api/v1/auth/login - Authenticate (use test_user/password)")
        logger.info("  GET /api/v1/users - List users (requires user/admin role)")
        logger.info("  GET /api/v1/admin/stats - Admin statistics (requires admin role)")
        logger.info("  GET /api/v1/security/status - Security framework status")
        logger.info("  GET /health - Health check")
        logger.info("")
        logger.info("To run: uvicorn basic_security_example:example_instance.app --reload")

    except Exception as e:
        logger.error(f"Failed to initialize basic security example: {e}")
        raise


# Global instance for uvicorn
example_instance = None


if __name__ == "__main__":
    asyncio.run(main())
