"""
Istio Service Mesh Manager Adapter

Implementation of IServiceMeshManager for Istio service mesh.
"""

import json
import logging
import subprocess
import yaml
from datetime import datetime
from typing import Any

from ...domain.config import ServiceMeshConfig
from ...domain.models.service_mesh import (
    ServiceMeshPolicy,
    ServiceMeshStatus,
    ServiceMeshMetrics,
    PolicySyncResult,
    NetworkSegment,
    PolicyType,
    MTLSMode,
    MeshType,
)
from ...ports.service_mesh import IServiceMeshManager

logger = logging.getLogger(__name__)


class IstioMeshManager(IServiceMeshManager):
    """
    Istio service mesh manager implementation.

    Manages Istio security policies via kubectl.
    """

    def __init__(self, config: ServiceMeshConfig):
        """
        Initialize Istio mesh manager.

        Args:
            config: Service mesh configuration
        """
        self.config = config

    async def _run_kubectl(self, args: list[str], input_data: str | None = None) -> str:
        """Run kubectl command."""
        cmd = [self.config.kubectl_cmd] + args

        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input=input_data)

            if process.returncode != 0:
                logger.error("kubectl command failed: %s", stderr)
                raise RuntimeError(f"kubectl failed: {stderr}")

            return stdout
        except Exception as e:
            logger.error("Error running kubectl: %s", e)
            raise

    async def apply_policy(self, policy: ServiceMeshPolicy) -> bool:
        """Apply a security policy to the service mesh."""
        manifest = policy.to_kubernetes_manifest()
        yaml_manifest = yaml.dump(manifest)

        try:
            await self._run_kubectl(["apply", "-f", "-"], input_data=yaml_manifest)
            logger.info("Applied policy %s in namespace %s", policy.name, policy.namespace)
            return True
        except Exception as e:
            logger.error("Failed to apply policy %s: %s", policy.name, e)
            return False

    async def apply_policies(self, policies: list[ServiceMeshPolicy]) -> PolicySyncResult:
        """Apply multiple security policies to the service mesh."""
        success_count = 0
        failed_policies = []

        for policy in policies:
            if await self.apply_policy(policy):
                success_count += 1
            else:
                failed_policies.append(policy.name)

        return PolicySyncResult(
            success=len(failed_policies) == 0,
            policies_applied=success_count,
            policies_failed=len(failed_policies),
            errors=failed_policies,
            metadata={"message": f"Applied {success_count} policies, {len(failed_policies)} failed"}
        )

    async def remove_policy(self, policy_name: str, namespace: str) -> bool:
        """Remove a policy from the service mesh."""
        # We need to know the kind to delete. Since we don't have the policy object,
        # we might need to try deleting all possible kinds or look it up first.
        # For simplicity, let's assume we look it up or try common kinds.
        # Or better, the caller should provide the type, but the interface doesn't support it.
        # Let's try to find it first.

        policy = await self.get_policy(policy_name, namespace)
        if not policy:
            return False

        manifest = policy.to_kubernetes_manifest()
        kind = manifest["kind"]

        try:
            await self._run_kubectl(["delete", kind, policy_name, "-n", namespace])
            logger.info("Deleted policy %s in namespace %s", policy_name, namespace)
            return True
        except Exception as e:
            logger.error("Failed to delete policy %s: %s", policy_name, e)
            return False

    async def get_policy(self, policy_name: str, namespace: str) -> ServiceMeshPolicy | None:
        """Get a policy from the service mesh."""
        # Try to find the policy among supported kinds
        kinds = [
            "AuthorizationPolicy",
            "PeerAuthentication",
            "RequestAuthentication",
            "EnvoyFilter",
            "NetworkPolicy"
        ]

        for kind in kinds:
            try:
                output = await self._run_kubectl(
                    ["get", kind, policy_name, "-n", namespace, "-o", "json"]
                )
                data = json.loads(output)

                # Convert back to ServiceMeshPolicy
                # This requires mapping back from K8s manifest to our model
                # For now, we'll return a partial object or implement a proper mapper
                # Let's implement a basic mapper

                policy_type_map = {
                    "AuthorizationPolicy": PolicyType.AUTHORIZATION,
                    "PeerAuthentication": PolicyType.PEER_AUTHENTICATION,
                    "RequestAuthentication": PolicyType.REQUEST_AUTHENTICATION,
                    "EnvoyFilter": PolicyType.RATE_LIMIT,
                    "NetworkPolicy": PolicyType.NETWORK_POLICY
                }

                return ServiceMeshPolicy(
                    name=data["metadata"]["name"],
                    policy_type=policy_type_map.get(kind, PolicyType.AUTHORIZATION),
                    namespace=data["metadata"]["namespace"],
                    description="Imported from cluster",
                    metadata=data["metadata"].get("labels", {}),
                    # Rules extraction is complex and depends on kind
                    rules=[],
                    enabled=True
                )
            except Exception:
                continue

        return None

    async def list_policies(self, namespace: str | None = None) -> list[ServiceMeshPolicy]:
        """List all policies in the service mesh."""
        # Similar to get_policy but for all kinds and list
        policies = []
        ns_args = ["-n", namespace] if namespace else ["-A"]

        kinds = [
            "AuthorizationPolicy",
            "PeerAuthentication",
            "RequestAuthentication",
            "EnvoyFilter",
            "NetworkPolicy"
        ]

        for kind in kinds:
            try:
                output = await self._run_kubectl(
                    ["get", kind] + ns_args + ["-o", "json"]
                )
                data = json.loads(output)

                for item in data.get("items", []):
                    # Convert to ServiceMeshPolicy (simplified)
                    policies.append(ServiceMeshPolicy(
                        name=item["metadata"]["name"],
                        policy_type=PolicyType.AUTHORIZATION,  # Placeholder
                        namespace=item["metadata"]["namespace"],
                        description="Imported from cluster",
                        enabled=True
                    ))
            except Exception:
                continue

        return policies

    async def enforce_mtls(
        self,
        namespace: str,
        services: list[str] | None = None,
        strict_mode: bool = True,
    ) -> bool:
        """Enforce mTLS for services."""
        mode = "STRICT" if strict_mode else "PERMISSIVE"

        if not services:
            # Namespace-wide policy
            policy = ServiceMeshPolicy(
                name="default",
                policy_type=PolicyType.PEER_AUTHENTICATION,
                namespace=namespace,
                description=f"Namespace-wide mTLS {mode}",
                metadata={"mtls_mode": mode},
                rules=[]
            )
            return await self.apply_policy(policy)
        else:
            # Per-service policies
            success = True
            for service in services:
                policy = ServiceMeshPolicy(
                    name=f"{service}-mtls",
                    policy_type=PolicyType.PEER_AUTHENTICATION,
                    namespace=namespace,
                    description=f"mTLS {mode} for {service}",
                    selector={"app": service},
                    metadata={"mtls_mode": mode},
                    rules=[]
                )
                if not await self.apply_policy(policy):
                    success = False
            return success

    async def create_network_segment(self, segment: NetworkSegment) -> PolicySyncResult:
        """Create a network segment with associated policies."""
        policies = []

        # 1. Network Policy
        policies.append(segment.to_network_policy())

        # 2. Authorization Policies
        policies.extend(segment.to_authorization_policies())

        return await self.apply_policies(policies)

    async def sync_authorization_policies(
        self,
        app_policies: list[dict[str, Any]],
    ) -> PolicySyncResult:
        """Sync application-level authorization policies to service mesh."""
        # Convert app policies to ServiceMeshPolicy objects
        mesh_policies = []
        for _ in app_policies:
            # Mapping logic here
            pass

        return await self.apply_policies(mesh_policies)

    async def get_mesh_status(self) -> ServiceMeshStatus:
        """Get service mesh status information."""
        # Check Istiod status
        try:
            output = await self._run_kubectl(
                ["get", "pod", "-n", self.config.istio_namespace, "-l", "app=istiod", "-o", "json"]
            )
            data = json.loads(output)
            items = data.get("items", [])

            is_healthy = len(items) > 0 and all(
                status["phase"] == "Running" for status in [i["status"] for i in items]
            )

            return ServiceMeshStatus(
                mesh_type=MeshType.ISTIO,
                installed=is_healthy,
                version="unknown",  # Could parse from image tag
                components={"istiod": "healthy" if is_healthy else "unhealthy"},
                policies_applied=0,  # Could count policies
                last_sync=datetime.utcnow(),
                health_status="healthy" if is_healthy else "unhealthy"
            )
        except Exception as e:
            logger.error("Failed to get mesh status: %s", e)
            return ServiceMeshStatus(
                mesh_type=MeshType.ISTIO,
                installed=False,
                version="unknown",
                components={},
                policies_applied=0,
                last_sync=datetime.utcnow(),
                health_status="unknown"
            )

    async def get_metrics(self) -> ServiceMeshMetrics:
        """Get service mesh metrics."""
        return ServiceMeshMetrics()

    async def supports_feature(self, feature: str) -> bool:
        """Check if service mesh supports a specific feature."""
        supported = {
            "mtls": True,
            "authorization": True,
            "rate_limit": True,
            "observability": True
        }
        return supported.get(feature, False)

    async def health_check(self) -> bool:
        """Check if service mesh is healthy."""
        status = await self.get_mesh_status()
        return status.is_healthy
