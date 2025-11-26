"""
Kubernetes operators for Marty Microservices Framework.

This module provides comprehensive Kubernetes operator capabilities including
custom resource definitions (CRDs), operators for microservice management,
automated operations, and cloud-native application lifecycle management.
"""

import asyncio
import builtins
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

from .core import DeploymentConfig

logger = logging.getLogger(__name__)


class OperatorType(Enum):
    """Kubernetes operator types."""

    MICROSERVICE = "microservice"
    DATABASE = "database"
    MONITORING = "monitoring"
    SECURITY = "security"
    NETWORKING = "networking"


class ReconciliationAction(Enum):
    """Reconciliation actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SCALE = "scale"
    RESTART = "restart"
    ROLLBACK = "rollback"


@dataclass
class CustomResourceDefinition:
    """Custom Resource Definition specification."""

    name: str
    group: str
    version: str
    kind: str
    plural: str
    scope: str = "Namespaced"
    schema: builtins.dict[str, Any] = field(default_factory=dict)
    additional_printer_columns: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    subresources: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class OperatorConfig:
    """Operator configuration."""

    name: str
    namespace: str
    image: str
    replicas: int = 1
    service_account: str = "default"
    cluster_role: str | None = None
    resources: builtins.dict[str, Any] = field(default_factory=dict)
    environment_variables: builtins.dict[str, str] = field(default_factory=dict)
    reconcile_interval: int = 30  # seconds


@dataclass
class ReconciliationEvent:
    """Reconciliation event information."""

    resource_name: str
    namespace: str
    action: ReconciliationAction
    timestamp: datetime
    status: str
    message: str | None = None
    error: str | None = None


class CustomResourceManager:
    """Manages Custom Resource Definitions."""

    def __init__(self, kubeconfig_path: str | None = None):
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()

        self.api_client = client.ApiClient()
        self.custom_objects_api = client.CustomObjectsApi()
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.apiextensions_v1 = client.ApiextensionsV1Api()

    async def create_crd(self, crd_spec: CustomResourceDefinition) -> bool:
        """Create Custom Resource Definition."""
        try:
            crd_manifest = {
                "apiVersion": "apiextensions.k8s.io/v1",
                "kind": "CustomResourceDefinition",
                "metadata": {"name": f"{crd_spec.plural}.{crd_spec.group}"},
                "spec": {
                    "group": crd_spec.group,
                    "versions": [
                        {
                            "name": crd_spec.version,
                            "served": True,
                            "storage": True,
                            "schema": {"openAPIV3Schema": crd_spec.schema},
                            "additionalPrinterColumns": crd_spec.additional_printer_columns,
                            "subresources": crd_spec.subresources,
                        }
                    ],
                    "scope": crd_spec.scope,
                    "names": {
                        "plural": crd_spec.plural,
                        "singular": crd_spec.name,
                        "kind": crd_spec.kind,
                    },
                },
            }

            crd = client.V1CustomResourceDefinition(
                api_version=crd_manifest["apiVersion"],
                kind=crd_manifest["kind"],
                metadata=client.V1ObjectMeta(**crd_manifest["metadata"]),
                spec=client.V1CustomResourceDefinitionSpec(**crd_manifest["spec"]),
            )

            self.apiextensions_v1.create_custom_resource_definition(crd)
            logger.info(f"Created CRD: {crd_spec.name}")
            return True

        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"CRD {crd_spec.name} already exists")
                return True
            logger.error(f"Failed to create CRD: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to create CRD: {e}")
            return False

    async def create_custom_resource(
        self,
        group: str,
        version: str,
        plural: str,
        namespace: str,
        name: str,
        spec: builtins.dict[str, Any],
    ) -> bool:
        """Create custom resource instance."""
        try:
            resource = {
                "apiVersion": f"{group}/{version}",
                "kind": plural.capitalize()[:-1],  # Remove 's' and capitalize
                "metadata": {"name": name, "namespace": namespace},
                "spec": spec,
            }

            self.custom_objects_api.create_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                body=resource,
            )

            logger.info(f"Created custom resource: {name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to create custom resource: {e}")
            return False

    async def get_custom_resource(
        self, group: str, version: str, plural: str, namespace: str, name: str
    ) -> builtins.dict[str, Any] | None:
        """Get custom resource instance."""
        try:
            resource = self.custom_objects_api.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
            )
            return resource

        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to get custom resource: {e}")
            return None

    async def update_custom_resource(
        self,
        group: str,
        version: str,
        plural: str,
        namespace: str,
        name: str,
        spec: builtins.dict[str, Any],
    ) -> bool:
        """Update custom resource instance."""
        try:
            # Get current resource
            current = await self.get_custom_resource(group, version, plural, namespace, name)
            if not current:
                return False

            # Update spec
            current["spec"] = spec

            self.custom_objects_api.patch_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
                body=current,
            )

            logger.info(f"Updated custom resource: {name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to update custom resource: {e}")
            return False

    async def delete_custom_resource(
        self, group: str, version: str, plural: str, namespace: str, name: str
    ) -> bool:
        """Delete custom resource instance."""
        try:
            self.custom_objects_api.delete_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
            )

            logger.info(f"Deleted custom resource: {name}")
            return True

        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to delete custom resource: {e}")
            return False

    async def list_custom_resources(
        self, group: str, version: str, plural: str, namespace: str | None = None
    ) -> builtins.list[builtins.dict[str, Any]]:
        """List custom resource instances."""
        try:
            if namespace:
                response = self.custom_objects_api.list_namespaced_custom_object(
                    group=group, version=version, namespace=namespace, plural=plural
                )
            else:
                response = self.custom_objects_api.list_cluster_custom_object(
                    group=group, version=version, plural=plural
                )

            return response.get("items", [])

        except ApiException as e:
            logger.error(f"Failed to list custom resources: {e}")
            return []


class MicroserviceOperator:
    """Kubernetes operator for microservice management."""

    def __init__(self, namespace: str = "default", kubeconfig_path: str | None = None):
        self.namespace = namespace
        self.resource_manager = CustomResourceManager(kubeconfig_path)
        self.reconciliation_events: builtins.list[ReconciliationEvent] = []
        self.running = False

    async def setup(self) -> bool:
        """Setup operator CRDs and resources."""
        try:
            # Create Microservice CRD
            microservice_crd = CustomResourceDefinition(
                name="microservice",
                group="marty.framework",
                version="v1",
                kind="Microservice",
                plural="microservices",
                schema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "properties": {
                                "image": {"type": "string"},
                                "replicas": {"type": "integer", "minimum": 1},
                                "port": {"type": "integer"},
                                "resources": {
                                    "type": "object",
                                    "properties": {
                                        "requests": {
                                            "type": "object",
                                            "properties": {
                                                "cpu": {"type": "string"},
                                                "memory": {"type": "string"},
                                            },
                                        },
                                        "limits": {
                                            "type": "object",
                                            "properties": {
                                                "cpu": {"type": "string"},
                                                "memory": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                                "environment": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                                "healthCheck": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "port": {"type": "integer"},
                                        "initialDelay": {"type": "integer"},
                                        "period": {"type": "integer"},
                                    },
                                },
                                "autoscaling": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "minReplicas": {"type": "integer"},
                                        "maxReplicas": {"type": "integer"},
                                        "targetCPU": {"type": "integer"},
                                    },
                                },
                            },
                            "required": ["image", "port"],
                        },
                        "status": {
                            "type": "object",
                            "properties": {
                                "phase": {"type": "string"},
                                "readyReplicas": {"type": "integer"},
                                "updatedReplicas": {"type": "integer"},
                                "conditions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string"},
                                            "status": {"type": "string"},
                                            "lastTransitionTime": {"type": "string"},
                                            "reason": {"type": "string"},
                                            "message": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                additional_printer_columns=[
                    {"name": "Image", "type": "string", "jsonPath": ".spec.image"},
                    {
                        "name": "Replicas",
                        "type": "integer",
                        "jsonPath": ".spec.replicas",
                    },
                    {
                        "name": "Ready",
                        "type": "integer",
                        "jsonPath": ".status.readyReplicas",
                    },
                    {"name": "Phase", "type": "string", "jsonPath": ".status.phase"},
                    {
                        "name": "Age",
                        "type": "date",
                        "jsonPath": ".metadata.creationTimestamp",
                    },
                ],
                subresources={
                    "status": {},
                    "scale": {
                        "specReplicasPath": ".spec.replicas",
                        "statusReplicasPath": ".status.readyReplicas",
                    },
                },
            )

            success = await self.resource_manager.create_crd(microservice_crd)

            if success:
                # Wait for CRD to be established
                await asyncio.sleep(2)

                logger.info("Microservice operator setup completed")
                return True

            return False

        except Exception as e:
            logger.error(f"Operator setup failed: {e}")
            return False

    async def start(self) -> None:
        """Start the operator."""
        self.running = True
        logger.info("Starting microservice operator")

        # Start reconciliation loop
        await asyncio.gather(self._watch_microservices(), self._reconciliation_loop())

    async def stop(self) -> None:
        """Stop the operator."""
        self.running = False
        logger.info("Stopping microservice operator")

    async def _watch_microservices(self) -> None:
        """Watch for microservice custom resource changes."""
        while self.running:
            try:
                w = watch.Watch()
                for event in w.stream(
                    self.resource_manager.custom_objects_api.list_namespaced_custom_object,
                    group="marty.framework",
                    version="v1",
                    namespace=self.namespace,
                    plural="microservices",
                    timeout_seconds=60,
                ):
                    if not self.running:
                        break

                    event_type = event["type"]
                    microservice = event["object"]

                    logger.info(
                        f"Microservice event: {event_type} - {microservice['metadata']['name']}"
                    )

                    # Queue reconciliation
                    await self._reconcile_microservice(microservice, event_type)

            except Exception as e:
                logger.error(f"Watch error: {e}")
                await asyncio.sleep(5)

    async def _reconciliation_loop(self) -> None:
        """Periodic reconciliation loop."""
        while self.running:
            try:
                # List all microservices and reconcile
                microservices = await self.resource_manager.list_custom_resources(
                    group="marty.framework",
                    version="v1",
                    plural="microservices",
                    namespace=self.namespace,
                )

                for microservice in microservices:
                    await self._reconcile_microservice(microservice, "PERIODIC")

                await asyncio.sleep(30)  # Reconcile every 30 seconds

            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}")
                await asyncio.sleep(5)

    async def _reconcile_microservice(
        self, microservice: builtins.dict[str, Any], event_type: str
    ) -> None:
        """Reconcile a single microservice."""
        try:
            name = microservice["metadata"]["name"]
            namespace = microservice["metadata"]["namespace"]
            spec = microservice.get("spec", {})

            logger.info(f"Reconciling microservice: {name}")

            event = ReconciliationEvent(
                resource_name=name,
                namespace=namespace,
                action=ReconciliationAction.UPDATE,
                timestamp=datetime.utcnow(),
                status="started",
            )

            if event_type == "DELETED":
                event.action = ReconciliationAction.DELETE
                await self._delete_microservice_resources(name, namespace)
                event.status = "completed"
                event.message = "Microservice resources deleted"
            else:
                # Create or update resources
                await self._ensure_deployment(name, namespace, spec)
                await self._ensure_service(name, namespace, spec)
                await self._ensure_hpa(name, namespace, spec)
                await self._update_microservice_status(name, namespace)

                event.status = "completed"
                event.message = "Microservice resources reconciled"

            self.reconciliation_events.append(event)

        except Exception as e:
            logger.error(f"Reconciliation failed for {microservice['metadata']['name']}: {e}")

            event = ReconciliationEvent(
                resource_name=microservice["metadata"]["name"],
                namespace=microservice["metadata"]["namespace"],
                action=ReconciliationAction.UPDATE,
                timestamp=datetime.utcnow(),
                status="failed",
                error=str(e),
            )
            self.reconciliation_events.append(event)

    async def _ensure_deployment(
        self, name: str, namespace: str, spec: builtins.dict[str, Any]
    ) -> None:
        """Ensure deployment exists and is up to date."""
        try:
            # Check if deployment exists
            try:
                existing_deployment = self.resource_manager.apps_v1.read_namespaced_deployment(
                    name=name, namespace=namespace
                )
                update_needed = False

                # Check if spec has changed
                current_image = existing_deployment.spec.template.spec.containers[0].image
                if current_image != spec.get("image"):
                    update_needed = True

                current_replicas = existing_deployment.spec.replicas
                if current_replicas != spec.get("replicas", 1):
                    update_needed = True

                if update_needed:
                    # Update deployment
                    deployment = self._build_deployment(name, namespace, spec)
                    self.resource_manager.apps_v1.patch_namespaced_deployment(
                        name=name, namespace=namespace, body=deployment
                    )
                    logger.info(f"Updated deployment: {name}")

            except ApiException as e:
                if e.status == 404:
                    # Create deployment
                    deployment = self._build_deployment(name, namespace, spec)
                    self.resource_manager.apps_v1.create_namespaced_deployment(
                        namespace=namespace, body=deployment
                    )
                    logger.info(f"Created deployment: {name}")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to ensure deployment {name}: {e}")
            raise

    def _build_deployment(
        self, name: str, namespace: str, spec: builtins.dict[str, Any]
    ) -> client.V1Deployment:
        """Build Kubernetes deployment manifest."""
        container = client.V1Container(
            name=name,
            image=spec["image"],
            ports=[client.V1ContainerPort(container_port=spec["port"])],
            env=[client.V1EnvVar(name=k, value=v) for k, v in spec.get("environment", {}).items()],
        )

        # Add resources if specified
        if "resources" in spec:
            resources_spec = spec["resources"]
            container.resources = client.V1ResourceRequirements(
                requests=resources_spec.get("requests", {}),
                limits=resources_spec.get("limits", {}),
            )

        # Add health checks if specified
        if "healthCheck" in spec:
            health_spec = spec["healthCheck"]
            probe = client.V1Probe(
                http_get=client.V1HTTPGetAction(
                    path=health_spec.get("path", "/health"),
                    port=health_spec.get("port", spec["port"]),
                ),
                initial_delay_seconds=health_spec.get("initialDelay", 30),
                period_seconds=health_spec.get("period", 10),
            )
            container.liveness_probe = probe
            container.readiness_probe = probe

        pod_spec = client.V1PodSpec(containers=[container])

        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": name, "managed-by": "marty-operator"}),
            spec=pod_spec,
        )

        deployment_spec = client.V1DeploymentSpec(
            replicas=spec.get("replicas", 1),
            selector=client.V1LabelSelector(match_labels={"app": name}),
            template=pod_template,
        )

        return client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels={"app": name, "managed-by": "marty-operator"},
            ),
            spec=deployment_spec,
        )

    async def _ensure_service(
        self, name: str, namespace: str, spec: builtins.dict[str, Any]
    ) -> None:
        """Ensure service exists."""
        try:
            # Check if service exists
            try:
                self.resource_manager.core_v1.read_namespaced_service(
                    name=name, namespace=namespace
                )
                # Service exists, no update needed for now

            except ApiException as e:
                if e.status == 404:
                    # Create service
                    service = client.V1Service(
                        api_version="v1",
                        kind="Service",
                        metadata=client.V1ObjectMeta(
                            name=name,
                            namespace=namespace,
                            labels={"app": name, "managed-by": "marty-operator"},
                        ),
                        spec=client.V1ServiceSpec(
                            selector={"app": name},
                            ports=[
                                client.V1ServicePort(
                                    port=80, target_port=spec["port"], protocol="TCP"
                                )
                            ],
                            type="ClusterIP",
                        ),
                    )

                    self.resource_manager.core_v1.create_namespaced_service(
                        namespace=namespace, body=service
                    )
                    logger.info(f"Created service: {name}")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to ensure service {name}: {e}")
            raise

    async def _ensure_hpa(self, name: str, namespace: str, spec: builtins.dict[str, Any]) -> None:
        """Ensure HorizontalPodAutoscaler exists if autoscaling is enabled."""
        try:
            autoscaling_spec = spec.get("autoscaling", {})
            if not autoscaling_spec.get("enabled", False):
                return

            autoscaling_v2 = client.AutoscalingV2Api()

            # Check if HPA exists
            try:
                autoscaling_v2.read_namespaced_horizontal_pod_autoscaler(
                    name=name, namespace=namespace
                )
                # HPA exists, no update needed for now

            except ApiException as e:
                if e.status == 404:
                    # Create HPA
                    hpa = client.V2HorizontalPodAutoscaler(
                        api_version="autoscaling/v2",
                        kind="HorizontalPodAutoscaler",
                        metadata=client.V1ObjectMeta(
                            name=name,
                            namespace=namespace,
                            labels={"app": name, "managed-by": "marty-operator"},
                        ),
                        spec=client.V2HorizontalPodAutoscalerSpec(
                            scale_target_ref=client.V2CrossVersionObjectReference(
                                api_version="apps/v1", kind="Deployment", name=name
                            ),
                            min_replicas=autoscaling_spec.get("minReplicas", 1),
                            max_replicas=autoscaling_spec.get("maxReplicas", 10),
                            metrics=[
                                client.V2MetricSpec(
                                    type="Resource",
                                    resource=client.V2ResourceMetricSource(
                                        name="cpu",
                                        target=client.V2MetricTarget(
                                            type="Utilization",
                                            average_utilization=autoscaling_spec.get(
                                                "targetCPU", 70
                                            ),
                                        ),
                                    ),
                                )
                            ],
                        ),
                    )

                    autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                        namespace=namespace, body=hpa
                    )
                    logger.info(f"Created HPA: {name}")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to ensure HPA {name}: {e}")
            raise

    async def _update_microservice_status(self, name: str, namespace: str) -> None:
        """Update microservice status."""
        try:
            # Get deployment status
            deployment = self.resource_manager.apps_v1.read_namespaced_deployment(
                name=name, namespace=namespace
            )

            ready_replicas = deployment.status.ready_replicas or 0
            updated_replicas = deployment.status.updated_replicas or 0
            replicas = deployment.spec.replicas or 0

            # Determine phase
            if ready_replicas == replicas and updated_replicas == replicas:
                phase = "Ready"
            elif ready_replicas > 0:
                phase = "Partially Ready"
            else:
                phase = "Not Ready"

            # Update status
            status = {
                "phase": phase,
                "readyReplicas": ready_replicas,
                "updatedReplicas": updated_replicas,
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True" if phase == "Ready" else "False",
                        "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                        "reason": "DeploymentReady" if phase == "Ready" else "DeploymentNotReady",
                        "message": f"Deployment has {ready_replicas}/{replicas} ready replicas",
                    }
                ],
            }

            # Get current microservice
            microservice = await self.resource_manager.get_custom_resource(
                group="marty.framework",
                version="v1",
                plural="microservices",
                namespace=namespace,
                name=name,
            )

            if microservice:
                microservice["status"] = status

                self.resource_manager.custom_objects_api.patch_namespaced_custom_object_status(
                    group="marty.framework",
                    version="v1",
                    namespace=namespace,
                    plural="microservices",
                    name=name,
                    body=microservice,
                )

        except Exception as e:
            logger.error(f"Failed to update status for {name}: {e}")

    async def _delete_microservice_resources(self, name: str, namespace: str) -> None:
        """Delete all resources associated with a microservice."""
        try:
            # Delete deployment
            try:
                self.resource_manager.apps_v1.delete_namespaced_deployment(
                    name=name, namespace=namespace
                )
                logger.info(f"Deleted deployment: {name}")
            except ApiException as e:
                if e.status != 404:
                    logger.error(f"Failed to delete deployment {name}: {e}")

            # Delete service
            try:
                self.resource_manager.core_v1.delete_namespaced_service(
                    name=name, namespace=namespace
                )
                logger.info(f"Deleted service: {name}")
            except ApiException as e:
                if e.status != 404:
                    logger.error(f"Failed to delete service {name}: {e}")

            # Delete HPA
            try:
                autoscaling_v2 = client.AutoscalingV2Api()
                autoscaling_v2.delete_namespaced_horizontal_pod_autoscaler(
                    name=name, namespace=namespace
                )
                logger.info(f"Deleted HPA: {name}")
            except ApiException as e:
                if e.status != 404:
                    logger.error(f"Failed to delete HPA {name}: {e}")

        except Exception as e:
            logger.error(f"Failed to delete microservice resources {name}: {e}")
            raise

    async def create_microservice(self, name: str, config: DeploymentConfig) -> bool:
        """Create a microservice custom resource."""
        try:
            spec = {
                "image": config.image,
                "replicas": config.resources.replicas,
                "port": config.health_check.port,
                "resources": {
                    "requests": {
                        "cpu": config.resources.cpu_request,
                        "memory": config.resources.memory_request,
                    },
                    "limits": {
                        "cpu": config.resources.cpu_limit,
                        "memory": config.resources.memory_limit,
                    },
                },
                "environment": config.environment_variables,
                "healthCheck": {
                    "path": config.health_check.path,
                    "port": config.health_check.port,
                    "initialDelay": config.health_check.initial_delay,
                    "period": config.health_check.period,
                },
                "autoscaling": {
                    "enabled": config.resources.max_replicas > config.resources.min_replicas,
                    "minReplicas": config.resources.min_replicas,
                    "maxReplicas": config.resources.max_replicas,
                    "targetCPU": 70,
                },
            }

            return await self.resource_manager.create_custom_resource(
                group="marty.framework",
                version="v1",
                plural="microservices",
                namespace=self.namespace,
                name=name,
                spec=spec,
            )

        except Exception as e:
            logger.error(f"Failed to create microservice {name}: {e}")
            return False

    async def get_microservice(self, name: str) -> builtins.dict[str, Any] | None:
        """Get microservice custom resource."""
        return await self.resource_manager.get_custom_resource(
            group="marty.framework",
            version="v1",
            plural="microservices",
            namespace=self.namespace,
            name=name,
        )

    async def list_microservices(self) -> builtins.list[builtins.dict[str, Any]]:
        """List all microservice custom resources."""
        return await self.resource_manager.list_custom_resources(
            group="marty.framework",
            version="v1",
            plural="microservices",
            namespace=self.namespace,
        )

    async def delete_microservice(self, name: str) -> bool:
        """Delete microservice custom resource."""
        return await self.resource_manager.delete_custom_resource(
            group="marty.framework",
            version="v1",
            plural="microservices",
            namespace=self.namespace,
            name=name,
        )

    def get_reconciliation_events(self, limit: int = 100) -> builtins.list[ReconciliationEvent]:
        """Get recent reconciliation events."""
        return sorted(self.reconciliation_events[-limit:], key=lambda x: x.timestamp, reverse=True)


class OperatorManager:
    """Manages multiple operators."""

    def __init__(self, kubeconfig_path: str | None = None):
        self.kubeconfig_path = kubeconfig_path
        self.operators: builtins.dict[str, Any] = {}
        self.running = False

    async def deploy_operator(self, config: OperatorConfig) -> bool:
        """Deploy operator to Kubernetes cluster."""
        try:
            resource_manager = CustomResourceManager(self.kubeconfig_path)

            # Create service account
            service_account = client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(
                    name=config.service_account, namespace=config.namespace
                )
            )

            try:
                resource_manager.core_v1.create_namespaced_service_account(
                    namespace=config.namespace, body=service_account
                )
            except ApiException as e:
                if e.status != 409:  # Ignore if already exists
                    raise

            # Create cluster role if specified
            if config.cluster_role:
                cluster_role = client.V1ClusterRole(
                    metadata=client.V1ObjectMeta(name=config.cluster_role),
                    rules=[
                        client.V1PolicyRule(
                            api_groups=[""],
                            resources=["pods", "services", "endpoints"],
                            verbs=[
                                "get",
                                "list",
                                "watch",
                                "create",
                                "update",
                                "patch",
                                "delete",
                            ],
                        ),
                        client.V1PolicyRule(
                            api_groups=["apps"],
                            resources=["deployments"],
                            verbs=[
                                "get",
                                "list",
                                "watch",
                                "create",
                                "update",
                                "patch",
                                "delete",
                            ],
                        ),
                        client.V1PolicyRule(
                            api_groups=["autoscaling"],
                            resources=["horizontalpodautoscalers"],
                            verbs=[
                                "get",
                                "list",
                                "watch",
                                "create",
                                "update",
                                "patch",
                                "delete",
                            ],
                        ),
                        client.V1PolicyRule(
                            api_groups=["marty.framework"],
                            resources=["microservices"],
                            verbs=[
                                "get",
                                "list",
                                "watch",
                                "create",
                                "update",
                                "patch",
                                "delete",
                            ],
                        ),
                    ],
                )

                try:
                    resource_manager.rbac_v1.create_cluster_role(body=cluster_role)
                except ApiException as e:
                    if e.status != 409:  # Ignore if already exists
                        raise

                # Create cluster role binding
                cluster_role_binding = client.V1ClusterRoleBinding(
                    metadata=client.V1ObjectMeta(name=f"{config.cluster_role}-binding"),
                    subjects=[
                        client.RbacV1Subject(
                            kind="ServiceAccount",
                            name=config.service_account,
                            namespace=config.namespace,
                        )
                    ],
                    role_ref=client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io",
                        kind="ClusterRole",
                        name=config.cluster_role,
                    ),
                )

                try:
                    resource_manager.rbac_v1.create_cluster_role_binding(body=cluster_role_binding)
                except ApiException as e:
                    if e.status != 409:  # Ignore if already exists
                        raise

            # Create operator deployment
            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(
                    name=config.name,
                    namespace=config.namespace,
                    labels={"app": config.name, "component": "operator"},
                ),
                spec=client.V1DeploymentSpec(
                    replicas=config.replicas,
                    selector=client.V1LabelSelector(match_labels={"app": config.name}),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={"app": config.name}),
                        spec=client.V1PodSpec(
                            service_account_name=config.service_account,
                            containers=[
                                client.V1Container(
                                    name="operator",
                                    image=config.image,
                                    env=[
                                        client.V1EnvVar(name=k, value=v)
                                        for k, v in config.environment_variables.items()
                                    ],
                                    resources=client.V1ResourceRequirements(**config.resources)
                                    if config.resources
                                    else None,
                                )
                            ],
                        ),
                    ),
                ),
            )

            resource_manager.apps_v1.create_namespaced_deployment(
                namespace=config.namespace, body=deployment
            )

            logger.info(f"Deployed operator: {config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy operator {config.name}: {e}")
            return False

    async def start_operator(self, operator_type: OperatorType, namespace: str = "default") -> bool:
        """Start an operator."""
        try:
            if operator_type == OperatorType.MICROSERVICE:
                operator = MicroserviceOperator(namespace, self.kubeconfig_path)
                await operator.setup()

                # Start operator in background
                asyncio.create_task(operator.start())

                self.operators[f"{operator_type.value}-{namespace}"] = operator
                logger.info(f"Started {operator_type.value} operator in namespace {namespace}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to start operator {operator_type.value}: {e}")
            return False

    async def stop_operator(self, operator_type: OperatorType, namespace: str = "default") -> bool:
        """Stop an operator."""
        try:
            operator_key = f"{operator_type.value}-{namespace}"
            operator = self.operators.get(operator_key)

            if operator:
                await operator.stop()
                del self.operators[operator_key]
                logger.info(f"Stopped {operator_type.value} operator in namespace {namespace}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to stop operator {operator_type.value}: {e}")
            return False

    def get_operator(self, operator_type: OperatorType, namespace: str = "default") -> Any | None:
        """Get operator instance."""
        operator_key = f"{operator_type.value}-{namespace}"
        return self.operators.get(operator_key)


# Utility functions
async def deploy_microservice_with_operator(
    operator: MicroserviceOperator, name: str, config: DeploymentConfig
) -> builtins.tuple[bool, str | None]:
    """Deploy microservice using operator."""
    try:
        success = await operator.create_microservice(name, config)

        if success:
            # Wait for microservice to be ready
            timeout = 300  # 5 minutes
            start_time = datetime.utcnow()

            while (datetime.utcnow() - start_time).total_seconds() < timeout:
                microservice = await operator.get_microservice(name)

                if microservice and microservice.get("status", {}).get("phase") == "Ready":
                    return True, f"Microservice {name} deployed and ready"

                await asyncio.sleep(10)

            return False, f"Microservice {name} deployment timed out"
        return False, f"Failed to create microservice {name}"

    except Exception as e:
        return False, f"Operator deployment error: {e!s}"


def create_operator_config(
    name: str, image: str, namespace: str = "marty-system"
) -> OperatorConfig:
    """Create operator configuration."""
    return OperatorConfig(
        name=name,
        namespace=namespace,
        image=image,
        service_account=f"{name}-operator",
        cluster_role=f"{name}-operator",
        resources={
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        },
        environment_variables={
            "OPERATOR_NAMESPACE": namespace,
            "RECONCILE_INTERVAL": "30",
        },
    )
