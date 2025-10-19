"""
Istio Service Mesh Security Integration

Provides real-time security policy enforcement at the service mesh level
integrating with the unified security framework for comprehensive protection.
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from ..interfaces import ServiceMeshSecurityManager

logger = logging.getLogger(__name__)


class IstioSecurityManager(ServiceMeshSecurityManager):
    """Istio service mesh security manager"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.namespace = config.get("namespace", "default")
        self.istio_namespace = config.get("istio_namespace", "istio-system")
        self.kubectl_cmd = config.get("kubectl_cmd", "kubectl")

        # Security policy templates
        self.policy_templates = self._load_policy_templates()

        # Status tracking
        self.applied_policies = {}
        self.mesh_status = {"initialized": False, "policies_applied": 0}

    async def apply_traffic_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Apply security policies to Istio service mesh traffic"""
        try:
            success_count = 0

            for policy in policies:
                policy_type = policy.get("type")

                if policy_type == "authorization":
                    if await self._apply_authorization_policy(policy):
                        success_count += 1
                elif policy_type == "authentication":
                    if await self._apply_authentication_policy(policy):
                        success_count += 1
                elif policy_type == "mtls":
                    if await self._apply_mtls_policy(policy):
                        success_count += 1
                elif policy_type == "rate_limit":
                    if await self._apply_rate_limit_policy(policy):
                        success_count += 1
                else:
                    logger.warning(f"Unknown policy type: {policy_type}")

            self.mesh_status["policies_applied"] = success_count

            if success_count == len(policies):
                logger.info(f"Successfully applied all {success_count} Istio policies")
                return True
            else:
                logger.warning(f"Applied {success_count}/{len(policies)} Istio policies")
                return False

        except Exception as e:
            logger.error(f"Failed to apply Istio traffic policies: {e}")
            return False

    async def get_mesh_status(self) -> dict[str, Any]:
        """Get current Istio service mesh security status"""
        try:
            # Check if Istio is installed
            istio_installed = await self._check_istio_installation()

            # Get policy status
            policy_status = await self._get_policy_status()

            # Get mTLS status
            mtls_status = await self._get_mtls_status()

            status = {
                "mesh_type": "istio",
                "namespace": self.namespace,
                "istio_namespace": self.istio_namespace,
                "istio_installed": istio_installed,
                "initialized": self.mesh_status["initialized"],
                "policies_applied": self.mesh_status["policies_applied"],
                "policy_status": policy_status,
                "mtls_status": mtls_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            return status

        except Exception as e:
            logger.error(f"Failed to get Istio mesh status: {e}")
            return {"error": str(e)}

    async def enforce_mTLS(self, services: list[str]) -> bool:
        """Enforce mutual TLS for specified services"""
        try:
            for service in services:
                peer_auth_policy = {
                    "apiVersion": "security.istio.io/v1beta1",
                    "kind": "PeerAuthentication",
                    "metadata": {
                        "name": f"{service}-mtls",
                        "namespace": self.namespace
                    },
                    "spec": {
                        "selector": {
                            "matchLabels": {
                                "app": service
                            }
                        },
                        "mtls": {
                            "mode": "STRICT"
                        }
                    }
                }

                if not await self._apply_k8s_resource(peer_auth_policy):
                    logger.error(f"Failed to apply mTLS policy for service {service}")
                    return False

            logger.info(f"Successfully enforced mTLS for {len(services)} services")
            return True

        except Exception as e:
            logger.error(f"Failed to enforce mTLS: {e}")
            return False

    # Private methods

    async def _apply_authorization_policy(self, policy: dict[str, Any]) -> bool:
        """Apply Istio AuthorizationPolicy"""
        try:
            service_name = policy.get("service")
            rules = policy.get("rules", [])

            auth_policy = {
                "apiVersion": "security.istio.io/v1beta1",
                "kind": "AuthorizationPolicy",
                "metadata": {
                    "name": f"{service_name}-authz",
                    "namespace": self.namespace
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app": service_name
                        }
                    },
                    "rules": self._convert_to_istio_auth_rules(rules)
                }
            }

            return await self._apply_k8s_resource(auth_policy)

        except Exception as e:
            logger.error(f"Failed to apply authorization policy: {e}")
            return False

    async def _apply_authentication_policy(self, policy: dict[str, Any]) -> bool:
        """Apply Istio RequestAuthentication"""
        try:
            service_name = policy.get("service")
            jwt_config = policy.get("jwt", {})

            req_auth_policy = {
                "apiVersion": "security.istio.io/v1beta1",
                "kind": "RequestAuthentication",
                "metadata": {
                    "name": f"{service_name}-jwt",
                    "namespace": self.namespace
                },
                "spec": {
                    "selector": {
                        "matchLabels": {
                            "app": service_name
                        }
                    },
                    "jwtRules": [
                        {
                            "issuer": jwt_config.get("issuer"),
                            "jwksUri": jwt_config.get("jwks_uri"),
                            "audiences": jwt_config.get("audiences", [])
                        }
                    ]
                }
            }

            return await self._apply_k8s_resource(req_auth_policy)

        except Exception as e:
            logger.error(f"Failed to apply authentication policy: {e}")
            return False

    async def _apply_mtls_policy(self, policy: dict[str, Any]) -> bool:
        """Apply Istio PeerAuthentication for mTLS"""
        try:
            services = policy.get("services", [])
            mode = policy.get("mode", "STRICT")

            for service in services:
                peer_auth_policy = {
                    "apiVersion": "security.istio.io/v1beta1",
                    "kind": "PeerAuthentication",
                    "metadata": {
                        "name": f"{service}-peer-auth",
                        "namespace": self.namespace
                    },
                    "spec": {
                        "selector": {
                            "matchLabels": {
                                "app": service
                            }
                        },
                        "mtls": {
                            "mode": mode
                        }
                    }
                }

                if not await self._apply_k8s_resource(peer_auth_policy):
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to apply mTLS policy: {e}")
            return False

    async def _apply_rate_limit_policy(self, policy: dict[str, Any]) -> bool:
        """Apply Istio rate limiting via EnvoyFilter"""
        try:
            service_name = policy.get("service")
            rate_limit = policy.get("rate_limit", {})

            envoy_filter = {
                "apiVersion": "networking.istio.io/v1alpha3",
                "kind": "EnvoyFilter",
                "metadata": {
                    "name": f"{service_name}-rate-limit",
                    "namespace": self.namespace
                },
                "spec": {
                    "workloadSelector": {
                        "labels": {
                            "app": service_name
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
                                            "stat_prefix": "local_rate_limiter",
                                            "token_bucket": {
                                                "max_tokens": rate_limit.get("max_tokens", 100),
                                                "tokens_per_fill": rate_limit.get("tokens_per_fill", 10),
                                                "fill_interval": rate_limit.get("fill_interval", "60s")
                                            },
                                            "filter_enabled": {
                                                "runtime_key": "local_rate_limit_enabled",
                                                "default_value": {
                                                    "numerator": 100,
                                                    "denominator": "HUNDRED"
                                                }
                                            },
                                            "filter_enforced": {
                                                "runtime_key": "local_rate_limit_enforced",
                                                "default_value": {
                                                    "numerator": 100,
                                                    "denominator": "HUNDRED"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            }

            return await self._apply_k8s_resource(envoy_filter)

        except Exception as e:
            logger.error(f"Failed to apply rate limit policy: {e}")
            return False

    async def _apply_k8s_resource(self, resource: dict[str, Any]) -> bool:
        """Apply Kubernetes resource using kubectl"""
        try:
            # Create temporary file for the resource
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(resource, f, default_flow_style=False)
                temp_file = f.name

            try:
                # Apply resource using kubectl
                result = await asyncio.create_subprocess_exec(
                    self.kubectl_cmd, 'apply', '-f', temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await result.communicate()

                if result.returncode == 0:
                    logger.info(f"Successfully applied {resource['kind']}: {resource['metadata']['name']}")
                    return True
                else:
                    logger.error(f"Failed to apply resource: {stderr.decode()}")
                    return False

            finally:
                # Clean up temporary file
                Path(temp_file).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to apply Kubernetes resource: {e}")
            return False

    async def _check_istio_installation(self) -> bool:
        """Check if Istio is installed in the cluster"""
        try:
            result = await asyncio.create_subprocess_exec(
                self.kubectl_cmd, 'get', 'namespace', self.istio_namespace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await result.communicate()
            return result.returncode == 0

        except Exception:
            return False

    async def _get_policy_status(self) -> dict[str, Any]:
        """Get status of applied security policies"""
        try:
            policy_types = ["AuthorizationPolicy", "RequestAuthentication", "PeerAuthentication"]
            status = {}

            for policy_type in policy_types:
                result = await asyncio.create_subprocess_exec(
                    self.kubectl_cmd, 'get', policy_type, '-n', self.namespace,
                    '-o', 'json',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, _ = await result.communicate()

                if result.returncode == 0:
                    policies_data = json.loads(stdout.decode())
                    status[policy_type] = len(policies_data.get("items", []))
                else:
                    status[policy_type] = 0

            return status

        except Exception as e:
            logger.error(f"Failed to get policy status: {e}")
            return {}

    async def _get_mtls_status(self) -> dict[str, Any]:
        """Get mTLS status for services"""
        try:
            # This would typically use istioctl or Istio APIs
            # For now, return basic status
            return {
                "enabled": True,
                "mode": "STRICT",
                "services_covered": 0
            }

        except Exception as e:
            logger.error(f"Failed to get mTLS status: {e}")
            return {"enabled": False}

    def _convert_to_istio_auth_rules(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert generic authorization rules to Istio format"""
        istio_rules = []

        for rule in rules:
            istio_rule = {}

            # Convert action
            if "action" in rule:
                istio_rule["to"] = [{"operation": {"methods": [rule["action"]]}}]

            # Convert principal conditions
            if "principal" in rule:
                when_conditions = []
                principal = rule["principal"]

                if "roles" in principal:
                    for role in principal["roles"]:
                        when_conditions.append({
                            "key": "request.auth.claims[roles]",
                            "values": [role]
                        })

                if when_conditions:
                    istio_rule["when"] = when_conditions

            # Convert resource
            if "resource" in rule:
                if "to" not in istio_rule:
                    istio_rule["to"] = [{}]
                istio_rule["to"][0]["operation"] = istio_rule["to"][0].get("operation", {})
                istio_rule["to"][0]["operation"]["paths"] = [rule["resource"]]

            istio_rules.append(istio_rule)

        return istio_rules

    def _load_policy_templates(self) -> dict[str, Any]:
        """Load Istio policy templates"""
        return {
            "authorization": {
                "template": "istio_authorization_policy.yaml",
                "required_fields": ["service", "rules"]
            },
            "authentication": {
                "template": "istio_request_authentication.yaml",
                "required_fields": ["service", "jwt"]
            },
            "mtls": {
                "template": "istio_peer_authentication.yaml",
                "required_fields": ["services"]
            },
            "rate_limit": {
                "template": "istio_envoy_filter.yaml",
                "required_fields": ["service", "rate_limit"]
            }
        }
