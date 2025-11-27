"""
OPA (Open Policy Agent) Integration

Integration with OPA for enterprise-grade policy evaluation.
OPA is the industry standard for policy as code in cloud-native environments.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union

import aiohttp
from marty_msf.core.enhanced_di import get_service

from ..abac import ABACContext, PolicyEffect
from ..exceptions import ExternalProviderError, PolicyEvaluationError
from .opa_service import OPAPolicyServiceWrapper

logger = logging.getLogger(__name__)


@dataclass
class PolicyEvaluationRequest:
    """Request for policy evaluation."""

    principal: dict[str, Any]
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyEvaluationResponse:
    """Response from policy evaluation."""

    decision: PolicyEffect
    allow: bool
    reason: str | None = None
    policy_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class OPAPolicyEngine:
    """Open Policy Agent (OPA) policy engine integration."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base_url = config.get("url", "http://localhost:8181")
        self.policy_path = config.get("policy_path", "v1/data/authz/allow")
        self.timeout = config.get("timeout", 5.0)
        self.session: aiohttp.ClientSession | None = None
        self.is_healthy = True
        self.last_error: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
        """Evaluate policy using OPA."""
        start_time = datetime.now()

        try:
            session = await self._get_session()

            # Prepare OPA input
            opa_input = {
                "input": {
                    "principal": request.principal,
                    "resource": request.resource,
                    "action": request.action,
                    "environment": request.environment,
                    **request.context,
                }
            }

            url = f"{self.base_url}/{self.policy_path}"

            async with session.post(url, json=opa_input) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise PolicyEvaluationError(
                        f"OPA returned status {response.status}: {error_text}", engine_type="OPA"
                    )

                result = await response.json()

                # Parse OPA response
                decision = result.get("result", False)
                allow = bool(decision) if isinstance(decision, bool) else False

                # Handle complex OPA responses
                if isinstance(decision, dict):
                    allow = decision.get("allow", False)
                    reason = decision.get("reason")
                    policy_id = decision.get("policy_id")
                else:
                    reason = f"OPA decision: {decision}"
                    policy_id = "opa_policy"

                evaluation_time = (datetime.now() - start_time).total_seconds() * 1000

                return PolicyEvaluationResponse(
                    decision=PolicyEffect.ALLOW if allow else PolicyEffect.DENY,
                    allow=allow,
                    reason=reason,
                    policy_id=policy_id,
                    evaluation_time_ms=evaluation_time,
                    metadata={"opa_result": result},
                )

        except aiohttp.ClientError as e:
            self.is_healthy = False
            self.last_error = str(e)
            raise ExternalProviderError(
                f"OPA connection failed: {e}", provider="OPA", provider_error=str(e)
            )
        except Exception as e:
            logger.error("OPA evaluation error: %s", e)
            raise PolicyEvaluationError(f"OPA evaluation failed: {e}", engine_type="OPA")

    async def health_check(self) -> bool:
        """Check OPA health."""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/health"

            async with session.get(url) as response:
                self.is_healthy = response.status == 200
                if not self.is_healthy:
                    self.last_error = f"Health check failed: {response.status}"
                return self.is_healthy

        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            return False

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def get_status(self) -> dict[str, Any]:
        """Get engine status."""
        return {
            "type": "OPA",
            "url": self.base_url,
            "policy_path": self.policy_path,
            "is_healthy": self.is_healthy,
            "last_error": self.last_error,
        }


class OPAPolicyService:
    """Service wrapper for OPA policy engine with configuration management."""

    def __init__(
        self, config: dict[str, Any] | None = None, service_config: dict[str, Any] | None = None
    ):
        # Load from service configuration if provided
        if service_config and not config:
            config = self._load_from_service_config(service_config)

        self.config = config or self._default_config()
        self.service_config = service_config
        self.engine = OPAPolicyEngine(self.config)
        self._initialized = False

    def _default_config(self) -> dict[str, Any]:
        """Default OPA configuration."""
        return {
            "url": "http://localhost:8181",
            "policy_path": "v1/data/authz/allow",
            "timeout": 5.0,
            "health_check_interval": 30.0,
        }

    def _load_from_service_config(self, service_config: dict[str, Any]) -> dict[str, Any]:
        """Load OPA configuration from service configuration."""
        opa_config = service_config.get("security", {}).get("opa", {})

        return {
            "url": opa_config.get("url", "http://localhost:8181"),
            "policy_path": opa_config.get("policy_path", "v1/data/authz/allow"),
            "timeout": opa_config.get("timeout", 5.0),
            "health_check_interval": opa_config.get("health_check_interval", 30.0),
        }

    async def initialize(self):
        """Initialize the policy service."""
        if self._initialized:
            return

        # Perform initial health check
        is_healthy = await self.engine.health_check()
        if not is_healthy:
            logger.warning("OPA initial health check failed: %s", self.engine.last_error)

        self._initialized = True
        logger.info("OPA Policy Service initialized: %s", self.config["url"])

    async def evaluate_policy(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResponse:
        """Evaluate policy for given request."""
        if not self._initialized:
            await self.initialize()

        request = PolicyEvaluationRequest(
            principal=principal,
            resource=resource,
            action=action,
            environment=environment or {},
            context=context or {},
        )

        return await self.engine.evaluate(request)

    async def health_check(self) -> bool:
        """Check service health."""
        return await self.engine.health_check()

    async def close(self):
        """Close the service and cleanup resources."""
        await self.engine.close()
        self._initialized = False

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive service status."""
        return {
            **self.engine.get_status(),
            "initialized": self._initialized,
            "config": {
                "url": self.config["url"],
                "policy_path": self.config["policy_path"],
                "timeout": self.config["timeout"],
            },
        }


# Service-based OPA policy service access


def get_policy_service(service_config: dict[str, Any] | None = None) -> OPAPolicyService:
    """Get OPA policy service from the DI container."""
    service = get_service(OPAPolicyServiceWrapper)
    return service.get_policy_service()


def configure_opa_service(
    url: str = "http://localhost:8181",
    policy_path: str = "v1/data/authz/allow",
    timeout: float = 5.0,
) -> OPAPolicyService:
    """Configure OPA policy service (not supported - use DI container instead)."""
    raise NotImplementedError(
        "configure_opa_service is not supported. Use the DI container to register OPAPolicyServiceWrapper instead."
    )


def create_policy_service_from_service_config(service_config: dict[str, Any]) -> OPAPolicyService:
    """Create a policy service from service configuration."""
    return OPAPolicyService(service_config=service_config)


def configure_policy_service(service_config: dict[str, Any]) -> OPAPolicyService:
    """Configure the policy service with service configuration (not supported)."""
    raise NotImplementedError(
        "configure_policy_service is not supported. Use the DI container to register OPAPolicyServiceWrapper instead."
    )


async def evaluate_policy(
    principal: dict[str, Any],
    resource: str,
    action: str,
    environment: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> PolicyEvaluationResponse:
    """Convenience function to evaluate policy using global service."""
    service = get_policy_service()
    return await service.evaluate_policy(
        principal=principal,
        resource=resource,
        action=action,
        environment=environment,
        context=context,
    )


__all__ = [
    "PolicyEvaluationRequest",
    "PolicyEvaluationResponse",
    "OPAPolicyEngine",
    "OPAPolicyService",
    "get_policy_service",
    "configure_opa_service",
    "evaluate_policy",
]
