"""
Enterprise Integration Patterns for Marty Microservices Framework

This module implements comprehensive enterprise integration patterns including API gateway
management, event-driven architecture, message brokers, external system connectors,
and enterprise service bus patterns.
"""

import base64
import builtins
import hashlib
import json
import logging
import random
import re
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, urlparse

# For HTTP operations
import aiohttp
import jwt


class IntegrationType(Enum):
    """Integration pattern types."""

    API_GATEWAY = "api_gateway"
    EVENT_DRIVEN = "event_driven"
    MESSAGE_BROKER = "message_broker"
    EXTERNAL_CONNECTOR = "external_connector"
    SERVICE_BUS = "service_bus"
    LEGACY_ADAPTER = "legacy_adapter"
    PROTOCOL_BRIDGE = "protocol_bridge"


class ProtocolType(Enum):
    """Communication protocol types."""

    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    MQTT = "mqtt"
    AMQP = "amqp"
    JMS = "jms"
    SOAP = "soap"
    FTP = "ftp"
    SFTP = "sftp"
    TCP = "tcp"
    UDP = "udp"


class AuthenticationType(Enum):
    """Authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    MTLS = "mtls"
    CUSTOM = "custom"


class RouteType(Enum):
    """API route types."""

    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    WILDCARD = "wildcard"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"
    GEOGRAPHIC = "geographic"


class MessagePattern(Enum):
    """Message exchange patterns."""

    REQUEST_REPLY = "request_reply"
    FIRE_AND_FORGET = "fire_and_forget"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    POINT_TO_POINT = "point_to_point"
    SCATTER_GATHER = "scatter_gather"
    AGGREGATOR = "aggregator"
    SPLITTER = "splitter"
    ROUTER = "router"


@dataclass
class APIRoute:
    """API route definition."""

    route_id: str
    path: str
    method: str
    route_type: RouteType = RouteType.EXACT

    # Backend configuration
    backend_service: str
    backend_path: str | None = None
    backend_protocol: ProtocolType = ProtocolType.HTTP

    # Security
    authentication: AuthenticationType = AuthenticationType.NONE
    authorization_required: bool = False
    required_scopes: builtins.list[str] = field(default_factory=list)

    # Rate limiting
    rate_limit_requests: int | None = None
    rate_limit_window: int | None = None  # seconds

    # Transformation
    request_transformation: str | None = None
    response_transformation: str | None = None

    # Caching
    cache_enabled: bool = False
    cache_ttl: int = 300  # seconds

    # Metadata
    tags: builtins.list[str] = field(default_factory=list)
    description: str = ""
    deprecated: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BackendService:
    """Backend service definition."""

    service_id: str
    name: str
    base_url: str
    protocol: ProtocolType = ProtocolType.HTTP

    # Load balancing
    endpoints: builtins.list[str] = field(default_factory=list)
    load_balancing: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    weights: builtins.dict[str, float] = field(default_factory=dict)

    # Health checking
    health_check_path: str = "/health"
    health_check_interval: int = 30
    health_check_timeout: int = 5
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60

    # Timeouts
    connect_timeout: int = 5
    request_timeout: int = 30

    # Security
    ssl_verify: bool = True
    client_certificate: str | None = None

    # Metadata
    version: str = "1.0.0"
    environment: str = "production"
    tags: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class SecurityPolicy:
    """Security policy definition."""

    policy_id: str
    name: str
    description: str

    # Authentication requirements
    authentication_methods: builtins.list[AuthenticationType]

    # Authorization rules
    required_roles: builtins.list[str] = field(default_factory=list)
    required_permissions: builtins.list[str] = field(default_factory=list)

    # IP restrictions
    allowed_ips: builtins.list[str] = field(default_factory=list)
    blocked_ips: builtins.list[str] = field(default_factory=list)

    # Request validation
    request_size_limit: int | None = None  # bytes
    content_type_restrictions: builtins.list[str] = field(default_factory=list)

    # Headers
    required_headers: builtins.list[str] = field(default_factory=list)
    forbidden_headers: builtins.list[str] = field(default_factory=list)

    # Rate limiting
    global_rate_limit: int | None = None
    per_user_rate_limit: int | None = None

    # CORS
    cors_enabled: bool = False
    cors_origins: builtins.list[str] = field(default_factory=list)
    cors_methods: builtins.list[str] = field(default_factory=list)
    cors_headers: builtins.list[str] = field(default_factory=list)


@dataclass
class EventDefinition:
    """Event definition for event-driven architecture."""

    event_id: str
    event_type: str
    version: str
    schema: builtins.dict[str, Any]

    # Event metadata
    source: str
    description: str = ""

    # Routing
    routing_key: str | None = None
    topic: str | None = None

    # Persistence
    persistent: bool = True
    ttl: int | None = None  # seconds

    # Serialization
    content_type: str = "application/json"
    compression: bool = False

    # Validation
    schema_validation: bool = True
    schema_registry: str | None = None


@dataclass
class MessageEndpoint:
    """Message broker endpoint."""

    endpoint_id: str
    name: str
    protocol: ProtocolType
    connection_string: str

    # Authentication
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool = False

    # Connection pooling
    max_connections: int = 10
    connection_timeout: int = 30

    # Message handling
    message_pattern: MessagePattern = MessagePattern.PUBLISH_SUBSCRIBE
    acknowledgment_required: bool = True
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)

    # Monitoring
    metrics_enabled: bool = True
    logging_enabled: bool = True


@dataclass
class IntegrationFlow:
    """Integration flow definition."""

    flow_id: str
    name: str
    description: str
    integration_type: IntegrationType

    # Flow configuration
    source: builtins.dict[str, Any]
    destination: builtins.dict[str, Any]
    transformations: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Error handling
    error_handling: builtins.dict[str, Any] = field(default_factory=dict)
    dead_letter_queue: str | None = None

    # Flow control
    enabled: bool = True
    max_concurrent: int = 10
    batch_size: int = 1

    # Monitoring
    metrics: builtins.dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class APIGateway:
    """Comprehensive API Gateway implementation."""

    def __init__(self):
        """Initialize API Gateway."""
        self.routes: builtins.dict[str, APIRoute] = {}
        self.backend_services: builtins.dict[str, BackendService] = {}
        self.security_policies: builtins.dict[str, SecurityPolicy] = {}

        # Route matching cache
        self.route_cache: builtins.dict[str, str] = {}

        # Rate limiting
        self.rate_limiters: builtins.dict[str, builtins.dict[str, Any]] = defaultdict(dict)

        # Circuit breakers
        self.circuit_breakers: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Request/response cache
        self.response_cache: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Metrics
        self.metrics: builtins.dict[str, Any] = defaultdict(int)
        self.latency_metrics: builtins.dict[str, builtins.list[float]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

    def register_route(self, route: APIRoute) -> bool:
        """Register API route."""
        try:
            with self._lock:
                self.routes[route.route_id] = route

                # Clear route cache
                self.route_cache.clear()

                logging.info(f"Registered route: {route.method} {route.path}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register route: {e}")
            return False

    def register_backend_service(self, service: BackendService) -> bool:
        """Register backend service."""
        try:
            with self._lock:
                self.backend_services[service.service_id] = service

                # Initialize circuit breaker
                if service.circuit_breaker_enabled:
                    self.circuit_breakers[service.service_id] = {
                        "state": "closed",
                        "failure_count": 0,
                        "last_failure_time": None,
                        "failure_threshold": service.failure_threshold,
                        "recovery_timeout": service.recovery_timeout,
                    }

                logging.info(f"Registered backend service: {service.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register backend service: {e}")
            return False

    def register_security_policy(self, policy: SecurityPolicy) -> bool:
        """Register security policy."""
        try:
            with self._lock:
                self.security_policies[policy.policy_id] = policy

                logging.info(f"Registered security policy: {policy.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register security policy: {e}")
            return False

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: builtins.dict[str, str],
        body: bytes,
        client_ip: str,
    ) -> builtins.dict[str, Any]:
        """Handle incoming API request."""
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            # Find matching route
            route = self._find_matching_route(method, path)
            if not route:
                return self._create_error_response(404, "Route not found", request_id)

            # Security validation
            security_result = await self._validate_security(route, headers, client_ip)
            if not security_result["valid"]:
                return self._create_error_response(
                    security_result["status_code"],
                    security_result["message"],
                    request_id,
                )

            # Rate limiting
            rate_limit_result = await self._check_rate_limit(
                route, client_ip, security_result.get("user_id")
            )
            if not rate_limit_result["allowed"]:
                return self._create_error_response(429, "Rate limit exceeded", request_id)

            # Check cache
            cache_key = self._generate_cache_key(route, method, path, headers, body)
            if route.cache_enabled:
                cached_response = self._get_cached_response(cache_key)
                if cached_response:
                    self.metrics["cache_hits"] += 1
                    return cached_response

            # Transform request
            transformed_request = await self._transform_request(route, headers, body)

            # Route to backend
            backend_response = await self._route_to_backend(
                route, transformed_request["headers"], transformed_request["body"]
            )

            # Transform response
            final_response = await self._transform_response(route, backend_response)

            # Cache response
            if route.cache_enabled and final_response["status_code"] == 200:
                self._cache_response(cache_key, final_response, route.cache_ttl)

            # Record metrics
            latency = (time.time() - start_time) * 1000
            self._record_metrics(route.route_id, latency, final_response["status_code"])

            return final_response

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self._record_metrics("unknown", latency, 500)

            logging.exception(f"Request handling error: {e}")
            return self._create_error_response(500, "Internal server error", request_id)

    def _find_matching_route(self, method: str, path: str) -> APIRoute | None:
        """Find matching route for request."""
        cache_key = f"{method}:{path}"

        # Check cache first
        if cache_key in self.route_cache:
            route_id = self.route_cache[cache_key]
            return self.routes.get(route_id)

        # Find matching route
        for route in self.routes.values():
            if route.method.upper() != method.upper():
                continue

            if self._path_matches(route, path):
                self.route_cache[cache_key] = route.route_id
                return route

        return None

    def _path_matches(self, route: APIRoute, path: str) -> bool:
        """Check if path matches route pattern."""
        if route.route_type == RouteType.EXACT:
            return route.path == path

        if route.route_type == RouteType.PREFIX:
            return path.startswith(route.path)

        if route.route_type == RouteType.REGEX:
            return bool(re.match(route.path, path))

        if route.route_type == RouteType.WILDCARD:
            # Simple wildcard matching (*, **)
            pattern = route.path.replace("*", "[^/]*").replace("[^/]*[^/]*", ".*")
            return bool(re.match(f"^{pattern}$", path))

        return False

    async def _validate_security(
        self, route: APIRoute, headers: builtins.dict[str, str], client_ip: str
    ) -> builtins.dict[str, Any]:
        """Validate security for request."""
        result = {"valid": True, "user_id": None, "roles": [], "permissions": []}

        # Authentication
        if route.authentication != AuthenticationType.NONE:
            auth_result = await self._authenticate_request(route.authentication, headers)

            if not auth_result["valid"]:
                return {
                    "valid": False,
                    "status_code": 401,
                    "message": auth_result.get("message", "Authentication failed"),
                }

            result.update(auth_result)

        # Authorization
        if route.authorization_required:
            if not result.get("user_id"):
                return {
                    "valid": False,
                    "status_code": 401,
                    "message": "Authentication required",
                }

            # Check required scopes
            user_scopes = result.get("scopes", [])
            if route.required_scopes and not any(
                scope in user_scopes for scope in route.required_scopes
            ):
                return {
                    "valid": False,
                    "status_code": 403,
                    "message": "Insufficient permissions",
                }

        return result

    async def _authenticate_request(
        self, auth_type: AuthenticationType, headers: builtins.dict[str, str]
    ) -> builtins.dict[str, Any]:
        """Authenticate request based on authentication type."""
        if auth_type == AuthenticationType.API_KEY:
            api_key = headers.get("X-API-Key") or headers.get("Authorization", "").replace(
                "ApiKey ", ""
            )
            if not api_key:
                return {"valid": False, "message": "API key required"}

            # Validate API key (simplified)
            # In practice, this would check against a database or cache
            if api_key.startswith("ak_"):
                return {
                    "valid": True,
                    "user_id": f"user_{api_key[-8:]}",
                    "scopes": ["read", "write"],
                }
            return {"valid": False, "message": "Invalid API key"}

        if auth_type == AuthenticationType.BEARER_TOKEN:
            auth_header = headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return {"valid": False, "message": "Bearer token required"}

            token = auth_header[7:]  # Remove "Bearer " prefix

            # Validate token (simplified)
            if len(token) >= 32:  # Basic validation
                return {
                    "valid": True,
                    "user_id": f"user_{token[-8:]}",
                    "scopes": ["read", "write"],
                }
            return {"valid": False, "message": "Invalid bearer token"}

        if auth_type == AuthenticationType.JWT:
            auth_header = headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return {"valid": False, "message": "JWT token required"}

            token = auth_header[7:]

            try:
                # Decode JWT (simplified - no signature verification)
                payload = jwt.decode(token, options={"verify_signature": False})

                return {
                    "valid": True,
                    "user_id": payload.get("sub"),
                    "scopes": payload.get("scope", "").split(),
                    "roles": payload.get("roles", []),
                    "permissions": payload.get("permissions", []),
                }

            except Exception as e:
                return {"valid": False, "message": f"Invalid JWT token: {e}"}

        elif auth_type == AuthenticationType.BASIC_AUTH:
            auth_header = headers.get("Authorization", "")
            if not auth_header.startswith("Basic "):
                return {"valid": False, "message": "Basic auth required"}

            # Decode basic auth (simplified)
            try:
                encoded_credentials = auth_header[6:]
                decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
                username, password = decoded_credentials.split(":", 1)

                # Validate credentials (simplified)
                if username == "admin" and password == "password":  # Demo only!
                    return {"valid": True, "user_id": username, "scopes": ["admin"]}
                return {"valid": False, "message": "Invalid credentials"}

            except Exception as e:
                return {"valid": False, "message": f"Invalid basic auth: {e}"}

        return {
            "valid": False,
            "message": f"Unsupported authentication type: {auth_type}",
        }

    async def _check_rate_limit(
        self, route: APIRoute, client_ip: str, user_id: str | None = None
    ) -> builtins.dict[str, bool]:
        """Check rate limiting for request."""
        if not route.rate_limit_requests:
            return {"allowed": True}

        current_time = time.time()
        window_start = current_time - route.rate_limit_window

        # Rate limit key (by IP or user)
        rate_limit_key = user_id if user_id else client_ip

        # Clean old entries
        if rate_limit_key in self.rate_limiters:
            self.rate_limiters[rate_limit_key] = {
                timestamp: count
                for timestamp, count in self.rate_limiters[rate_limit_key].items()
                if timestamp > window_start
            }

        # Count current requests
        current_requests = sum(self.rate_limiters[rate_limit_key].values())

        if current_requests >= route.rate_limit_requests:
            return {"allowed": False}

        # Record this request
        timestamp_key = int(current_time)
        self.rate_limiters[rate_limit_key][timestamp_key] = (
            self.rate_limiters[rate_limit_key].get(timestamp_key, 0) + 1
        )

        return {"allowed": True}

    async def _transform_request(
        self, route: APIRoute, headers: builtins.dict[str, str], body: bytes
    ) -> builtins.dict[str, Any]:
        """Transform request before sending to backend."""
        if not route.request_transformation:
            return {"headers": headers, "body": body}

        # Apply request transformation
        # This is a simplified example - in practice, would use a transformation engine
        transformed_headers = headers.copy()
        transformed_body = body

        # Example transformations
        if route.request_transformation == "add_auth_header":
            transformed_headers["X-Internal-Auth"] = "gateway-service"

        elif route.request_transformation == "json_to_xml":
            # Convert JSON body to XML (simplified)
            if headers.get("Content-Type") == "application/json":
                try:
                    json_data = json.loads(body.decode("utf-8"))
                    # This would use a proper JSON to XML converter
                    xml_data = f"<root>{json_data}</root>"
                    transformed_body = xml_data.encode("utf-8")
                    transformed_headers["Content-Type"] = "application/xml"
                except Exception as e:
                    logging.exception(f"JSON to XML transformation error: {e}")

        return {"headers": transformed_headers, "body": transformed_body}

    async def _route_to_backend(
        self, route: APIRoute, headers: builtins.dict[str, str], body: bytes
    ) -> builtins.dict[str, Any]:
        """Route request to backend service."""
        backend_service = self.backend_services.get(route.backend_service)
        if not backend_service:
            raise Exception(f"Backend service not found: {route.backend_service}")

        # Check circuit breaker
        if not self._is_circuit_breaker_closed(backend_service.service_id):
            raise Exception("Circuit breaker is open")

        # Select backend endpoint
        endpoint = self._select_backend_endpoint(backend_service)

        # Build backend URL
        backend_path = route.backend_path or route.path
        backend_url = f"{endpoint.rstrip('/')}/{backend_path.lstrip('/')}"

        try:
            # Make request to backend
            timeout = aiohttp.ClientTimeout(
                connect=backend_service.connect_timeout,
                total=backend_service.request_timeout,
            )

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=route.method,
                    url=backend_url,
                    headers=headers,
                    data=body,
                    ssl=backend_service.ssl_verify,
                ) as response:
                    response_body = await response.read()
                    response_headers = dict(response.headers)

                    # Record successful request
                    self._record_circuit_breaker_success(backend_service.service_id)

                    return {
                        "status_code": response.status,
                        "headers": response_headers,
                        "body": response_body,
                    }

        except Exception as e:
            # Record failure
            self._record_circuit_breaker_failure(backend_service.service_id)
            raise e

    def _select_backend_endpoint(self, service: BackendService) -> str:
        """Select backend endpoint based on load balancing strategy."""
        if not service.endpoints:
            return service.base_url

        if service.load_balancing == LoadBalancingStrategy.ROUND_ROBIN:
            # Simple round-robin (stateless)

            return random.choice(service.endpoints)

        if service.load_balancing == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            # Weighted selection
            if service.weights:
                endpoints = []
                for endpoint in service.endpoints:
                    weight = service.weights.get(endpoint, 1.0)
                    endpoints.extend([endpoint] * int(weight * 10))

                if endpoints:
                    return random.choice(endpoints)

            return random.choice(service.endpoints)

        if service.load_balancing == LoadBalancingStrategy.RANDOM:
            return random.choice(service.endpoints)

        # Default to first endpoint
        return service.endpoints[0]

    def _is_circuit_breaker_closed(self, service_id: str) -> bool:
        """Check if circuit breaker is closed (allowing requests)."""
        if service_id not in self.circuit_breakers:
            return True

        cb = self.circuit_breakers[service_id]

        if cb["state"] == "closed":
            return True

        if cb["state"] == "open":
            # Check if recovery timeout has passed
            if cb["last_failure_time"]:
                elapsed = time.time() - cb["last_failure_time"]
                if elapsed > cb["recovery_timeout"]:
                    cb["state"] = "half_open"
                    return True
            return False

        if cb["state"] == "half_open":
            return True

        return False

    def _record_circuit_breaker_success(self, service_id: str):
        """Record successful request for circuit breaker."""
        if service_id in self.circuit_breakers:
            cb = self.circuit_breakers[service_id]
            cb["failure_count"] = 0
            if cb["state"] == "half_open":
                cb["state"] = "closed"

    def _record_circuit_breaker_failure(self, service_id: str):
        """Record failed request for circuit breaker."""
        if service_id in self.circuit_breakers:
            cb = self.circuit_breakers[service_id]
            cb["failure_count"] += 1
            cb["last_failure_time"] = time.time()

            if cb["failure_count"] >= cb["failure_threshold"]:
                cb["state"] = "open"

    async def _transform_response(
        self, route: APIRoute, response: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Transform response before returning to client."""
        if not route.response_transformation:
            return response

        # Apply response transformation
        transformed_response = response.copy()

        # Example transformations
        if route.response_transformation == "add_gateway_headers":
            transformed_response["headers"]["X-Gateway"] = "marty-api-gateway"
            transformed_response["headers"]["X-Response-Time"] = str(time.time())

        elif route.response_transformation == "xml_to_json":
            # Convert XML response to JSON (simplified)
            if response["headers"].get("Content-Type") == "application/xml":
                try:
                    # This would use a proper XML to JSON converter
                    xml_data = response["body"].decode("utf-8")
                    json_data = {"xml_content": xml_data}  # Simplified conversion

                    transformed_response["body"] = json.dumps(json_data).encode("utf-8")
                    transformed_response["headers"]["Content-Type"] = "application/json"
                except Exception as e:
                    logging.exception(f"XML to JSON transformation error: {e}")

        return transformed_response

    def _generate_cache_key(
        self,
        route: APIRoute,
        method: str,
        path: str,
        headers: builtins.dict[str, str],
        body: bytes,
    ) -> str:
        """Generate cache key for response."""
        # Include relevant parts in cache key
        cache_input = {
            "route_id": route.route_id,
            "method": method,
            "path": path,
            "query_params": parse_qs(urlparse(path).query),
            "body_hash": hashlib.sha256(body).hexdigest() if body else None,
        }

        cache_string = json.dumps(cache_input, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]

    def _get_cached_response(self, cache_key: str) -> builtins.dict[str, Any] | None:
        """Get cached response."""
        if cache_key in self.response_cache:
            cache_entry = self.response_cache[cache_key]

            # Check expiration
            if time.time() < cache_entry["expires_at"]:
                return cache_entry["response"]
            # Remove expired entry
            del self.response_cache[cache_key]

        return None

    def _cache_response(self, cache_key: str, response: builtins.dict[str, Any], ttl: int):
        """Cache response."""
        self.response_cache[cache_key] = {
            "response": response,
            "cached_at": time.time(),
            "expires_at": time.time() + ttl,
        }

    def _create_error_response(
        self, status_code: int, message: str, request_id: str
    ) -> builtins.dict[str, Any]:
        """Create error response."""
        return {
            "status_code": status_code,
            "headers": {"Content-Type": "application/json", "X-Request-ID": request_id},
            "body": json.dumps(
                {
                    "error": {
                        "code": status_code,
                        "message": message,
                        "request_id": request_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                }
            ).encode("utf-8"),
        }

    def _record_metrics(self, route_id: str, latency: float, status_code: int):
        """Record request metrics."""
        with self._lock:
            self.metrics["total_requests"] += 1
            self.metrics[f"requests_{route_id}"] = self.metrics.get(f"requests_{route_id}", 0) + 1

            if 200 <= status_code < 300:
                self.metrics["successful_requests"] += 1
            elif 400 <= status_code < 500:
                self.metrics["client_errors"] += 1
            elif 500 <= status_code < 600:
                self.metrics["server_errors"] += 1

            self.latency_metrics[route_id].append(latency)

            # Keep only recent latency metrics
            if len(self.latency_metrics[route_id]) > 1000:
                self.latency_metrics[route_id] = self.latency_metrics[route_id][-1000:]

    def get_gateway_status(self) -> builtins.dict[str, Any]:
        """Get gateway status and metrics."""
        with self._lock:
            # Calculate average latencies
            avg_latencies = {}
            for route_id, latencies in self.latency_metrics.items():
                if latencies:
                    avg_latencies[route_id] = sum(latencies) / len(latencies)

            return {
                "total_routes": len(self.routes),
                "total_backend_services": len(self.backend_services),
                "total_security_policies": len(self.security_policies),
                "metrics": dict(self.metrics),
                "average_latencies": avg_latencies,
                "cache_size": len(self.response_cache),
                "circuit_breaker_status": {
                    service_id: cb["state"] for service_id, cb in self.circuit_breakers.items()
                },
            }


def create_api_gateway() -> APIGateway:
    """Create API Gateway instance."""
    return APIGateway()
