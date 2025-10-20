"""
Security service for the PetStore Domain plugin.

This service manages the initialization and coordination of all security components
including Vault integration, policy engines, and authentication/authorization.
"""
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import PetstoreDomainConfig

# Import Marty MSF unified security framework (using bridge during migration)
from marty_msf.security.bridge import (
    UnifiedSecurityFrameworkBridge as UnifiedSecurityFramework,
)
from marty_msf.security.interfaces import SecurityContext, SecurityPrincipal
from marty_msf.security.unified_framework import (
    SecurityPolicyType,
    create_unified_security_framework,
)

SECURITY_AVAILABLE = True

logger = logging.getLogger(__name__)

class PetStoreSecurityService:
    """
    Main security service for the PetStore domain.

    Coordinates all security-related functionality including:
    - HashiCorp Vault integration
    - Policy-based authorization
    - Secret management
    - Certificate management
    """

    def __init__(self, config: PetstoreDomainConfig):
        self.config = config
        self.security_framework = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize unified security framework"""
        if self._initialized:
            return

        logger.info("Initializing PetStore security service with unified framework...")

        try:
            # Configuration for unified security framework
            security_config = {
                "default_identity_provider": "local",
                "policy_cache_ttl": 300,
                "audit_enabled": True,
                "service_mesh_enabled": False,
                "compliance_scanning_enabled": False
            }

            # Initialize unified security framework
            self.security_framework = await create_unified_security_framework(security_config)

            if not self.security_framework:
                raise Exception("Failed to initialize unified security framework")

            # Load default policies
            await self._load_default_policies()

            self._initialized = True
            logger.info("Security service initialized successfully with unified framework")

        except Exception as e:
            logger.error(f"Failed to initialize security service: {e}")
            raise

    async def _initialize_vault(self) -> None:
        """Initialize HashiCorp Vault client - DEPRECATED, now handled by unified framework"""
        logger.info("Vault integration now handled by unified security framework")

    async def _initialize_secret_manager(self) -> None:
        """Initialize secret manager - DEPRECATED, now handled by unified framework"""
        logger.info("Secret management now handled by unified security framework")

    async def _initialize_policy_manager(self) -> None:
        """Initialize policy manager - DEPRECATED, now handled by unified framework"""
        logger.info("Policy management now handled by unified security framework")

    async def _configure_opa(self) -> None:
        """Configure Open Policy Agent"""
        try:
            # OPA configuration would be done here
            # For now, just log that it's configured
            logger.info(f"OPA configured: {self.config.opa_url}")
        except Exception as e:
            logger.error(f"Failed to configure OPA: {e}")

    async def _configure_oso(self) -> None:
        """Configure Oso policy engine"""
        try:
            # Load Oso policy file if it exists
            if self.config.oso_policy_file:
                policy_path = Path(self.config.oso_policy_file)
                if policy_path.exists():
                    logger.info(f"Oso policy loaded from: {policy_path}")
                else:
                    logger.warning(f"Oso policy file not found: {policy_path}")
        except Exception as e:
            logger.error(f"Failed to configure Oso: {e}")

    async def _setup_default_secrets(self) -> None:
        """Set up default secrets for the petstore domain"""
        if not self.secret_manager:
            return

        try:
            # JWT signing key
            jwt_secret = self.config.jwt_secret_key or self.config.secret_key
            if jwt_secret and jwt_secret != "dev-secret-key-change-in-production":
                await self.secret_manager.store_secret("jwt/signing_key", jwt_secret)

            # API keys for external services
            default_api_keys = {
                "psk-demo-key": {
                    "service_name": "demo_service",
                    "roles": ["service"],
                    "description": "Demo API key for testing"
                }
            }
            await self.secret_manager.store_secret("api_keys/valid_keys", json.dumps(default_api_keys))

            logger.info("Default secrets configured")

        except Exception as e:
            logger.error(f"Failed to setup default secrets: {e}")

    async def _load_default_policies(self) -> None:
        """Load default authorization policies for the petstore domain"""
        if not self.policy_manager:
            return

        try:
            # PetStore RBAC policy
            petstore_rbac = {
                "id": "petstore_rbac",
                "name": "PetStore RBAC Policy",
                "rules": [
                    {
                        "resource": "/api/v1/pets/public",
                        "action": "GET",
                        "principal": {"type": "*"},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/pets/*",
                        "action": "GET",
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/pets/*",
                        "action": ["POST", "PUT", "DELETE"],
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*",
                        "action": "GET",
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*",
                        "action": ["POST", "PUT"],
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*/cancel",
                        "action": "POST",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/admin/*",
                        "action": "*",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    }
                ]
            }

            await self.policy_manager.load_policy("petstore_rbac", json.dumps(petstore_rbac))

            # Service-to-service policies
            service_policy = {
                "id": "service_to_service",
                "name": "Service-to-Service Communication Policy",
                "rules": [
                    {
                        "resource": "/api/v1/internal/*",
                        "action": "*",
                        "principal": {"type": "service"},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/events/*",
                        "action": ["POST"],
                        "principal": {"type": "service", "roles": ["event_publisher"]},
                        "effect": "allow"
                    }
                ]
            }

            await self.policy_manager.load_policy("service_policy", json.dumps(service_policy))

            logger.info("Default policies loaded")

        except Exception as e:
            logger.error(f"Failed to load default policies: {e}")

    async def evaluate_authorization(
        self,
        principal: dict[str, Any],
        action: str,
        resource: str,
        environment: dict[str, Any] | None = None
    ) -> bool:
        """
        Evaluate authorization request using the policy manager

        Args:
            principal: User/service principal information
            action: HTTP method or action being performed
            resource: Resource being accessed
            environment: Additional context information

        Returns:
            True if authorized, False otherwise
        """
        if not self.policy_manager:
            # If no policy manager, allow for development
            logger.warning("No policy manager available, allowing request")
            return True

        try:
            auth_request = AuthorizationRequest(
                principal=principal,
                action=action,
                resource=resource,
                environment=environment or {}
            )

            result = await self.policy_manager.evaluate(auth_request)
            return getattr(result, 'allowed', False)

        except Exception as e:
            logger.error(f"Authorization evaluation failed: {e}")
            return False  # Deny on error

    async def get_secret(self, key: str) -> str | None:
        """Get secret from secret manager"""
        if not self.secret_manager:
            return None

        try:
            return await self.secret_manager.get_secret(key)
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
            return None

    async def health_check(self) -> dict[str, Any]:
        """Get health status of all security components"""
        health = {
            "security_service": "healthy",
            "components": {}
        }

        try:
            # Check Vault
            if self.vault_client:
                vault_healthy = await self.vault_client.health_check()
                health["components"]["vault"] = "healthy" if vault_healthy else "unhealthy"
            else:
                health["components"]["vault"] = "disabled"

            # Check policy manager
            if self.policy_manager:
                policy_healthy = await self.policy_manager.health_check()
                health["components"]["policy_manager"] = "healthy" if policy_healthy else "unhealthy"
            else:
                health["components"]["policy_manager"] = "disabled"

            # Check secret manager
            if self.secret_manager:
                health["components"]["secret_manager"] = "healthy"
            else:
                health["components"]["secret_manager"] = "disabled"

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health["security_service"] = "degraded"

        return health

    async def cleanup(self) -> None:
        """Cleanup security service resources"""
        try:
            if self.vault_client:
                # Cleanup vault client if needed
                pass

            if self.policy_manager:
                # Cleanup policy manager if needed
                pass

            logger.info("Security service cleanup completed")

        except Exception as e:
            logger.error(f"Security service cleanup failed: {e}")


# Global security service instance
_security_service: PetStoreSecurityService | None = None

async def get_security_service(config: PetstoreDomainConfig | None = None) -> PetStoreSecurityService:
    """
    Get or create the global security service instance

    Args:
        config: Configuration object (required for first call)

    Returns:
        Security service instance
    """
    global _security_service

    if _security_service is None:
        if config is None:
            raise ValueError("Config required for security service initialization")

        _security_service = PetStoreSecurityService(config)
        await _security_service.initialize()

    return _security_service

async def cleanup_security_service() -> None:
    """Cleanup the global security service"""
    global _security_service

    if _security_service:
        await _security_service.cleanup()
        _security_service = None
