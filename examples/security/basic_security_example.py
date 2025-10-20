"""
Basic security integration example using the Unified Security Framework.
This example shows basic integration patterns with the new unified architecture.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer

# Import Marty MSF unified security framework
from marty_msf.security.bridge import (
    UnifiedSecurityFrameworkBridge as UnifiedSecurityFramework,
)
from marty_msf.security.interfaces import SecurityDecision, SecurityPrincipal
from marty_msf.security.unified_framework import (
    BuiltinPolicyEngine,
    ComplianceFramework,
    IdentityProviderType,
    PolicyEngineType,
    SecurityPolicyType,
    create_unified_security_framework,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BasicSecurityExample:
    """Basic security integration example using Unified Security Framework"""

    def __init__(self):
        self.app = FastAPI(title="Basic Secure Service")
        self.security_framework = None
        self.test_principal = None

    async def initialize_security(self) -> None:
        """Initialize unified security framework"""

        # Configuration for the unified security framework
        security_config = {
            "default_identity_provider": "local",
            "policy_cache_ttl": 300,
            "audit_enabled": True,
            "service_mesh_enabled": False,
            "compliance_scanning_enabled": False
        }

        # Create unified security framework
        self.security_framework = await create_unified_security_framework(security_config)

        if not self.security_framework:
            raise Exception("Failed to initialize security framework")

        # Load basic policies
        await self._load_basic_policies()

        # Create a test principal for demonstration
        self.test_principal = SecurityPrincipal(
            id="demo_user",
            type="user",
            roles={"user", "admin"},
            attributes={"department": "engineering", "level": "senior"}
        )

        logger.info("Unified Security Framework initialized successfully")

    async def _load_basic_policies(self) -> None:
        """Load basic RBAC policies into the framework"""

        policies = [
            {
                "id": "basic_rbac_users",
                "type": SecurityPolicyType.RBAC.value,
                "rules": [
                    {
                        "resource": "/api/v1/users",
                        "action": "GET",
                        "principal": {"roles": ["admin", "user"]},
                        "effect": "allow"
                    }
                ]
            },
            {
                "id": "basic_rbac_admin",
                "type": SecurityPolicyType.RBAC.value,
                "rules": [
                    {
                        "resource": "/api/v1/admin/*",
                        "action": "*",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    }
                ]
            }
        ]

        # Load policies into the framework
        for policy_engine in self.security_framework.policy_engines.values():
            if hasattr(policy_engine, 'load_policies'):
                await policy_engine.load_policies(policies)
                break

        logger.info("Basic policies loaded into security framework")

    def setup_routes(self) -> None:
        """Setup API routes with security enforcement"""

        security = HTTPBearer()

        @self.app.get("/api/v1/users")
        async def list_users():
            """List users - requires user or admin role"""
            # Demonstrate authorization check
            decision = await self.security_framework.authorize(
                self.test_principal,
                "/api/v1/users",
                "GET"
            )

            if not decision.allowed:
                raise HTTPException(status_code=403, detail=f"Access denied: {decision.reason}")

            return {"users": ["alice", "bob"], "decision": decision.reason}

        @self.app.get("/api/v1/admin/stats")
        async def get_admin_stats():
            """Get admin statistics - requires admin role"""
            # Demonstrate authorization check for admin-only resource
            decision = await self.security_framework.authorize(
                self.test_principal,
                "/api/v1/admin/stats",
                "GET"
            )

            if not decision.allowed:
                raise HTTPException(status_code=403, detail=f"Access denied: {decision.reason}")

            return {
                "total_users": 42,
                "active_sessions": len(self.security_framework.active_sessions),
                "policy_evaluations": self.security_framework.metrics["policy_evaluations"],
                "decision": decision.reason
            }

        @self.app.get("/api/v1/security/status")
        async def get_security_status():
            """Get security framework status"""
            return {
                "framework_initialized": self.security_framework is not None,
                "identity_providers": list(self.security_framework.identity_providers.keys()) if self.security_framework else [],
                "policy_engines": list(self.security_framework.policy_engines.keys()) if self.security_framework else [],
                "active_sessions": len(self.security_framework.active_sessions) if self.security_framework else 0,
                "metrics": self.security_framework.metrics if self.security_framework else {}
            }

        @self.app.get("/health")
        async def health():
            """Health check"""
            return {"status": "healthy", "security_initialized": self.security_framework is not None}

async def main():
    """Run the basic example"""

    global example_instance
    example_instance = BasicSecurityExample()

    try:
        await example_instance.initialize_security()
        example_instance.setup_routes()

        logger.info("Basic security example ready!")
        logger.info("Available endpoints:")
        logger.info("  GET /api/v1/users - List users (requires user/admin role)")
        logger.info("  GET /api/v1/admin/stats - Admin statistics (requires admin role)")
        logger.info("  GET /api/v1/security/status - Security framework status")
        logger.info("  GET /health - Health check")
        logger.info("")
        logger.info("To run: uvicorn basic_security_example:example_instance.app --reload")

    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise

# Global instance for uvicorn
example_instance = None

if __name__ == "__main__":
    asyncio.run(main())
