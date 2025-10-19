"""
Load Balancing Integration Module for API Gateway

Advanced load balancing integration with service discovery, health checking,
multiple algorithms, and sophisticated upstream management capabilities.
"""

import builtins
import hashlib
import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import requests

from .core import GatewayRequest, GatewayResponse

logger = logging.getLogger(__name__)


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


@dataclass
class UpstreamServer:
    """Upstream server configuration."""

    id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 1000

    # Health check settings
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_retries: int = 3

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60

    # Connection settings
    connect_timeout: int = 5
    read_timeout: int = 30
    max_retries: int = 3

    # Metadata
    tags: builtins.dict[str, str] = field(default_factory=dict)
    region: str | None = None
    zone: str | None = None
    version: str | None = None

    # Runtime state
    status: HealthStatus = HealthStatus.UNKNOWN
    current_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: float = 0.0
    response_times: builtins.list[float] = field(default_factory=list)
    circuit_breaker_open: bool = False
    circuit_breaker_last_failure: float = 0.0

    @property
    def url(self) -> str:
        """Get server URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def is_available(self) -> bool:
        """Check if server is available for requests."""
        if self.status != HealthStatus.HEALTHY:
            return False

        if self.circuit_breaker_enabled and self.circuit_breaker_open:
            # Check if recovery timeout has passed
            if time.time() - self.circuit_breaker_last_failure < self.recovery_timeout:
                return False
            # Try to close circuit breaker
            self.circuit_breaker_open = False

        return self.current_connections < self.max_connections

    @property
    def average_response_time(self) -> float:
        """Get average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def add_response_time(self, response_time: float):
        """Add response time measurement."""
        self.response_times.append(response_time)
        # Keep only recent measurements (last 100)
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]

    def record_request(self, success: bool = True):
        """Record request statistics."""
        self.total_requests += 1
        if not success:
            self.failed_requests += 1

            # Check circuit breaker
            if self.circuit_breaker_enabled:
                failure_rate = self.failed_requests / max(1, self.total_requests)
                if self.failed_requests >= self.failure_threshold or failure_rate > 0.5:
                    self.circuit_breaker_open = True
                    self.circuit_breaker_last_failure = time.time()


@dataclass
class UpstreamGroup:
    """Group of upstream servers."""

    name: str
    servers: builtins.list[UpstreamServer] = field(default_factory=list)
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
    sessions: builtins.dict[str, str] = field(default_factory=dict)  # session_id -> server_id

    def add_server(self, server: UpstreamServer):
        """Add server to group."""
        self.servers.append(server)

    def remove_server(self, server_id: str):
        """Remove server from group."""
        self.servers = [s for s in self.servers if s.id != server_id]

    def get_healthy_servers(self) -> builtins.list[UpstreamServer]:
        """Get list of healthy servers."""
        return [s for s in self.servers if s.is_available]


class LoadBalancer(ABC):
    """Abstract load balancer interface."""

    @abstractmethod
    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server from group for request."""
        raise NotImplementedError


class RoundRobinBalancer(LoadBalancer):
    """Round-robin load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server using round-robin algorithm."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Use round-robin selection
        server = healthy_servers[group.current_index % len(healthy_servers)]
        group.current_index += 1

        return server


class WeightedRoundRobinBalancer(LoadBalancer):
    """Weighted round-robin load balancer."""

    def __init__(self):
        self._current_weights: builtins.dict[str, builtins.dict[str, int]] = {}

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server using weighted round-robin algorithm."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Initialize weights if needed
        group_key = group.name
        if group_key not in self._current_weights:
            self._current_weights[group_key] = {}

        current_weights = self._current_weights[group_key]

        # Update current weights
        total_weight = 0
        for server in healthy_servers:
            if server.id not in current_weights:
                current_weights[server.id] = 0
            current_weights[server.id] += server.weight
            total_weight += server.weight

        # Find server with highest current weight
        best_server = None
        max_weight = -1

        for server in healthy_servers:
            if current_weights[server.id] > max_weight:
                max_weight = current_weights[server.id]
                best_server = server

        if best_server:
            # Reduce weight of selected server
            current_weights[best_server.id] -= total_weight

        return best_server


class LeastConnectionsBalancer(LoadBalancer):
    """Least connections load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server with least connections."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Find server with minimum connections
        return min(healthy_servers, key=lambda s: s.current_connections)


class WeightedLeastConnectionsBalancer(LoadBalancer):
    """Weighted least connections load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server based on weighted least connections."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Calculate weighted connections (connections / weight)
        def weighted_connections(server: UpstreamServer) -> float:
            return server.current_connections / max(1, server.weight)

        return min(healthy_servers, key=weighted_connections)


class RandomBalancer(LoadBalancer):
    """Random load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select random server."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        return random.choice(healthy_servers)


class WeightedRandomBalancer(LoadBalancer):
    """Weighted random load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server using weighted random selection."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Calculate total weight
        total_weight = sum(s.weight for s in healthy_servers)
        if total_weight == 0:
            return random.choice(healthy_servers)

        # Select random point in weight range
        random_weight = random.randint(1, total_weight)

        # Find server corresponding to random weight
        current_weight = 0
        for server in healthy_servers:
            current_weight += server.weight
            if random_weight <= current_weight:
                return server

        # Fallback to last server
        return healthy_servers[-1]


class ConsistentHashBalancer(LoadBalancer):
    """Consistent hash load balancer."""

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._hash_ring: builtins.dict[
            str, builtins.dict[int, str]
        ] = {}  # group_name -> {hash -> server_id}

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server using consistent hashing."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Build or update hash ring for group
        self._update_hash_ring(group, healthy_servers)

        # Generate request hash
        request_key = self._generate_request_key(request)
        request_hash = self._hash_function(request_key)

        # Find server in hash ring
        hash_ring = self._hash_ring[group.name]
        if not hash_ring:
            return random.choice(healthy_servers)

        # Find first server hash >= request hash
        sorted_hashes = sorted(hash_ring.keys())
        for server_hash in sorted_hashes:
            if server_hash >= request_hash:
                server_id = hash_ring[server_hash]
                return next((s for s in healthy_servers if s.id == server_id), None)

        # Wrap around to first server
        server_id = hash_ring[sorted_hashes[0]]
        return next((s for s in healthy_servers if s.id == server_id), None)

    def _update_hash_ring(self, group: UpstreamGroup, servers: builtins.list[UpstreamServer]):
        """Update hash ring for server group."""
        if group.name not in self._hash_ring:
            self._hash_ring[group.name] = {}

        hash_ring = self._hash_ring[group.name]

        # Clear existing ring
        hash_ring.clear()

        # Add virtual nodes for each server
        for server in servers:
            for i in range(self.virtual_nodes):
                virtual_key = f"{server.id}:{i}"
                virtual_hash = self._hash_function(virtual_key)
                hash_ring[virtual_hash] = server.id

    def _generate_request_key(self, request: GatewayRequest) -> str:
        """Generate hash key for request."""
        # Use client IP for consistent routing
        ip = request.get_header("X-Forwarded-For") or request.get_header("X-Real-IP") or "unknown"
        return ip.split(",")[0].strip()

    def _hash_function(self, key: str) -> int:
        """Hash function for consistent hashing."""
        return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


class IPHashBalancer(LoadBalancer):
    """IP hash load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server based on client IP hash."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Get client IP
        ip = request.get_header("X-Forwarded-For") or request.get_header("X-Real-IP") or "unknown"
        ip = ip.split(",")[0].strip()

        # Hash IP to select server
        ip_hash = hash(ip)
        server_index = ip_hash % len(healthy_servers)

        return healthy_servers[server_index]


class LeastResponseTimeBalancer(LoadBalancer):
    """Least response time load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server with least average response time."""
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Find server with minimum average response time
        return min(healthy_servers, key=lambda s: s.average_response_time)


class StickySessionBalancer(LoadBalancer):
    """Sticky session load balancer wrapper."""

    def __init__(self, underlying_balancer: LoadBalancer):
        self.underlying_balancer = underlying_balancer

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server using sticky sessions."""
        if not group.sticky_sessions:
            return self.underlying_balancer.select_server(group, request)

        # Check for existing session
        session_id = request.get_header(f"Cookie:{group.session_cookie_name}")
        if session_id and session_id in group.sessions:
            server_id = group.sessions[session_id]
            # Find server by ID
            for server in group.get_healthy_servers():
                if server.id == server_id:
                    return server

            # Server no longer available, remove session
            del group.sessions[session_id]

        # No existing session or server unavailable, select new server
        server = self.underlying_balancer.select_server(group, request)
        if server and session_id:
            # Create session mapping
            group.sessions[session_id] = server.id

        return server


class HealthChecker:
    """Health checker for upstream servers."""

    def __init__(self):
        self._check_threads: builtins.dict[str, threading.Thread] = {}
        self._stop_events: builtins.dict[str, threading.Event] = {}

    def start_health_checks(self, group: UpstreamGroup):
        """Start health checking for server group."""
        if not group.health_check_enabled:
            return

        for server in group.servers:
            if server.health_check_enabled and server.id not in self._check_threads:
                self._start_server_health_check(server)

    def stop_health_checks(self, group: UpstreamGroup):
        """Stop health checking for server group."""
        for server in group.servers:
            self._stop_server_health_check(server.id)

    def _start_server_health_check(self, server: UpstreamServer):
        """Start health checking for individual server."""
        stop_event = threading.Event()
        self._stop_events[server.id] = stop_event

        def health_check_loop():
            while not stop_event.is_set():
                try:
                    self._perform_health_check(server)
                except Exception as e:
                    logger.error(f"Health check error for {server.id}: {e}")

                # Wait for next check
                stop_event.wait(server.health_check_interval)

        thread = threading.Thread(target=health_check_loop, daemon=True)
        self._check_threads[server.id] = thread
        thread.start()

    def _stop_server_health_check(self, server_id: str):
        """Stop health checking for server."""
        if server_id in self._stop_events:
            self._stop_events[server_id].set()
            del self._stop_events[server_id]

        if server_id in self._check_threads:
            del self._check_threads[server_id]

    def _perform_health_check(self, server: UpstreamServer):
        """Perform health check for server."""

        start_time = time.time()

        try:
            health_url = f"{server.url}{server.health_check_path}"

            # Use SSL verification by default, only disable if explicitly configured
            # This addresses the security vulnerability while maintaining flexibility
            verify_ssl = getattr(server, "verify_ssl", True)

            response = requests.get(
                health_url,
                timeout=server.health_check_timeout,
                verify=verify_ssl,
            )

            response_time = time.time() - start_time
            server.add_response_time(response_time)

            if response.status_code == 200:
                server.status = HealthStatus.HEALTHY
                server.record_request(success=True)
            else:
                server.status = HealthStatus.UNHEALTHY
                server.record_request(success=False)

        except Exception as e:
            logger.debug(f"Health check failed for {server.id}: {e}")
            server.status = HealthStatus.UNHEALTHY
            server.record_request(success=False)

        server.last_health_check = time.time()


class LoadBalancingManager:
    """Manager for load balancing operations."""

    def __init__(self):
        self.groups: builtins.dict[str, UpstreamGroup] = {}
        self.balancers: builtins.dict[LoadBalancingAlgorithm, LoadBalancer] = {
            LoadBalancingAlgorithm.ROUND_ROBIN: RoundRobinBalancer(),
            LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN: WeightedRoundRobinBalancer(),
            LoadBalancingAlgorithm.LEAST_CONNECTIONS: LeastConnectionsBalancer(),
            LoadBalancingAlgorithm.WEIGHTED_LEAST_CONNECTIONS: WeightedLeastConnectionsBalancer(),
            LoadBalancingAlgorithm.RANDOM: RandomBalancer(),
            LoadBalancingAlgorithm.WEIGHTED_RANDOM: WeightedRandomBalancer(),
            LoadBalancingAlgorithm.CONSISTENT_HASH: ConsistentHashBalancer(),
            LoadBalancingAlgorithm.IP_HASH: IPHashBalancer(),
            LoadBalancingAlgorithm.LEAST_RESPONSE_TIME: LeastResponseTimeBalancer(),
        }
        self.health_checker = HealthChecker()

    def add_group(self, group: UpstreamGroup):
        """Add upstream group."""
        self.groups[group.name] = group
        self.health_checker.start_health_checks(group)

    def remove_group(self, name: str):
        """Remove upstream group."""
        if name in self.groups:
            group = self.groups[name]
            self.health_checker.stop_health_checks(group)
            del self.groups[name]

    def get_group(self, name: str) -> UpstreamGroup | None:
        """Get upstream group by name."""
        return self.groups.get(name)

    def select_server(self, group_name: str, request: GatewayRequest) -> UpstreamServer | None:
        """Select server from group for request."""
        group = self.groups.get(group_name)
        if not group:
            return None

        # Get balancer for algorithm
        balancer = self.balancers.get(group.algorithm)
        if not balancer:
            logger.error(f"Unsupported load balancing algorithm: {group.algorithm}")
            return None

        # Handle sticky sessions
        if group.sticky_sessions:
            balancer = StickySessionBalancer(balancer)

        return balancer.select_server(group, request)

    def record_request_start(self, server: UpstreamServer):
        """Record start of request to server."""
        server.current_connections += 1

    def record_request_end(
        self, server: UpstreamServer, response_time: float, success: bool = True
    ):
        """Record end of request to server."""
        server.current_connections = max(0, server.current_connections - 1)
        server.add_response_time(response_time)
        server.record_request(success)

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get load balancing statistics."""
        stats = {}

        for group_name, group in self.groups.items():
            group_stats = {
                "algorithm": group.algorithm.value,
                "total_servers": len(group.servers),
                "healthy_servers": len(group.get_healthy_servers()),
                "servers": [],
            }

            for server in group.servers:
                server_stats = {
                    "id": server.id,
                    "url": server.url,
                    "status": server.status.value,
                    "weight": server.weight,
                    "current_connections": server.current_connections,
                    "total_requests": server.total_requests,
                    "failed_requests": server.failed_requests,
                    "average_response_time": server.average_response_time,
                    "circuit_breaker_open": server.circuit_breaker_open,
                    "is_available": server.is_available,
                }
                group_stats["servers"].append(server_stats)

            stats[group_name] = group_stats

        return stats


class LoadBalancingMiddleware:
    """Load balancing middleware for API Gateway."""

    def __init__(self, manager: LoadBalancingManager | None = None):
        self.manager = manager or LoadBalancingManager()

    def process_request(self, request: GatewayRequest) -> GatewayResponse | None:
        """Process request for load balancing."""
        # Extract upstream group from route configuration
        route_config = getattr(request.context, "route_config", None)
        if not route_config or not route_config.upstream:
            return None

        # Select server
        server = self.manager.select_server(route_config.upstream, request)
        if not server:
            logger.error(f"No available servers in group: {route_config.upstream}")

            return GatewayResponse(status_code=503, body=b"Service Unavailable")

        # Store selected server in request context
        request.context["upstream_server"] = server

        # Record request start
        self.manager.record_request_start(server)

        return None

    def process_response(
        self,
        response: GatewayResponse,
        request: GatewayRequest,
        response_time: float,
        success: bool = True,
    ) -> GatewayResponse:
        """Process response for load balancing."""
        # Get server from request context
        server = request.context.get("upstream_server")
        if server:
            # Record request end
            self.manager.record_request_end(server, response_time, success)

        return response


# Convenience functions
def create_round_robin_group(
    name: str,
    servers: builtins.list[builtins.tuple[str, int]],
    weights: builtins.list[int] | None = None,
) -> UpstreamGroup:
    """Create round-robin upstream group."""
    group = UpstreamGroup(name=name, algorithm=LoadBalancingAlgorithm.ROUND_ROBIN)

    for i, (host, port) in enumerate(servers):
        weight = weights[i] if weights and i < len(weights) else 1
        server = UpstreamServer(id=f"{name}_server_{i}", host=host, port=port, weight=weight)
        group.add_server(server)

    return group


def create_weighted_group(
    name: str, servers: builtins.list[builtins.tuple[str, int, int]]
) -> UpstreamGroup:
    """Create weighted upstream group."""
    group = UpstreamGroup(name=name, algorithm=LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN)

    for i, (host, port, weight) in enumerate(servers):
        server = UpstreamServer(id=f"{name}_server_{i}", host=host, port=port, weight=weight)
        group.add_server(server)

    return group


def create_consistent_hash_group(
    name: str, servers: builtins.list[builtins.tuple[str, int]]
) -> UpstreamGroup:
    """Create consistent hash upstream group."""
    group = UpstreamGroup(name=name, algorithm=LoadBalancingAlgorithm.CONSISTENT_HASH)

    for i, (host, port) in enumerate(servers):
        server = UpstreamServer(id=f"{name}_server_{i}", host=host, port=port)
        group.add_server(server)

    return group
