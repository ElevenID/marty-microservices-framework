"""
Enhanced Service Mesh Manager with Unified Security Integration
Provides real-time security policy enforcement and service mesh deployment
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EnhancedServiceMeshManager:
    """
    Enhanced Service Mesh management with real-time security policy enforcement

    This manager handles multiple service mesh deployment, configuration, and integrates
    with the unified security framework for runtime policy enforcement and cross-mesh
    security policy synchronization.
    """

    def __init__(
        self,
        service_mesh_type: str = "istio",
        config: dict[str, Any] | None = None,
        security_manager: Any | None = None,
    ):
        """
        Initialize EnhancedServiceMeshManager with security integration

        Args:
            service_mesh_type: Primary type of service mesh (istio, linkerd)
            config: Service mesh configuration including multi-mesh settings
            security_manager: Unified security framework manager for policy enforcement
        """
        self.service_mesh_type = service_mesh_type.lower()
        self.config = config or {}
        self.security_manager = security_manager
        self.is_installed = False

        # Multi-mesh support
        self.multi_mesh_enabled = self.config.get("multi_mesh", {}).get("enabled", False)
        self.mesh_deployments: dict[str, dict[str, Any]] = {}
        self.policy_sync_enabled = self.config.get("multi_mesh", {}).get("policy_sync", True)
        self.cross_mesh_policies: dict[str, list[dict[str, Any]]] = {}

        self._check_installation()

    def _check_installation(self) -> None:
        """Check if the selected service mesh is available"""
        try:
            if self.service_mesh_type == "istio":
                result = subprocess.run(
                    ["istioctl", "version", "--remote=false"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.is_installed = result.returncode == 0
            elif self.service_mesh_type == "linkerd":
                result = subprocess.run(
                    ["linkerd", "version", "--client"], capture_output=True, text=True, check=False
                )
                self.is_installed = result.returncode == 0
            else:
                logger.warning(f"Unsupported service mesh type: {self.service_mesh_type}")
        except FileNotFoundError:
            logger.info(f"{self.service_mesh_type} CLI not found in PATH")
            self.is_installed = False

    async def deploy_service_mesh(
        self, namespace: str = "istio-system", security_policies: list[dict[str, Any]] | None = None
    ) -> bool:
        """
        Deploy service mesh with integrated security policies

        Args:
            namespace: Kubernetes namespace for service mesh
            security_policies: List of security policies to apply

        Returns:
            bool: True if deployment successful
        """
        try:
            if not self.is_installed:
                logger.error(f"{self.service_mesh_type} is not installed")
                return False

            # Deploy base service mesh
            success = await self._deploy_base_mesh(namespace)
            if not success:
                return False

            # Apply security policies if provided and security manager available
            if security_policies and self.security_manager:
                await self._apply_security_policies(security_policies, namespace)

            logger.info(f"{self.service_mesh_type} deployed successfully with security integration")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy service mesh: {e}")
            return False

    async def _deploy_base_mesh(self, namespace: str) -> bool:
        """Deploy the base service mesh installation"""
        if self.service_mesh_type == "istio":
            return await self._deploy_istio(namespace)
        elif self.service_mesh_type == "linkerd":
            return await self._deploy_linkerd(namespace)
        return False

    async def _deploy_istio(self, namespace: str) -> bool:
        """Deploy Istio service mesh"""
        try:
            # Install Istio with security features enabled
            cmd = [
                "istioctl",
                "install",
                "--set",
                "values.global.meshConfig.defaultConfig.proxyStatsMatcher.inclusionRegexps=.*outlier_detection.*",
                "--set",
                "values.pilot.env.EXTERNAL_ISTIOD=false",
                "--set",
                "values.global.meshConfig.defaultConfig.discoveryRefreshDelay=10s",
                "--set",
                "values.global.meshConfig.defaultConfig.proxyMetadata.ISTIO_META_DNS_CAPTURE=true",
                "-y",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("Istio installed successfully")
                # Enable automatic sidecar injection
                await self._enable_sidecar_injection(namespace)
                return True
            else:
                logger.error(f"Istio installation failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to deploy Istio: {e}")
            return False

    async def _deploy_linkerd(self, namespace: str) -> bool:
        """Deploy Linkerd service mesh"""
        try:
            # Pre-check
            check_cmd = ["linkerd", "check", "--pre"]
            process = await asyncio.create_subprocess_exec(
                *check_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Linkerd pre-check failed: {stderr.decode()}")
                return False

            # Install Linkerd
            install_cmd = ["linkerd", "install"]
            process = await asyncio.create_subprocess_exec(
                *install_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Apply the installation
                apply_cmd = ["kubectl", "apply", "-f", "-"]
                apply_process = await asyncio.create_subprocess_exec(
                    *apply_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await apply_process.communicate(input=stdout)

                if apply_process.returncode == 0:
                    logger.info("Linkerd installed successfully")
                    return True

            logger.error(f"Linkerd installation failed: {stderr.decode()}")
            return False

        except Exception as e:
            logger.error(f"Failed to deploy Linkerd: {e}")
            return False

    async def _enable_sidecar_injection(self, namespace: str) -> None:
        """Enable automatic sidecar injection for a namespace"""
        try:
            cmd = [
                "kubectl",
                "label",
                "namespace",
                namespace,
                "istio-injection=enabled",
                "--overwrite",
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            logger.info(f"Enabled sidecar injection for namespace: {namespace}")
        except Exception as e:
            logger.warning(f"Failed to enable sidecar injection: {e}")

    async def _apply_security_policies(
        self, security_policies: list[dict[str, Any]], namespace: str
    ) -> None:
        """Apply security policies through the unified security framework"""
        if not self.security_manager:
            logger.warning("No security manager available for policy enforcement")
            return

        try:
            # Get the appropriate service mesh security manager
            mesh_security = self.security_manager.get_service_mesh_manager(self.service_mesh_type)

            if mesh_security:
                for policy in security_policies:
                    await mesh_security.apply_traffic_policies([policy], namespace)

                # Enable mTLS for the namespace
                await mesh_security.enforce_mTLS(namespace, "STRICT")

                logger.info(f"Applied {len(security_policies)} security policies to {namespace}")
            else:
                logger.warning(f"No security manager available for {self.service_mesh_type}")

        except Exception as e:
            logger.error(f"Failed to apply security policies: {e}")

    async def enforce_runtime_policies(
        self, service_name: str, namespace: str, policies: list[dict[str, Any]]
    ) -> bool:
        """
        Enforce runtime security policies for a specific service

        Args:
            service_name: Name of the service
            namespace: Kubernetes namespace
            policies: List of policies to enforce

        Returns:
            bool: True if policies applied successfully
        """
        if not self.security_manager:
            logger.error("No security manager available for runtime policy enforcement")
            return False

        try:
            mesh_security = self.security_manager.get_service_mesh_manager(self.service_mesh_type)
            if not mesh_security:
                logger.error(f"No security manager for {self.service_mesh_type}")
                return False

            # Apply service-specific policies
            success = True
            for policy in policies:
                try:
                    # Enhance policy with service context
                    enhanced_policy = {
                        **policy,
                        "metadata": {
                            **policy.get("metadata", {}),
                            "target_service": service_name,
                            "namespace": namespace,
                        },
                    }

                    await mesh_security.apply_traffic_policies([enhanced_policy], namespace)
                    logger.info(
                        f"Applied runtime policy for service {service_name}: {policy.get('metadata', {}).get('name', 'unnamed')}"
                    )

                except Exception as policy_error:
                    logger.error(f"Failed to apply policy for {service_name}: {policy_error}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"Runtime policy enforcement failed: {e}")
            return False

    async def monitor_security_events(self, namespace: str = "default") -> list[dict[str, Any]]:
        """
        Monitor security events from the service mesh

        Args:
            namespace: Kubernetes namespace to monitor

        Returns:
            List of security events
        """
        events = []

        try:
            if self.service_mesh_type == "istio":
                events = await self._get_istio_security_events(namespace)
            elif self.service_mesh_type == "linkerd":
                events = await self._get_linkerd_security_events(namespace)

        except Exception as e:
            logger.error(f"Failed to monitor security events: {e}")

        return events

    async def _get_istio_security_events(self, namespace: str) -> list[dict[str, Any]]:
        """Get security events from Istio"""
        events = []

        try:
            # Get access logs from Envoy sidecars
            cmd = ["kubectl", "logs", "-l", "app=istio-proxy", "-n", namespace, "--tail=100"]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Parse access logs for security events
                log_lines = stdout.decode().split("\n")
                for line in log_lines:
                    if any(
                        indicator in line.lower()
                        for indicator in ["denied", "unauthorized", "forbidden"]
                    ):
                        events.append(
                            {
                                "timestamp": "now",  # Parse actual timestamp
                                "type": "security_violation",
                                "source": "istio",
                                "message": line.strip(),
                                "namespace": namespace,
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to get Istio security events: {e}")

        return events

    async def _get_linkerd_security_events(self, namespace: str) -> list[dict[str, Any]]:
        """Get security events from Linkerd"""
        events = []

        try:
            # Get Linkerd stats for security metrics
            cmd = ["linkerd", "stat", "deploy", "-n", namespace, "--output", "json"]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                stats_data = json.loads(stdout.decode())

                for stat in stats_data.get("rows", []):
                    # Check for security-related metrics
                    if stat.get("meshed", "") == "-":
                        events.append(
                            {
                                "timestamp": "now",
                                "type": "mesh_injection_missing",
                                "source": "linkerd",
                                "message": f"Service {stat.get('name')} is not meshed",
                                "namespace": namespace,
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to get Linkerd security events: {e}")

        return events

    def generate_deployment_script(self, service_name: str, config: dict | None = None) -> str:
        """
        Generate deployment script with enhanced security integration

        Args:
            service_name: Name of the service
            config: Service configuration

        Returns:
            Deployment script content
        """
        config = config or {}

        if self.service_mesh_type == "istio":
            return self._generate_istio_script(service_name, config)
        elif self.service_mesh_type == "linkerd":
            return self._generate_linkerd_script(service_name, config)
        else:
            return f"# Unsupported service mesh: {self.service_mesh_type}"

    def _generate_istio_script(self, service_name: str, config: dict) -> str:
        """Generate Istio deployment script with security policies"""
        security_config = config.get("security", {})

        script = f"""#!/bin/bash
# Enhanced Istio Deployment Script for {service_name}
# Generated by Marty Microservices Framework

set -e

echo "Deploying {service_name} with Istio service mesh and security policies..."

# Apply Kubernetes manifests
kubectl apply -f k8s/

# Ensure namespace has sidecar injection enabled
kubectl label namespace default istio-injection=enabled --overwrite

# Apply Istio-specific configurations
cat <<EOF | kubectl apply -f -
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: {service_name}-peer-auth
  namespace: default
spec:
  selector:
    matchLabels:
      app: {service_name}
  mtls:
    mode: {security_config.get("mtls_mode", "STRICT")}
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: {service_name}-authz
  namespace: default
spec:
  selector:
    matchLabels:
      app: {service_name}
  rules:
  - from:
    - source:
        principals: {json.dumps(security_config.get("allowed_principals", ["*"]))}
  - to:
    - operation:
        methods: {json.dumps(security_config.get("allowed_methods", ["GET", "POST"]))}
EOF

# Apply rate limiting if configured
"""

        if security_config.get("rate_limiting"):
            script += f"""
cat <<EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: {service_name}-rate-limit
  namespace: default
spec:
  workloadSelector:
    labels:
      app: {service_name}
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: "envoy.filters.network.http_connection_manager"
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: local_rate_limiter
            token_bucket:
              max_tokens: {security_config["rate_limiting"].get("max_tokens", 100)}
              tokens_per_fill: {security_config["rate_limiting"].get("tokens_per_fill", 100)}
              fill_interval: {security_config["rate_limiting"].get("fill_interval", "60s")}
EOF
"""

        script += f"""
echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/{service_name}

echo "✅ {service_name} deployed successfully with Istio security integration"
echo "🔒 Security features enabled:"
echo "  - mTLS: {security_config.get("mtls_mode", "STRICT")}"
echo "  - Authorization policies: ✓"
"""

        if security_config.get("rate_limiting"):
            script += 'echo "  - Rate limiting: ✓"\n'

        script += """
echo ""
echo "Service mesh status:"
istioctl proxy-status
"""

        return script

    def _generate_linkerd_script(self, service_name: str, config: dict) -> str:
        """Generate Linkerd deployment script with security policies"""
        security_config = config.get("security", {})

        script = f"""#!/bin/bash
# Enhanced Linkerd Deployment Script for {service_name}
# Generated by Marty Microservices Framework

set -e

echo "Deploying {service_name} with Linkerd service mesh and security policies..."

# Inject Linkerd proxy into deployment manifests
linkerd inject k8s/ | kubectl apply -f -

# Apply server authorization if configured
"""

        if security_config.get("authorization_policies"):
            script += f"""
cat <<EOF | kubectl apply -f -
apiVersion: policy.linkerd.io/v1beta1
kind: Server
metadata:
  name: {service_name}-server
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: {service_name}
  port: {config.get("port", 8080)}
---
apiVersion: policy.linkerd.io/v1beta1
kind: ServerAuthorization
metadata:
  name: {service_name}-authz
  namespace: default
spec:
  server:
    name: {service_name}-server
  requiredRoutes:
  - pathRegex: ".*"
    methods: {json.dumps(security_config.get("allowed_methods", ["GET", "POST"]))}
EOF
"""

        script += f"""
echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/{service_name}

echo "✅ {service_name} deployed successfully with Linkerd security integration"
echo "🔒 Security features enabled:"
echo "  - Automatic mTLS: ✓"
"""

        if security_config.get("authorization_policies"):
            script += 'echo "  - Authorization policies: ✓"\n'

        script += """
echo ""
echo "Service mesh status:"
linkerd stat deploy
"""

        return script

    async def validate_security_integration(self, namespace: str = "default") -> dict[str, Any]:
        """
        Validate that security integration is working properly

        Args:
            namespace: Kubernetes namespace to validate

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "security_manager_available": self.security_manager is not None,
            "service_mesh_installed": self.is_installed,
            "namespace_secured": False,
            "mtls_enabled": False,
            "policies_applied": False,
            "issues": [],
        }

        try:
            # Check if security manager is available
            if not self.security_manager:
                validation_results["issues"].append("No security manager configured")
                return validation_results

            # Check if service mesh is properly installed
            if not self.is_installed:
                validation_results["issues"].append(f"{self.service_mesh_type} CLI not available")
                return validation_results

            # Validate namespace security
            if self.service_mesh_type == "istio":
                validation_results.update(await self._validate_istio_security(namespace))
            elif self.service_mesh_type == "linkerd":
                validation_results.update(await self._validate_linkerd_security(namespace))

        except Exception as e:
            validation_results["issues"].append(f"Validation failed: {e}")

        return validation_results

    async def _validate_istio_security(self, namespace: str) -> dict[str, Any]:
        """Validate Istio security configuration"""
        results = {}

        try:
            # Check sidecar injection
            cmd = ["kubectl", "get", "namespace", namespace, "-o", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                namespace_data = json.loads(stdout.decode())
                labels = namespace_data.get("metadata", {}).get("labels", {})
                results["namespace_secured"] = labels.get("istio-injection") == "enabled"

            # Check for PeerAuthentication policies
            cmd = ["kubectl", "get", "peerauthentication", "-n", namespace, "-o", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                policies_data = json.loads(stdout.decode())
                results["mtls_enabled"] = len(policies_data.get("items", [])) > 0

            # Check for AuthorizationPolicy
            cmd = ["kubectl", "get", "authorizationpolicy", "-n", namespace, "-o", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                authz_data = json.loads(stdout.decode())
                results["policies_applied"] = len(authz_data.get("items", [])) > 0

        except Exception as e:
            results["issues"] = results.get("issues", [])
            results["issues"].append(f"Istio validation error: {e}")

        return results

    async def _validate_linkerd_security(self, namespace: str) -> dict[str, Any]:
        """Validate Linkerd security configuration"""
        results = {}

        try:
            # Check if services are meshed
            cmd = ["linkerd", "stat", "deploy", "-n", namespace, "--output", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                stats_data = json.loads(stdout.decode())
                meshed_services = 0
                total_services = 0

                for stat in stats_data.get("rows", []):
                    total_services += 1
                    if stat.get("meshed", "") != "-":
                        meshed_services += 1

                results["namespace_secured"] = meshed_services > 0
                results["mtls_enabled"] = meshed_services > 0  # Linkerd enables mTLS automatically

            # Check for ServerAuthorization policies
            cmd = ["kubectl", "get", "serverauthorization", "-n", namespace, "-o", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                authz_data = json.loads(stdout.decode())
                results["policies_applied"] = len(authz_data.get("items", [])) > 0

        except Exception as e:
            results["issues"] = results.get("issues", [])
            results["issues"].append(f"Linkerd validation error: {e}")

        return results

    # Multi-Mesh Support Methods

    async def deploy_multi_mesh(
        self, mesh_configs: dict[str, dict[str, Any]], namespace: str = "service-mesh"
    ) -> dict[str, bool]:
        """
        Deploy multiple service mesh instances with cross-mesh communication

        Args:
            mesh_configs: Dictionary of mesh_name -> config mappings
            namespace: Base namespace for mesh deployments

        Returns:
            Dict mapping mesh names to deployment success status
        """
        if not self.multi_mesh_enabled:
            logger.warning("Multi-mesh not enabled in configuration")
            return {}

        deployment_results = {}

        try:
            logger.info(f"Starting multi-mesh deployment with {len(mesh_configs)} meshes")

            # Deploy each mesh in parallel
            deployment_tasks = []
            for mesh_name, mesh_config in mesh_configs.items():
                mesh_namespace = f"{namespace}-{mesh_name}"
                task = self._deploy_single_mesh(mesh_name, mesh_config, mesh_namespace)
                deployment_tasks.append((mesh_name, task))

            # Wait for all deployments
            for mesh_name, task in deployment_tasks:
                try:
                    success = await task
                    deployment_results[mesh_name] = success

                    if success:
                        self.mesh_deployments[mesh_name] = {
                            "type": mesh_config.get("type", "istio"),
                            "namespace": f"{namespace}-{mesh_name}",
                            "config": mesh_config,
                            "status": "deployed",
                        }
                        logger.info(f"Successfully deployed mesh: {mesh_name}")
                    else:
                        logger.error(f"Failed to deploy mesh: {mesh_name}")

                except Exception as e:
                    logger.error(f"Error deploying mesh {mesh_name}: {e}")
                    deployment_results[mesh_name] = False

            # Set up cross-mesh communication if multiple meshes were deployed
            successful_meshes = [name for name, success in deployment_results.items() if success]
            if len(successful_meshes) > 1:
                await self._setup_cross_mesh_communication(successful_meshes)

            # Synchronize security policies across meshes
            if self.policy_sync_enabled and len(successful_meshes) > 1:
                await self._synchronize_cross_mesh_policies(successful_meshes)

            logger.info(
                f"Multi-mesh deployment completed. Success: {len(successful_meshes)}/{len(mesh_configs)}"
            )

        except Exception as e:
            logger.error(f"Multi-mesh deployment failed: {e}")

        return deployment_results

    async def _deploy_single_mesh(
        self, mesh_name: str, mesh_config: dict[str, Any], namespace: str
    ) -> bool:
        """Deploy a single mesh instance"""
        try:
            mesh_type = mesh_config.get("type", "istio").lower()

            # Create namespace
            await self._create_namespace(namespace)

            # Deploy based on mesh type
            if mesh_type == "istio":
                return await self._deploy_istio_instance(mesh_name, mesh_config, namespace)
            elif mesh_type == "linkerd":
                return await self._deploy_linkerd_instance(mesh_name, mesh_config, namespace)
            else:
                logger.error(f"Unsupported mesh type: {mesh_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to deploy mesh {mesh_name}: {e}")
            return False

    async def _deploy_istio_instance(
        self, mesh_name: str, mesh_config: dict[str, Any], namespace: str
    ) -> bool:
        """Deploy a named Istio instance"""
        try:
            # Generate unique mesh ID
            mesh_id = f"mesh-{mesh_name}"
            network_id = mesh_config.get("network_id", f"network-{mesh_name}")
            cluster_name = mesh_config.get("cluster_name", f"cluster-{mesh_name}")

            # Install Istio with multi-mesh configuration
            cmd = [
                "istioctl",
                "install",
                "--set",
                f"values.global.meshID={mesh_id}",
                "--set",
                f"values.global.network={network_id}",
                "--set",
                "values.pilot.env.EXTERNAL_ISTIOD=false",
                "--set",
                f"values.global.meshConfig.defaultConfig.proxyMetadata.ISTIO_META_CLUSTER_ID={cluster_name}",
                "--set",
                "values.pilot.env.ENABLE_CROSS_CLUSTER_WORKLOAD_ENTRY=true",
                "--set",
                "values.global.meshConfig.enablePrometheusMerge=true",
                "-y",
            ]

            if mesh_config.get("custom_values"):
                for key, value in mesh_config["custom_values"].items():
                    cmd.extend(["--set", f"{key}={value}"])

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Istio instance '{mesh_name}' installed successfully")

                # Enable automatic sidecar injection for the namespace
                await self._enable_sidecar_injection(namespace)

                # Create mesh-specific policies
                await self._create_mesh_policies(mesh_name, mesh_config, namespace)

                return True
            else:
                logger.error(f"Istio instance '{mesh_name}' installation failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to deploy Istio instance {mesh_name}: {e}")
            return False

    async def _deploy_linkerd_instance(
        self, mesh_name: str, mesh_config: dict[str, Any], namespace: str
    ) -> bool:
        """Deploy a named Linkerd instance"""
        try:
            # Linkerd doesn't natively support multiple instances, but we can use different namespaces
            # and configure cross-namespace communication

            # Install Linkerd control plane in specific namespace
            cmd = [
                "linkerd",
                "install",
                "--control-plane-namespace",
                namespace,
                "--identity-trust-domain",
                f"{mesh_name}.local",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Apply the installation
                kubectl_process = await asyncio.create_subprocess_exec(
                    "kubectl",
                    "apply",
                    "-f",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await kubectl_process.communicate(input=stdout)

                if kubectl_process.returncode == 0:
                    logger.info(
                        f"Linkerd instance '{mesh_name}' installed successfully in namespace {namespace}"
                    )

                    # Wait for control plane to be ready
                    await asyncio.sleep(30)  # Give Linkerd time to start

                    # Create mesh-specific policies
                    await self._create_mesh_policies(mesh_name, mesh_config, namespace)

                    return True
                else:
                    logger.error(f"Failed to apply Linkerd installation for {mesh_name}")
                    return False
            else:
                logger.error(
                    f"Linkerd installation generation failed for {mesh_name}: {stderr.decode()}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to deploy Linkerd instance {mesh_name}: {e}")
            return False

    async def _setup_cross_mesh_communication(self, mesh_names: list[str]) -> None:
        """Set up communication between multiple mesh instances"""
        try:
            logger.info(f"Setting up cross-mesh communication for: {', '.join(mesh_names)}")

            # For Istio meshes, create cross-network gateways
            istio_meshes = [
                name for name in mesh_names if self.mesh_deployments[name]["type"] == "istio"
            ]

            if len(istio_meshes) > 1:
                await self._setup_istio_cross_network_gateways(istio_meshes)

            # For mixed meshes (Istio + Linkerd), set up service discovery
            await self._setup_mixed_mesh_communication(mesh_names)

            logger.info("Cross-mesh communication setup completed")

        except Exception as e:
            logger.error(f"Failed to setup cross-mesh communication: {e}")

    async def _setup_istio_cross_network_gateways(self, mesh_names: list[str]) -> None:
        """Set up Istio cross-network gateways for multi-mesh communication"""
        try:
            for mesh_name in mesh_names:
                mesh_info = self.mesh_deployments[mesh_name]
                namespace = mesh_info["namespace"]

                # Create east-west gateway
                gateway_yaml = f"""
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: cross-network-gateway-{mesh_name}
  namespace: {namespace}
spec:
  selector:
    istio: eastwestgateway
  servers:
  - port:
      number: 15443
      name: tls
      protocol: TLS
    tls:
      mode: ISTIO_MUTUAL
    hosts:
    - cross-network.local
"""

                # Apply gateway configuration
                process = await asyncio.create_subprocess_exec(
                    "kubectl",
                    "apply",
                    "-f",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await process.communicate(input=gateway_yaml.encode())

                if process.returncode == 0:
                    logger.info(f"Cross-network gateway created for mesh {mesh_name}")
                else:
                    logger.error(f"Failed to create cross-network gateway for mesh {mesh_name}")

        except Exception as e:
            logger.error(f"Failed to setup Istio cross-network gateways: {e}")

    async def _setup_mixed_mesh_communication(self, mesh_names: list[str]) -> None:
        """Set up communication between different types of service meshes"""
        try:
            # Create service entries for cross-mesh service discovery
            for source_mesh in mesh_names:
                for target_mesh in mesh_names:
                    if source_mesh != target_mesh:
                        await self._create_cross_mesh_service_entry(source_mesh, target_mesh)

            logger.info("Mixed mesh communication setup completed")

        except Exception as e:
            logger.error(f"Failed to setup mixed mesh communication: {e}")

    async def _create_cross_mesh_service_entry(self, source_mesh: str, target_mesh: str) -> None:
        """Create service entries for cross-mesh service discovery"""
        try:
            source_info = self.mesh_deployments[source_mesh]
            # target_info = self.mesh_deployments[target_mesh]  # Reserved for future use

            # Only create service entries for Istio meshes
            if source_info["type"] == "istio":
                service_entry_yaml = f"""
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: cross-mesh-{target_mesh}
  namespace: {source_info["namespace"]}
spec:
  hosts:
  - {target_mesh}.local
  location: MESH_EXTERNAL
  ports:
  - number: 80
    name: http
    protocol: HTTP
  - number: 443
    name: https
    protocol: HTTPS
  resolution: DNS
  addresses:
  - 240.0.0.1  # Virtual IP for cross-mesh communication
"""

                process = await asyncio.create_subprocess_exec(
                    "kubectl",
                    "apply",
                    "-f",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await process.communicate(input=service_entry_yaml.encode())

                if process.returncode == 0:
                    logger.info(f"Service entry created: {source_mesh} -> {target_mesh}")
                else:
                    logger.error(f"Failed to create service entry: {source_mesh} -> {target_mesh}")

        except Exception as e:
            logger.error(f"Failed to create cross-mesh service entry: {e}")

    async def _synchronize_cross_mesh_policies(self, mesh_names: list[str]) -> None:
        """Synchronize security policies across multiple meshes"""
        try:
            if not self.security_manager:
                logger.warning("No security manager configured, skipping policy synchronization")
                return

            logger.info(f"Synchronizing security policies across {len(mesh_names)} meshes")

            # Get unified security policies from the security manager
            if hasattr(self.security_manager, "get_security_policies"):
                unified_policies = await self.security_manager.get_security_policies()
            else:
                unified_policies = []

            # Apply policies to each mesh
            for mesh_name in mesh_names:
                mesh_policies = await self._convert_policies_for_mesh(unified_policies, mesh_name)
                await self._apply_mesh_policies(mesh_name, mesh_policies)
                self.cross_mesh_policies[mesh_name] = mesh_policies

            # Create cross-mesh authorization policies
            await self._create_cross_mesh_authorization_policies(mesh_names)

            logger.info("Cross-mesh policy synchronization completed")

        except Exception as e:
            logger.error(f"Failed to synchronize cross-mesh policies: {e}")

    async def _convert_policies_for_mesh(
        self, unified_policies: list[dict[str, Any]], mesh_name: str
    ) -> list[dict[str, Any]]:
        """Convert unified security policies to mesh-specific format"""
        mesh_info = self.mesh_deployments[mesh_name]
        mesh_type = mesh_info["type"]
        mesh_policies = []

        for policy in unified_policies:
            if mesh_type == "istio":
                mesh_policy = await self._convert_to_istio_policy(policy, mesh_name)
            elif mesh_type == "linkerd":
                mesh_policy = await self._convert_to_linkerd_policy(policy, mesh_name)
            else:
                continue

            if mesh_policy:
                mesh_policies.append(mesh_policy)

        return mesh_policies

    async def _convert_to_istio_policy(
        self, unified_policy: dict[str, Any], mesh_name: str
    ) -> dict[str, Any] | None:
        """Convert unified policy to Istio AuthorizationPolicy format"""
        try:
            mesh_info = self.mesh_deployments[mesh_name]
            namespace = mesh_info["namespace"]

            # Convert to Istio AuthorizationPolicy
            istio_policy = {
                "apiVersion": "security.istio.io/v1beta1",
                "kind": "AuthorizationPolicy",
                "metadata": {
                    "name": f"{unified_policy.get('name', 'policy')}-{mesh_name}",
                    "namespace": namespace,
                },
                "spec": {"rules": []},
            }

            # Convert rules
            for rule in unified_policy.get("rules", []):
                istio_rule = {
                    "from": [{"source": {"principals": rule.get("principals", ["*"])}}],
                    "to": [{"operation": {"methods": rule.get("methods", ["*"])}}],
                }

                if "paths" in rule:
                    istio_rule["to"][0]["operation"]["paths"] = rule["paths"]

                istio_policy["spec"]["rules"].append(istio_rule)

            return istio_policy

        except Exception as e:
            logger.error(f"Failed to convert policy to Istio format: {e}")
            return None

    async def _convert_to_linkerd_policy(
        self, unified_policy: dict[str, Any], mesh_name: str
    ) -> dict[str, Any] | None:
        """Convert unified policy to Linkerd ServerAuthorization format"""
        try:
            mesh_info = self.mesh_deployments[mesh_name]
            namespace = mesh_info["namespace"]

            # Convert to Linkerd ServerAuthorization
            linkerd_policy = {
                "apiVersion": "policy.linkerd.io/v1beta1",
                "kind": "ServerAuthorization",
                "metadata": {
                    "name": f"{unified_policy.get('name', 'policy')}-{mesh_name}",
                    "namespace": namespace,
                },
                "spec": {
                    "server": {"name": unified_policy.get("target_service", "default")},
                    "client": {"meshTLS": {"identities": unified_policy.get("principals", ["*"])}},
                },
            }

            return linkerd_policy

        except Exception as e:
            logger.error(f"Failed to convert policy to Linkerd format: {e}")
            return None

    async def _apply_mesh_policies(self, mesh_name: str, policies: list[dict[str, Any]]) -> None:
        """Apply security policies to a specific mesh"""
        try:
            for policy in policies:
                policy_yaml = json.dumps(policy, indent=2)

                process = await asyncio.create_subprocess_exec(
                    "kubectl",
                    "apply",
                    "-f",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await process.communicate(input=policy_yaml.encode())

                if process.returncode == 0:
                    logger.info(f"Applied policy {policy['metadata']['name']} to mesh {mesh_name}")
                else:
                    logger.error(f"Failed to apply policy to mesh {mesh_name}")

        except Exception as e:
            logger.error(f"Failed to apply mesh policies: {e}")

    async def _create_cross_mesh_authorization_policies(self, mesh_names: list[str]) -> None:
        """Create authorization policies that allow cross-mesh communication"""
        try:
            for source_mesh in mesh_names:
                for target_mesh in mesh_names:
                    if source_mesh != target_mesh:
                        await self._create_cross_mesh_authz_policy(source_mesh, target_mesh)

            logger.info("Cross-mesh authorization policies created")

        except Exception as e:
            logger.error(f"Failed to create cross-mesh authorization policies: {e}")

    async def _create_namespace(self, namespace: str) -> bool:
        """Create Kubernetes namespace if it doesn't exist"""
        try:
            # Check if namespace exists
            cmd = ["kubectl", "get", "namespace", namespace]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Namespace {namespace} already exists")
                return True

            # Create namespace
            cmd = ["kubectl", "create", "namespace", namespace]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Created namespace: {namespace}")
                return True
            else:
                logger.error(f"Failed to create namespace {namespace}: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Error creating namespace {namespace}: {e}")
            return False

    async def _create_cross_mesh_authz_policy(self, source_mesh: str, target_mesh: str) -> None:
        """Create authorization policy allowing communication between specific meshes"""
        try:
            target_info = self.mesh_deployments[target_mesh]

            if target_info["type"] == "istio":
                policy_yaml = f"""
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-cross-mesh-{source_mesh}
  namespace: {target_info["namespace"]}
spec:
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/{self.mesh_deployments[source_mesh]["namespace"]}/sa/*"]
  - to:
    - operation:
        methods: ["GET", "POST", "PUT", "DELETE"]
"""

                process = await asyncio.create_subprocess_exec(
                    "kubectl",
                    "apply",
                    "-f",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await process.communicate(input=policy_yaml.encode())

                if process.returncode == 0:
                    logger.info(
                        f"Cross-mesh authorization policy created: {source_mesh} -> {target_mesh}"
                    )

        except Exception as e:
            logger.error(f"Failed to create cross-mesh authorization policy: {e}")

    def get_multi_mesh_status(self) -> dict[str, Any]:
        """Get status of all deployed meshes"""
        return {
            "multi_mesh_enabled": self.multi_mesh_enabled,
            "policy_sync_enabled": self.policy_sync_enabled,
            "deployed_meshes": {
                name: {
                    "type": info["type"],
                    "namespace": info["namespace"],
                    "status": info["status"],
                }
                for name, info in self.mesh_deployments.items()
            },
            "cross_mesh_policies_count": sum(
                len(policies) for policies in self.cross_mesh_policies.values()
            ),
        }

    async def update_cross_mesh_policies(self, updated_policies: list[dict[str, Any]]) -> bool:
        """Update security policies across all deployed meshes"""
        try:
            if not self.policy_sync_enabled:
                logger.warning("Policy synchronization is disabled")
                return False

            mesh_names = list(self.mesh_deployments.keys())
            if len(mesh_names) < 2:
                logger.info("Less than 2 meshes deployed, skipping cross-mesh policy update")
                return True

            # Convert and apply policies to each mesh
            for mesh_name in mesh_names:
                mesh_policies = await self._convert_policies_for_mesh(updated_policies, mesh_name)
                await self._apply_mesh_policies(mesh_name, mesh_policies)
                self.cross_mesh_policies[mesh_name] = mesh_policies

            logger.info(f"Cross-mesh policies updated across {len(mesh_names)} meshes")
            return True

        except Exception as e:
            logger.error(f"Failed to update cross-mesh policies: {e}")
            return False
