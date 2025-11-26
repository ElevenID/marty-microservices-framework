"""
Istio Rate Limiter Adapter

Istio EnvoyFilter-based rate limiter for DDoS protection and coarse-grained limits.
This works in coordination with application-level rate limiting.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf_new.core.security.domain.models.rate_limit import RateLimitQuota, RateLimitResult
from mmf_new.core.security.domain.services.rate_limiting import RateLimitCoordinationService

logger = logging.getLogger(__name__)


class IstioRateLimiter:
    """Istio-based rate limiter for service mesh level protection."""

    def __init__(
        self,
        kubernetes_client: Any,  # Will be properly typed when K8s client is implemented
        namespace: str = "default",
        istio_namespace: str = "istio-system",
        safety_multiplier: float = 2.0,
    ):
        self.k8s_client = kubernetes_client
        self.namespace = namespace
        self.istio_namespace = istio_namespace
        self.coordination_service = RateLimitCoordinationService(safety_multiplier)

    async def apply_rate_limit_policy(
        self,
        service_name: str,
        app_limits: dict[str, int],
        user_authenticated: bool = False,
    ) -> bool:
        """
        Apply Istio EnvoyFilter for rate limiting.

        Args:
            service_name: Name of the service to apply limits to
            app_limits: Application-level rate limits (endpoint -> limit)
            user_authenticated: Whether this is for authenticated users

        Returns:
            True if policy was applied successfully
        """
        try:
            # Calculate Istio limits based on app limits
            istio_limits = {}
            for endpoint, app_limit in app_limits.items():
                istio_limits[endpoint] = self.coordination_service.calculate_istio_limit(
                    app_limit
                )

            # Create EnvoyFilter for rate limiting
            envoy_filter = self._create_rate_limit_envoy_filter(
                service_name, istio_limits, user_authenticated
            )

            # Apply via Kubernetes API
            if self.k8s_client:
                return await self.k8s_client.apply_resource(envoy_filter)
            else:
                logger.warning("No Kubernetes client available, skipping Istio rate limit application")
                return False

        except Exception as e:
            logger.error("Error applying Istio rate limit policy: %s", str(e))
            return False

    async def remove_rate_limit_policy(self, service_name: str) -> bool:
        """Remove Istio rate limit policy for a service."""
        try:
            if self.k8s_client:
                return await self.k8s_client.delete_resource(
                    "EnvoyFilter",
                    f"{service_name}-rate-limit",
                    self.namespace,
                )
            return False
        except Exception as e:
            logger.error("Error removing Istio rate limit policy: %s", str(e))
            return False

    def should_apply_istio_limits(
        self, app_result: RateLimitResult, user_authenticated: bool
    ) -> bool:
        """Check if Istio limits should be applied based on app result."""
        return self.coordination_service.should_apply_istio_limit(
            app_result, user_authenticated
        )

    def _create_rate_limit_envoy_filter(
        self,
        service_name: str,
        limits: dict[str, int],
        user_authenticated: bool,
    ) -> dict[str, Any]:
        """Create EnvoyFilter resource for rate limiting."""
        # Create rate limit configuration
        rate_limit_config = {
            "domain": f"{service_name}-rate-limit",
            "descriptors": [],
        }

        # Add descriptors for each endpoint
        for endpoint, limit in limits.items():
            descriptor = {
                "key": "header_match",
                "value": endpoint,
                "rate_limit": {
                    "unit": "minute",
                    "requests_per_unit": limit,
                },
            }

            # Add user authentication context if relevant
            if user_authenticated:
                descriptor["descriptors"] = [
                    {
                        "key": "authenticated",
                        "value": "true",
                        "rate_limit": {
                            "unit": "minute",
                            "requests_per_unit": limit,
                        },
                    }
                ]

            rate_limit_config["descriptors"].append(descriptor)

        # Create EnvoyFilter resource
        envoy_filter = {
            "apiVersion": "networking.istio.io/v1alpha3",
            "kind": "EnvoyFilter",
            "metadata": {
                "name": f"{service_name}-rate-limit",
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "marty-security",
                    "marty.io/rate-limit-type": "istio-coordination",
                },
            },
            "spec": {
                "workloadSelector": {
                    "labels": {
                        "app": service_name,
                    }
                },
                "configPatches": [
                    {
                        "applyTo": "HTTP_FILTER",
                        "match": {
                            "context": "SIDECAR_INBOUND",
                            "listener": {
                                "filterChain": {
                                    "filter": {
                                        "name": "envoy.filters.network.http_connection_manager"
                                    }
                                }
                            }
                        },
                        "patch": {
                            "operation": "INSERT_BEFORE",
                            "value": {
                                "name": "envoy.filters.http.local_ratelimit",
                                "typed_config": {
                                    "@type": "type.googleapis.com/udpa.type.v1.TypedStruct",
                                    "type_url": "type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit",
                                    "value": {
                                        "stat_prefix": f"{service_name}_rate_limiter",
                                        "token_bucket": {
                                            "max_tokens": max(limits.values(), default=100),
                                            "tokens_per_fill": max(limits.values(), default=100),
                                            "fill_interval": "60s",
                                        },
                                        "filter_enabled": {
                                            "runtime_key": f"{service_name}_rate_limit_enabled",
                                            "default_value": {
                                                "numerator": 100,
                                                "denominator": "HUNDRED",
                                            },
                                        },
                                        "filter_enforced": {
                                            "runtime_key": f"{service_name}_rate_limit_enforced",
                                            "default_value": {
                                                "numerator": 100,
                                                "denominator": "HUNDRED",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    }
                ],
            },
        }

        return envoy_filter

    async def get_rate_limit_status(self, service_name: str) -> dict[str, Any] | None:
        """Get current rate limit status from Istio."""
        try:
            if self.k8s_client:
                envoy_filter = await self.k8s_client.get_resource(
                    "EnvoyFilter",
                    f"{service_name}-rate-limit",
                    self.namespace,
                )

                if envoy_filter:
                    return {
                        "service": service_name,
                        "namespace": self.namespace,
                        "status": "active",
                        "envoy_filter": envoy_filter,
                    }

            return None
        except Exception as e:
            logger.error("Error getting Istio rate limit status: %s", str(e))
            return None

    async def health_check(self) -> bool:
        """Check if Istio rate limiter is healthy."""
        try:
            # Check if we can communicate with Kubernetes API
            if self.k8s_client:
                return await self.k8s_client.health_check()
            return False
        except Exception as e:
            logger.error("Istio rate limiter health check failed: %s", str(e))
            return False