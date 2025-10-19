"""
Traffic Management for Advanced Deployment Strategies

Provides comprehensive traffic management capabilities including:
- Load balancer integration
- Service mesh configuration
- Traffic splitting and routing
- Feature flag integration
- Circuit breaker patterns
- Rate limiting and throttling
"""

import asyncio
import builtins
import importlib.util
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kubernetes import client, config

# External dependencies availability checks
KUBERNETES_AVAILABLE = importlib.util.find_spec("kubernetes") is not None


class TrafficBackend(Enum):
    """Traffic management backend types"""

    ISTIO = "istio"
    NGINX = "nginx"
    TRAEFIK = "traefik"
    KONG = "kong"
    ENVOY = "envoy"
    AWS_ALB = "aws_alb"
    AZURE_AG = "azure_ag"
    GCP_LB = "gcp_lb"


class RoutingRule(Enum):
    """Traffic routing rule types"""

    WEIGHTED = "weighted"
    HEADER_MATCH = "header_match"
    PATH_MATCH = "path_match"
    USER_AGENT = "user_agent"
    GEOGRAPHIC = "geographic"
    FEATURE_FLAG = "feature_flag"
    TIME_BASED = "time_based"


@dataclass
class TrafficDestination:
    """Traffic destination configuration"""

    name: str
    host: str
    port: int = 80

    # Weight and priority
    weight: int = 100
    priority: int = 1

    # Health check configuration
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_retries: int = 3

    # Routing configuration
    subset: str | None = None  # For Istio destination rules
    labels: builtins.dict[str, str] = field(default_factory=dict)

    # Load balancing
    load_balancer_policy: str = "round_robin"  # round_robin, least_conn, random, hash

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class TrafficRoute:
    """Traffic routing rule configuration"""

    name: str
    rule_type: RoutingRule
    destinations: builtins.list[TrafficDestination]

    # Matching criteria
    match_headers: builtins.dict[str, str] = field(default_factory=dict)
    match_paths: builtins.list[str] = field(default_factory=list)
    match_methods: builtins.list[str] = field(default_factory=list)
    match_query_params: builtins.dict[str, str] = field(default_factory=dict)

    # Advanced matching
    user_agent_patterns: builtins.list[str] = field(default_factory=list)
    geographic_regions: builtins.list[str] = field(default_factory=list)
    feature_flags: builtins.dict[str, Any] = field(default_factory=dict)
    time_windows: builtins.list[builtins.dict[str, str]] = field(default_factory=list)

    # Route configuration
    timeout: int = 30
    retries: int = 3
    retry_on: builtins.list[str] = field(default_factory=lambda: ["5xx", "timeout"])

    # Traffic policies
    rate_limit: builtins.dict[str, Any] | None = None
    circuit_breaker: builtins.dict[str, Any] | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "rule_type": self.rule_type.value,
            "destinations": [dest.to_dict() for dest in self.destinations],
        }


@dataclass
class TrafficPolicy:
    """Traffic management policy"""

    name: str
    namespace: str = "default"

    # Load balancing
    load_balancer: builtins.dict[str, Any] = field(default_factory=dict)

    # Connection pool settings
    connection_pool: builtins.dict[str, Any] = field(default_factory=dict)

    # Circuit breaker settings
    circuit_breaker: builtins.dict[str, Any] = field(default_factory=dict)

    # Retry policy
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)

    # Timeout settings
    timeout: builtins.dict[str, Any] = field(default_factory=dict)

    # Rate limiting
    rate_limit: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


class TrafficManagerBase(ABC):
    """
    Base class for traffic management implementations

    Defines the interface that all traffic managers must implement
    """

    def __init__(self, backend: TrafficBackend):
        self.backend = backend
        self.routes: builtins.dict[str, TrafficRoute] = {}
        self.policies: builtins.dict[str, TrafficPolicy] = {}

    @abstractmethod
    async def configure_route(self, route: TrafficRoute) -> bool:
        """Configure traffic route"""

    @abstractmethod
    async def update_traffic_split(
        self, route_name: str, destinations: builtins.list[TrafficDestination]
    ) -> bool:
        """Update traffic split weights"""

    @abstractmethod
    async def apply_policy(self, policy: TrafficPolicy) -> bool:
        """Apply traffic policy"""

    @abstractmethod
    async def get_traffic_metrics(self, route_name: str) -> builtins.dict[str, Any]:
        """Get traffic metrics for route"""

    @abstractmethod
    async def validate_configuration(self) -> builtins.dict[str, Any]:
        """Validate traffic configuration"""


class IstioTrafficManager(TrafficManagerBase):
    """
    Istio service mesh traffic management implementation

    Features:
    - Virtual Service configuration
    - Destination Rule management
    - Traffic policies and circuit breakers
    - Canary and blue-green deployments
    """

    def __init__(self):
        super().__init__(TrafficBackend.ISTIO)
        self.kubernetes_client = None

        if KUBERNETES_AVAILABLE:
            try:
                config.load_incluster_config()
                self.kubernetes_client = client.CustomObjectsApi()
            except Exception as incluster_error:
                try:
                    config.load_kube_config()
                    self.kubernetes_client = client.CustomObjectsApi()
                except Exception as kubeconfig_error:
                    print(
                        "⚠️ Kubernetes config not available for Istio traffic management: "
                        f"in-cluster error={incluster_error}, kubeconfig error={kubeconfig_error}"
                    )

    async def configure_route(self, route: TrafficRoute) -> bool:
        """Configure Istio Virtual Service"""

        try:
            print(f"⚙️ Configuring Istio route: {route.name}")

            # Create Virtual Service manifest
            virtual_service = self._create_virtual_service(route)

            # Apply Virtual Service
            if self.kubernetes_client:
                await self._apply_virtual_service(virtual_service)
            else:
                # Mock configuration
                print("📋 Mock Istio VirtualService configuration:")
                print(json.dumps(virtual_service, indent=2))

            # Create Destination Rules for each destination
            for destination in route.destinations:
                if destination.subset:
                    destination_rule = self._create_destination_rule(destination)

                    if self.kubernetes_client:
                        await self._apply_destination_rule(destination_rule)
                    else:
                        print("📋 Mock Istio DestinationRule configuration:")
                        print(json.dumps(destination_rule, indent=2))

            self.routes[route.name] = route
            return True

        except Exception as e:
            print(f"❌ Failed to configure Istio route {route.name}: {e}")
            return False

    async def update_traffic_split(
        self, route_name: str, destinations: builtins.list[TrafficDestination]
    ) -> bool:
        """Update traffic split in Istio Virtual Service"""

        try:
            if route_name not in self.routes:
                print(f"❌ Route {route_name} not found")
                return False

            route = self.routes[route_name]
            route.destinations = destinations

            print(f"🔄 Updating Istio traffic split for {route_name}")

            # Update Virtual Service
            virtual_service = self._create_virtual_service(route)

            if self.kubernetes_client:
                await self._update_virtual_service(virtual_service)
            else:
                # Mock update
                weights = {dest.name: dest.weight for dest in destinations}
                print(f"📊 Traffic split updated: {weights}")

            return True

        except Exception as e:
            print(f"❌ Failed to update traffic split for {route_name}: {e}")
            return False

    async def apply_policy(self, policy: TrafficPolicy) -> bool:
        """Apply Istio traffic policy"""

        try:
            print(f"📐 Applying Istio policy: {policy.name}")

            # Create Destination Rule with traffic policy
            destination_rule = self._create_policy_destination_rule(policy)

            if self.kubernetes_client:
                await self._apply_destination_rule(destination_rule)
            else:
                print("📋 Mock Istio policy configuration:")
                print(json.dumps(destination_rule, indent=2))

            self.policies[policy.name] = policy
            return True

        except Exception as e:
            print(f"❌ Failed to apply Istio policy {policy.name}: {e}")
            return False

    async def get_traffic_metrics(self, route_name: str) -> builtins.dict[str, Any]:
        """Get traffic metrics from Istio/Prometheus"""

        try:
            # Mock metrics - would query Prometheus/Grafana
            metrics = {
                "total_requests": 1000,
                "success_rate": 0.998,
                "avg_response_time": 45.2,
                "p95_response_time": 120.5,
                "error_rate": 0.002,
                "destinations": {},
            }

            if route_name in self.routes:
                route = self.routes[route_name]
                for dest in route.destinations:
                    metrics["destinations"][dest.name] = {
                        "requests": int(1000 * (dest.weight / 100)),
                        "success_rate": 0.99 + (dest.weight / 10000),
                        "avg_response_time": 40 + (dest.weight / 10),
                    }

            return metrics

        except Exception as e:
            print(f"❌ Failed to get traffic metrics for {route_name}: {e}")
            return {}

    async def validate_configuration(self) -> builtins.dict[str, Any]:
        """Validate Istio configuration"""

        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "routes_checked": len(self.routes),
            "policies_checked": len(self.policies),
        }

        try:
            # Validate routes
            for _route_name, route in self.routes.items():
                route_validation = self._validate_route(route)
                if not route_validation["valid"]:
                    validation_results["valid"] = False
                    validation_results["errors"].extend(route_validation["errors"])
                validation_results["warnings"].extend(route_validation["warnings"])

            # Validate policies
            for _policy_name, policy in self.policies.items():
                policy_validation = self._validate_policy(policy)
                if not policy_validation["valid"]:
                    validation_results["valid"] = False
                    validation_results["errors"].extend(policy_validation["errors"])
                validation_results["warnings"].extend(policy_validation["warnings"])

        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation error: {e}")

        return validation_results

    def _create_virtual_service(self, route: TrafficRoute) -> builtins.dict[str, Any]:
        """Create Istio Virtual Service manifest"""

        # Build HTTP routes
        http_routes = []

        # Create match conditions
        match_conditions = []
        if route.match_headers:
            for header, value in route.match_headers.items():
                match_conditions.append({"headers": {header: {"exact": value}}})

        if route.match_paths:
            for path in route.match_paths:
                match_conditions.append({"uri": {"prefix": path}})

        # If no specific match conditions, match all
        if not match_conditions:
            match_conditions = [{}]

        # Build destinations
        destinations = []
        total_weight = sum(dest.weight for dest in route.destinations)

        for dest in route.destinations:
            # Normalize weights to sum to 100
            normalized_weight = int((dest.weight / total_weight) * 100) if total_weight > 0 else 0

            destination = {
                "destination": {"host": dest.host, "port": {"number": dest.port}},
                "weight": normalized_weight,
            }

            if dest.subset:
                destination["destination"]["subset"] = dest.subset

            destinations.append(destination)

        # Build HTTP route
        http_route = {
            "match": match_conditions,
            "route": destinations,
            "timeout": f"{route.timeout}s",
        }

        # Add retries if configured
        if route.retries > 0:
            http_route["retries"] = {
                "attempts": route.retries,
                "retryOn": ",".join(route.retry_on),
            }

        # Add fault injection for testing (optional)
        # http_route['fault'] = {...}

        http_routes.append(http_route)

        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {"name": route.name, "namespace": "default"},
            "spec": {
                "hosts": [route.destinations[0].host if route.destinations else "*"],
                "http": http_routes,
            },
        }

    def _create_destination_rule(self, destination: TrafficDestination) -> builtins.dict[str, Any]:
        """Create Istio Destination Rule manifest"""

        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": f"{destination.name}-destination-rule",
                "namespace": "default",
            },
            "spec": {
                "host": destination.host,
                "subsets": [{"name": destination.subset, "labels": destination.labels}]
                if destination.subset
                else [],
                "trafficPolicy": {
                    "loadBalancer": {"simple": destination.load_balancer_policy.upper()}
                },
            },
        }

    def _create_policy_destination_rule(self, policy: TrafficPolicy) -> builtins.dict[str, Any]:
        """Create Destination Rule with traffic policy"""

        traffic_policy = {}

        # Load balancer settings
        if policy.load_balancer:
            traffic_policy["loadBalancer"] = policy.load_balancer

        # Connection pool settings
        if policy.connection_pool:
            traffic_policy["connectionPool"] = policy.connection_pool

        # Circuit breaker settings
        if policy.circuit_breaker:
            traffic_policy["outlierDetection"] = policy.circuit_breaker

        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": f"{policy.name}-policy",
                "namespace": policy.namespace,
            },
            "spec": {"host": policy.name, "trafficPolicy": traffic_policy},
        }

    async def _apply_virtual_service(self, virtual_service: builtins.dict[str, Any]):
        """Apply Virtual Service to Kubernetes"""

        try:
            self.kubernetes_client.create_namespaced_custom_object(
                group="networking.istio.io",
                version="v1beta1",
                namespace=virtual_service["metadata"]["namespace"],
                plural="virtualservices",
                body=virtual_service,
            )
        except Exception as e:
            if "already exists" in str(e):
                await self._update_virtual_service(virtual_service)
            else:
                raise e

    async def _update_virtual_service(self, virtual_service: builtins.dict[str, Any]):
        """Update Virtual Service in Kubernetes"""

        self.kubernetes_client.patch_namespaced_custom_object(
            group="networking.istio.io",
            version="v1beta1",
            namespace=virtual_service["metadata"]["namespace"],
            plural="virtualservices",
            name=virtual_service["metadata"]["name"],
            body=virtual_service,
        )

    async def _apply_destination_rule(self, destination_rule: builtins.dict[str, Any]):
        """Apply Destination Rule to Kubernetes"""

        try:
            self.kubernetes_client.create_namespaced_custom_object(
                group="networking.istio.io",
                version="v1beta1",
                namespace=destination_rule["metadata"]["namespace"],
                plural="destinationrules",
                body=destination_rule,
            )
        except Exception as e:
            if "already exists" in str(e):
                self.kubernetes_client.patch_namespaced_custom_object(
                    group="networking.istio.io",
                    version="v1beta1",
                    namespace=destination_rule["metadata"]["namespace"],
                    plural="destinationrules",
                    name=destination_rule["metadata"]["name"],
                    body=destination_rule,
                )
            else:
                raise e

    def _validate_route(self, route: TrafficRoute) -> builtins.dict[str, Any]:
        """Validate route configuration"""

        validation = {"valid": True, "errors": [], "warnings": []}

        # Check destinations
        if not route.destinations:
            validation["valid"] = False
            validation["errors"].append(f"Route {route.name} has no destinations")

        # Check weights sum to 100
        total_weight = sum(dest.weight for dest in route.destinations)
        if total_weight != 100:
            validation["warnings"].append(
                f"Route {route.name} destination weights sum to {total_weight}, not 100"
            )

        # Check destination hosts
        for dest in route.destinations:
            if not dest.host:
                validation["valid"] = False
                validation["errors"].append(f"Destination {dest.name} missing host")

        return validation

    def _validate_policy(self, policy: TrafficPolicy) -> builtins.dict[str, Any]:
        """Validate policy configuration"""

        validation = {"valid": True, "errors": [], "warnings": []}

        # Validate circuit breaker settings
        if policy.circuit_breaker:
            cb = policy.circuit_breaker
            if "consecutiveErrors" in cb and cb["consecutiveErrors"] < 1:
                validation["errors"].append(
                    f"Policy {policy.name} circuit breaker consecutiveErrors must be >= 1"
                )
                validation["valid"] = False

        # Validate retry policy
        if policy.retry_policy:
            rp = policy.retry_policy
            if "attempts" in rp and rp["attempts"] < 1:
                validation["errors"].append(f"Policy {policy.name} retry attempts must be >= 1")
                validation["valid"] = False

        return validation


class NginxTrafficManager(TrafficManagerBase):
    """
    NGINX Ingress Controller traffic management implementation

    Features:
    - Ingress configuration
    - Upstream management
    - Load balancing strategies
    - Rate limiting and SSL termination
    """

    def __init__(self):
        super().__init__(TrafficBackend.NGINX)
        self.kubernetes_client = None

        if KUBERNETES_AVAILABLE:
            try:
                config.load_incluster_config()
                self.kubernetes_client = client.NetworkingV1Api()
            except Exception as incluster_error:
                try:
                    config.load_kube_config()
                    self.kubernetes_client = client.NetworkingV1Api()
                except Exception as kubeconfig_error:
                    print(
                        "⚠️ Kubernetes config not available for NGINX traffic management: "
                        f"in-cluster error={incluster_error}, kubeconfig error={kubeconfig_error}"
                    )

    async def configure_route(self, route: TrafficRoute) -> bool:
        """Configure NGINX Ingress"""

        try:
            print(f"⚙️ Configuring NGINX route: {route.name}")

            # Create Ingress manifest
            ingress = self._create_ingress(route)

            if self.kubernetes_client:
                await self._apply_ingress(ingress)
            else:
                print("📋 Mock NGINX Ingress configuration:")
                print(json.dumps(ingress, indent=2))

            # Create ConfigMap for upstream configuration
            configmap = self._create_upstream_configmap(route)

            if self.kubernetes_client:
                core_v1 = client.CoreV1Api()
                await self._apply_configmap(core_v1, configmap)
            else:
                print("📋 Mock NGINX upstream configuration:")
                print(json.dumps(configmap, indent=2))

            self.routes[route.name] = route
            return True

        except Exception as e:
            print(f"❌ Failed to configure NGINX route {route.name}: {e}")
            return False

    async def update_traffic_split(
        self, route_name: str, destinations: builtins.list[TrafficDestination]
    ) -> bool:
        """Update traffic split in NGINX upstream"""

        try:
            if route_name not in self.routes:
                print(f"❌ Route {route_name} not found")
                return False

            route = self.routes[route_name]
            route.destinations = destinations

            print(f"🔄 Updating NGINX traffic split for {route_name}")

            # Update upstream ConfigMap
            configmap = self._create_upstream_configmap(route)

            if self.kubernetes_client:
                core_v1 = client.CoreV1Api()
                await self._update_configmap(core_v1, configmap)
            else:
                weights = {dest.name: dest.weight for dest in destinations}
                print(f"📊 Traffic split updated: {weights}")

            return True

        except Exception as e:
            print(f"❌ Failed to update NGINX traffic split for {route_name}: {e}")
            return False

    async def apply_policy(self, policy: TrafficPolicy) -> bool:
        """Apply NGINX traffic policy via ConfigMap"""

        try:
            print(f"📐 Applying NGINX policy: {policy.name}")

            # Mock policy application
            print("📋 NGINX policy configuration:")
            print(f"  Rate limit: {policy.rate_limit}")
            print(f"  Connection pool: {policy.connection_pool}")
            print(f"  Timeout: {policy.timeout}")

            self.policies[policy.name] = policy
            return True

        except Exception as e:
            print(f"❌ Failed to apply NGINX policy {policy.name}: {e}")
            return False

    async def get_traffic_metrics(self, route_name: str) -> builtins.dict[str, Any]:
        """Get traffic metrics from NGINX"""

        try:
            # Mock metrics - would query NGINX status endpoint
            metrics = {
                "total_requests": 800,
                "success_rate": 0.995,
                "avg_response_time": 52.1,
                "p95_response_time": 140.2,
                "error_rate": 0.005,
                "active_connections": 45,
            }

            return metrics

        except Exception as e:
            print(f"❌ Failed to get NGINX traffic metrics for {route_name}: {e}")
            return {}

    async def validate_configuration(self) -> builtins.dict[str, Any]:
        """Validate NGINX configuration"""

        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "routes_checked": len(self.routes),
            "policies_checked": len(self.policies),
        }

        # Basic validation for NGINX
        for route_name, route in self.routes.items():
            if not route.destinations:
                validation_results["valid"] = False
                validation_results["errors"].append(f"Route {route_name} has no destinations")

        return validation_results

    def _create_ingress(self, route: TrafficRoute) -> builtins.dict[str, Any]:
        """Create NGINX Ingress manifest"""

        # Build ingress rules
        rules = []
        if route.destinations:
            primary_dest = route.destinations[0]

            rule = {"host": primary_dest.host, "http": {"paths": []}}

            # Add paths
            paths = route.match_paths if route.match_paths else ["/"]
            for path in paths:
                path_config = {
                    "path": path,
                    "pathType": "Prefix",
                    "backend": {
                        "service": {
                            "name": route.name,
                            "port": {"number": primary_dest.port},
                        }
                    },
                }
                rule["http"]["paths"].append(path_config)

            rules.append(rule)

        # Build annotations
        annotations = {
            "kubernetes.io/ingress.class": "nginx",
            "nginx.ingress.kubernetes.io/rewrite-target": "/",
        }

        # Add rate limiting if configured
        if route.rate_limit:
            annotations.update(
                {
                    "nginx.ingress.kubernetes.io/rate-limit": str(
                        route.rate_limit.get("requests_per_second", 100)
                    ),
                    "nginx.ingress.kubernetes.io/rate-limit-window": "1s",
                }
            )

        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": route.name,
                "namespace": "default",
                "annotations": annotations,
            },
            "spec": {"rules": rules},
        }

    def _create_upstream_configmap(self, route: TrafficRoute) -> builtins.dict[str, Any]:
        """Create ConfigMap for NGINX upstream configuration"""

        # Build upstream configuration
        upstream_config = f"""
upstream {route.name} {{
"""

        for dest in route.destinations:
            weight = f"weight={dest.weight}" if dest.weight != 100 else ""
            upstream_config += f"    server {dest.host}:{dest.port} {weight};\n"

        upstream_config += "}\n"

        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": f"{route.name}-upstream", "namespace": "default"},
            "data": {"upstream.conf": upstream_config},
        }

    async def _apply_ingress(self, ingress: builtins.dict[str, Any]):
        """Apply Ingress to Kubernetes"""

        try:
            self.kubernetes_client.create_namespaced_ingress(
                namespace=ingress["metadata"]["namespace"], body=ingress
            )
        except Exception as e:
            if "already exists" in str(e):
                self.kubernetes_client.patch_namespaced_ingress(
                    name=ingress["metadata"]["name"],
                    namespace=ingress["metadata"]["namespace"],
                    body=ingress,
                )
            else:
                raise e

    async def _apply_configmap(self, core_v1: client.CoreV1Api, configmap: builtins.dict[str, Any]):
        """Apply ConfigMap to Kubernetes"""

        try:
            core_v1.create_namespaced_config_map(
                namespace=configmap["metadata"]["namespace"], body=configmap
            )
        except Exception as e:
            if "already exists" in str(e):
                await self._update_configmap(core_v1, configmap)
            else:
                raise e

    async def _update_configmap(
        self, core_v1: client.CoreV1Api, configmap: builtins.dict[str, Any]
    ):
        """Update ConfigMap in Kubernetes"""

        core_v1.patch_namespaced_config_map(
            name=configmap["metadata"]["name"],
            namespace=configmap["metadata"]["namespace"],
            body=configmap,
        )


class TrafficManagerFactory:
    """
    Factory for creating traffic manager instances

    Supports multiple traffic management backends
    """

    @staticmethod
    def create_manager(backend: TrafficBackend) -> TrafficManagerBase:
        """Create traffic manager for specified backend"""

        if backend == TrafficBackend.ISTIO:
            return IstioTrafficManager()
        if backend == TrafficBackend.NGINX:
            return NginxTrafficManager()
        raise ValueError(f"Unsupported traffic backend: {backend.value}")


class TrafficOrchestrator:
    """
    Traffic management orchestrator

    Features:
    - Multi-backend support
    - Traffic split management
    - Policy enforcement
    - Metrics aggregation
    """

    def __init__(self, primary_backend: TrafficBackend = TrafficBackend.ISTIO):
        self.primary_backend = primary_backend
        self.managers: builtins.dict[TrafficBackend, TrafficManagerBase] = {}

        # Initialize primary manager
        self.managers[primary_backend] = TrafficManagerFactory.create_manager(primary_backend)

        # Traffic operations
        self.active_splits: builtins.dict[str, builtins.dict[str, Any]] = {}

    def add_backend(self, backend: TrafficBackend):
        """Add additional traffic management backend"""

        if backend not in self.managers:
            self.managers[backend] = TrafficManagerFactory.create_manager(backend)
            print(f"➕ Added {backend.value} traffic manager")

    async def configure_route(
        self, route: TrafficRoute, backends: builtins.list[TrafficBackend] | None = None
    ) -> builtins.dict[TrafficBackend, bool]:
        """Configure traffic route across specified backends"""

        if backends is None:
            backends = [self.primary_backend]

        results = {}

        for backend in backends:
            if backend not in self.managers:
                self.add_backend(backend)

            try:
                success = await self.managers[backend].configure_route(route)
                results[backend] = success

                if success:
                    print(f"✅ Route {route.name} configured on {backend.value}")
                else:
                    print(f"❌ Route {route.name} failed on {backend.value}")

            except Exception as e:
                print(f"❌ Route {route.name} error on {backend.value}: {e}")
                results[backend] = False

        return results

    async def execute_traffic_split(
        self,
        route_name: str,
        destinations: builtins.list[TrafficDestination],
        backends: builtins.list[TrafficBackend] | None = None,
    ) -> builtins.dict[TrafficBackend, bool]:
        """Execute traffic split across backends"""

        if backends is None:
            backends = [self.primary_backend]

        results = {}

        print(f"🔄 Executing traffic split for {route_name}")

        for backend in backends:
            if backend not in self.managers:
                results[backend] = False
                continue

            try:
                success = await self.managers[backend].update_traffic_split(
                    route_name, destinations
                )
                results[backend] = success

            except Exception as e:
                print(f"❌ Traffic split error on {backend.value}: {e}")
                results[backend] = False

        # Store split configuration
        if any(results.values()):
            self.active_splits[route_name] = {
                "destinations": [dest.to_dict() for dest in destinations],
                "timestamp": datetime.now().isoformat(),
                "backends": list(backends),
            }

        return results

    async def get_aggregated_metrics(self, route_name: str) -> builtins.dict[str, Any]:
        """Get aggregated traffic metrics across all backends"""

        aggregated_metrics = {
            "route_name": route_name,
            "backends": {},
            "summary": {
                "total_requests": 0,
                "avg_success_rate": 0.0,
                "avg_response_time": 0.0,
            },
        }

        backend_count = 0
        total_success_rate = 0.0
        total_response_time = 0.0

        for backend, manager in self.managers.items():
            try:
                metrics = await manager.get_traffic_metrics(route_name)
                if metrics:
                    aggregated_metrics["backends"][backend.value] = metrics

                    # Aggregate summary metrics
                    aggregated_metrics["summary"]["total_requests"] += metrics.get(
                        "total_requests", 0
                    )
                    total_success_rate += metrics.get("success_rate", 0.0)
                    total_response_time += metrics.get("avg_response_time", 0.0)
                    backend_count += 1

            except Exception as e:
                print(f"⚠️ Failed to get metrics from {backend.value}: {e}")

        # Calculate averages
        if backend_count > 0:
            aggregated_metrics["summary"]["avg_success_rate"] = total_success_rate / backend_count
            aggregated_metrics["summary"]["avg_response_time"] = total_response_time / backend_count

        return aggregated_metrics

    async def validate_all_configurations(self) -> builtins.dict[str, Any]:
        """Validate configurations across all backends"""

        validation_results = {
            "overall_valid": True,
            "backends": {},
            "summary": {
                "total_routes": 0,
                "total_policies": 0,
                "total_errors": 0,
                "total_warnings": 0,
            },
        }

        for backend, manager in self.managers.items():
            try:
                backend_validation = await manager.validate_configuration()
                validation_results["backends"][backend.value] = backend_validation

                if not backend_validation.get("valid", False):
                    validation_results["overall_valid"] = False

                # Aggregate summary
                validation_results["summary"]["total_routes"] += backend_validation.get(
                    "routes_checked", 0
                )
                validation_results["summary"]["total_policies"] += backend_validation.get(
                    "policies_checked", 0
                )
                validation_results["summary"]["total_errors"] += len(
                    backend_validation.get("errors", [])
                )
                validation_results["summary"]["total_warnings"] += len(
                    backend_validation.get("warnings", [])
                )

            except Exception as e:
                validation_results["overall_valid"] = False
                validation_results["backends"][backend.value] = {
                    "valid": False,
                    "errors": [f"Validation failed: {e}"],
                }

        return validation_results

    def get_active_splits(self) -> builtins.dict[str, Any]:
        """Get all active traffic splits"""
        return self.active_splits


# Example usage and demo
async def main():
    """Example usage of traffic management"""

    print("=== Traffic Management Demo ===")

    # Initialize traffic orchestrator
    orchestrator = TrafficOrchestrator(TrafficBackend.ISTIO)
    orchestrator.add_backend(TrafficBackend.NGINX)

    # Create traffic destinations
    stable_dest = TrafficDestination(
        name="api-stable",
        host="api.example.com",
        port=80,
        weight=80,
        subset="stable",
        labels={"version": "stable"},
    )

    canary_dest = TrafficDestination(
        name="api-canary",
        host="api.example.com",
        port=80,
        weight=20,
        subset="canary",
        labels={"version": "canary"},
    )

    # Create traffic route
    api_route = TrafficRoute(
        name="api-route",
        rule_type=RoutingRule.WEIGHTED,
        destinations=[stable_dest, canary_dest],
        match_paths=["/api/v1"],
        timeout=30,
        retries=3,
    )

    # Configure route
    print("\n⚙️ Configuring traffic route")
    route_results = await orchestrator.configure_route(
        api_route, backends=[TrafficBackend.ISTIO, TrafficBackend.NGINX]
    )
    print(f"Route configuration results: {route_results}")

    # Execute traffic split progression
    split_scenarios = [
        (90, 10),  # 90% stable, 10% canary
        (70, 30),  # 70% stable, 30% canary
        (50, 50),  # 50% stable, 50% canary
        (20, 80),  # 20% stable, 80% canary
        (0, 100),  # 0% stable, 100% canary
    ]

    for stable_weight, canary_weight in split_scenarios:
        print(f"\n🔄 Traffic Split: {stable_weight}% stable, {canary_weight}% canary")

        # Update destination weights
        stable_dest.weight = stable_weight
        canary_dest.weight = canary_weight

        # Execute split
        split_results = await orchestrator.execute_traffic_split(
            "api-route", [stable_dest, canary_dest], backends=[TrafficBackend.ISTIO]
        )

        print(f"Split results: {split_results}")

        # Get metrics
        metrics = await orchestrator.get_aggregated_metrics("api-route")
        print(f"Traffic metrics: {metrics['summary']}")

        # Wait between splits
        await asyncio.sleep(2)

    # Create and apply traffic policy
    print("\n📐 Applying traffic policy")
    policy = TrafficPolicy(
        name="api-policy",
        circuit_breaker={
            "consecutiveErrors": 5,
            "interval": "30s",
            "baseEjectionTime": "30s",
        },
        retry_policy={"attempts": 3, "retryOn": ["5xx", "timeout"]},
        rate_limit={"requests_per_second": 100},
    )

    await orchestrator.managers[TrafficBackend.ISTIO].apply_policy(policy)

    # Validate all configurations
    print("\n✅ Validating configurations")
    validation = await orchestrator.validate_all_configurations()
    print(f"Validation results: Overall valid: {validation['overall_valid']}")
    print(f"Summary: {validation['summary']}")

    # Show active splits
    active_splits = orchestrator.get_active_splits()
    print(f"\n📊 Active traffic splits: {len(active_splits)}")


if __name__ == "__main__":
    asyncio.run(main())
