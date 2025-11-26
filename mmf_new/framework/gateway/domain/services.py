"""
Gateway Domain Services
"""

import re
import fnmatch
import random
from abc import ABC, abstractmethod
from re import Pattern

from .models import (
    GatewayRequest,
    UpstreamGroup,
    UpstreamServer
)

# --- Routing Services ---

class RouteMatcher(ABC):
    """Abstract route matcher interface."""

    @abstractmethod
    def matches(self, pattern: str, path: str) -> bool:
        """Check if pattern matches path."""

    @abstractmethod
    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        """Extract parameters from matched path."""

class ExactMatcher(RouteMatcher):
    """Exact path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return pattern == path

    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        return {}

class PrefixMatcher(RouteMatcher):
    """Prefix path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return path.startswith(pattern)

    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        if self.matches(pattern, path):
            remaining = path[len(pattern) :].lstrip("/")
            return {"*": remaining} if remaining else {}
        return {}

class RegexMatcher(RouteMatcher):
    """Regular expression path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive
        self._compiled_patterns: dict[str, Pattern] = {}

    def _compile_pattern(self, pattern: str) -> Pattern:
        if pattern not in self._compiled_patterns:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled_patterns[pattern] = re.compile(pattern, flags)
        return self._compiled_patterns[pattern]

    def matches(self, pattern: str, path: str) -> bool:
        try:
            compiled = self._compile_pattern(pattern)
            return bool(compiled.match(path))
        except re.error:
            return False

    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        try:
            compiled = self._compile_pattern(pattern)
            match = compiled.match(path)
            return match.groupdict() if match else {}
        except re.error:
            return {}

class WildcardMatcher(RouteMatcher):
    """Wildcard path matching using shell-style patterns."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return fnmatch.fnmatch(path, pattern)

    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        if "*" in pattern:
            return {"wildcard": path}
        return {}

class TemplateMatcher(RouteMatcher):
    """Template-based path matching with parameter extraction."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive
        self._compiled_patterns: dict[str, tuple[Pattern, list[str]]] = {}

    def _compile_template(self, template: str) -> tuple[Pattern, list[str]]:
        if template not in self._compiled_patterns:
            param_names = []
            pattern = template

            # Find all parameters in {name} format
            for match in re.finditer(r"\{([^}]+)\}", template):
                param_name = match.group(1)
                param_names.append(param_name)
                # Replace with named regex group
                pattern = pattern.replace(f"{{{param_name}}}", f"(?P<{param_name}>[^/]+)")

            # Ensure full match
            pattern = f"^{pattern}$"
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled_patterns[template] = (re.compile(pattern, flags), param_names)

        return self._compiled_patterns[template]

    def matches(self, pattern: str, path: str) -> bool:
        try:
            regex, _ = self._compile_template(pattern)
            return bool(regex.match(path))
        except re.error:
            return False

    def extract_params(self, pattern: str, path: str) -> dict[str, str]:
        try:
            regex, _ = self._compile_template(pattern)
            match = regex.match(path)
            return match.groupdict() if match else {}
        except re.error:
            return {}

# --- Load Balancing Services ---

class LoadBalancer(ABC):
    """Abstract load balancer interface."""

    @abstractmethod
    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        """Select server from group for request."""

class RoundRobinBalancer(LoadBalancer):
    """Round-robin load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        server = healthy_servers[group.current_index % len(healthy_servers)]
        group.current_index += 1
        return server

class RandomBalancer(LoadBalancer):
    """Random load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None
        return random.choice(healthy_servers)

class LeastConnectionsBalancer(LoadBalancer):
    """Least connections load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Find server with minimum connections
        return min(healthy_servers, key=lambda s: s.current_connections)

class WeightedRoundRobinBalancer(LoadBalancer):
    """Weighted round-robin load balancer."""

    def select_server(self, group: UpstreamGroup, request: GatewayRequest) -> UpstreamServer | None:
        healthy_servers = group.get_healthy_servers()
        if not healthy_servers:
            return None

        # Simple weighted implementation
        # In a real implementation, this would be more sophisticated (e.g. smooth weighted round-robin)
        total_weight = sum(s.weight for s in healthy_servers)
        if total_weight == 0:
            return healthy_servers[0]

        # Select based on weight
        r = random.uniform(0, total_weight)
        current = 0
        for server in healthy_servers:
            current += server.weight
            if r <= current:
                return server

        return healthy_servers[-1]
