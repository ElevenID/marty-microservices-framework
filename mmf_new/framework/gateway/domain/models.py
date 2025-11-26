"""
Gateway Domain Models
"""

import time
import uuid
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class HTTPMethod(Enum):
    """HTTP methods supported by the gateway."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
    CONNECT = "CONNECT"

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

class RoutingStrategy(Enum):
    """Routing strategy types."""
    PATH_BASED = "path_based"
    HOST_BASED = "host_based"
    HEADER_BASED = "header_based"
    WEIGHT_BASED = "weight_based"
    CANARY = "canary"
    AB_TEST = "ab_test"

class MatchType(Enum):
    """Route matching types."""
    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    WILDCARD = "wildcard"
    TEMPLATE = "template"

class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"
    CONSISTENT_HASH = "consistent_hash"
    IP_HASH = "ip_hash"
    LEAST_RESPONSE_TIME = "least_response_time"
    RESOURCE_BASED = "resource_based"

class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"

class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm types."""
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW_LOG = "sliding_window_log"
    SLIDING_WINDOW_COUNTER = "sliding_window_counter"

class RateLimitAction(Enum):
    """Actions to take when rate limit is exceeded."""
    REJECT = "reject"
    DELAY = "delay"
    THROTTLE = "throttle"
    LOG_ONLY = "log_only"

@dataclass
class GatewayRequest:
    """Gateway request object."""
    method: HTTPMethod
    path: str
    query_params: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None

    # Client information
    client_ip: str | None = None
    user_agent: str | None = None

    # Request metadata
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # Processing context
    route_params: dict[str, str] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    def get_header(self, name: str, default: str | None = None) -> str | None:
        """Get header value (case-insensitive)."""
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return default

@dataclass
class GatewayResponse:
    """Gateway response object."""
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None

    # Response metadata
    response_time: float | None = None
    upstream_service: str | None = None

    def set_header(self, name: str, value: str):
        """Set response header."""
        self.headers[name] = value

    def set_json_body(self, data: Any):
        """Set JSON response body."""
        self.body = json.dumps(data).encode("utf-8")
        self.set_header("Content-Type", "application/json")
        self.set_header("Content-Length", str(len(self.body)))

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_window: int = 100
    window_size_seconds: int = 60
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW_COUNTER
    action: RateLimitAction = RateLimitAction.REJECT
    delay_seconds: float = 1.0
    throttle_factor: float = 0.5

@dataclass
class UpstreamServer:
    """Upstream server configuration."""
    id: str
    host: str
    port: int
    protocol: ProtocolType = ProtocolType.HTTP
    weight: int = 1
    max_connections: int = 1000

    # Health check settings
    health_check_enabled: bool = True
    health_check_path: str = "/health"

    # Runtime state
    status: HealthStatus = HealthStatus.UNKNOWN
    current_connections: int = 0

    @property
    def url(self) -> str:
        return f"{self.protocol.value}://{self.host}:{self.port}"

@dataclass
class UpstreamGroup:
    """Group of upstream servers."""
    name: str
    servers: list[UpstreamServer] = field(default_factory=list)
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN

    # Group settings
    health_check_enabled: bool = True
    sticky_sessions: bool = False
    session_cookie_name: str = "GATEWAY_SESSION"
    session_timeout: int = 3600

    # Retry settings
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay: float = 0.1

    # Runtime state
    current_index: int = 0
    sessions: dict[str, str] = field(default_factory=dict)  # session_id -> server_id

    def add_server(self, server: UpstreamServer):
        """Add server to group."""
        self.servers.append(server)

    def remove_server(self, server_id: str):
        """Remove server from group."""
        self.servers = [s for s in self.servers if s.id != server_id]

    def get_healthy_servers(self) -> list[UpstreamServer]:
        """Get list of healthy servers."""
        # Note: is_available property needs to be added to UpstreamServer or logic moved here
        # For now assuming UpstreamServer has is_available property or logic
        return [s for s in self.servers if s.status == HealthStatus.HEALTHY]

@dataclass
class RouteConfig:
    """Configuration for a route."""
    path: str
    upstream: str
    methods: list[HTTPMethod] = field(default_factory=lambda: [HTTPMethod.GET])
    host: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    rewrite_path: str | None = None
    timeout: float = 30.0
    retries: int = 3
    rate_limit: RateLimitConfig | None = None
    auth_required: bool = True
    authentication_type: AuthenticationType = AuthenticationType.NONE
    name: str | None = None
    tags: list[str] = field(default_factory=list)

@dataclass
class RoutingRule:
    """Rule for routing decisions."""
    match_type: MatchType
    pattern: str
    weight: float = 1.0
    conditions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

class Route:
    """Individual route configuration and handlers."""
    def __init__(self, config: RouteConfig):
        self.config = config
        # Middleware and handlers would be added here, but we might want to keep them separate in domain
        # For now, keeping it simple as a wrapper around config
