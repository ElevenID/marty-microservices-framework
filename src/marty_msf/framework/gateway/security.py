"""
Security Module for API Gateway

Advanced security capabilities including CORS handling, security headers,
input validation, attack prevention, and comprehensive security policies.
"""

import builtins
import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .core import GatewayRequest, GatewayResponse

logger = logging.getLogger(__name__)


class SecurityThreat(Enum):
    """Security threat types."""

    XSS = "xss"
    SQL_INJECTION = "sql_injection"
    CSRF = "csrf"
    SSRF = "ssrf"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    LDAP_INJECTION = "ldap_injection"
    HEADER_INJECTION = "header_injection"
    XXE = "xxe"
    DESERIALIZATION = "deserialization"


@dataclass
class CORSConfig:
    """CORS configuration."""

    enabled: bool = True
    allow_origins: builtins.list[str] = field(default_factory=lambda: ["*"])
    allow_methods: builtins.list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    allow_headers: builtins.list[str] = field(
        default_factory=lambda: ["Content-Type", "Authorization"]
    )
    expose_headers: builtins.list[str] = field(default_factory=list)
    allow_credentials: bool = False
    max_age: int = 86400  # 24 hours

    # Advanced settings
    allow_private_network: bool = False
    vary_origin: bool = True


@dataclass
class SecurityHeadersConfig:
    """Security headers configuration."""

    # Content Security Policy
    csp_enabled: bool = True
    csp_policy: str = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    csp_report_only: bool = False

    # HSTS
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # Other security headers
    x_frame_options: str = "DENY"  # DENY, SAMEORIGIN, or ALLOW-FROM
    x_content_type_options: bool = True
    x_xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str | None = None

    # Custom headers
    custom_headers: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class ValidationConfig:
    """Input validation configuration."""

    enabled: bool = True
    validate_headers: bool = True
    validate_query_params: bool = True
    validate_body: bool = True
    validate_path: bool = True

    # Limits
    max_header_size: int = 8192  # 8KB
    max_query_param_size: int = 4096  # 4KB
    max_body_size: int = 10 * 1024 * 1024  # 10MB
    max_path_length: int = 2048

    # Validation rules
    allowed_content_types: builtins.set[str] = field(
        default_factory=lambda: {
            "application/json",
            "application/xml",
            "text/plain",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        }
    )

    # Character filtering
    block_null_bytes: bool = True
    block_control_chars: bool = True
    normalize_unicode: bool = True

    # Custom validation
    custom_validators: builtins.list[Callable[[str], bool]] = field(default_factory=list)


@dataclass
class AttackPreventionConfig:
    """Attack prevention configuration."""

    enabled: bool = True

    # XSS Prevention
    xss_protection: bool = True
    html_encode: bool = True
    script_tag_blocking: bool = True

    # SQL Injection Prevention
    sql_injection_protection: bool = True
    sql_keywords_blocking: bool = True

    # Path Traversal Prevention
    path_traversal_protection: bool = True
    directory_traversal_patterns: builtins.list[str] = field(
        default_factory=lambda: [
            "../",
            "..\\",
            "%2e%2e%2f",
            "%2e%2e%5c",
            "..%2f",
            "..%5c",
        ]
    )

    # Command Injection Prevention
    command_injection_protection: bool = True
    dangerous_commands: builtins.list[str] = field(
        default_factory=lambda: [
            "rm",
            "del",
            "format",
            "fdisk",
            "mkfs",
            "shutdown",
            "reboot",
        ]
    )

    # Rate limiting for attacks
    attack_rate_limit: bool = True
    attack_window_size: int = 300  # 5 minutes
    max_attacks_per_window: int = 10

    # Logging
    log_attacks: bool = True
    log_level: str = "WARNING"


@dataclass
class SecurityEvent:
    """Security event data."""

    timestamp: float
    threat_type: SecurityThreat
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    source_ip: str
    user_agent: str
    request_path: str
    details: builtins.dict[str, Any] = field(default_factory=dict)
    blocked: bool = False


class SecurityValidator(ABC):
    """Abstract security validator interface."""

    @abstractmethod
    def validate(
        self, data: str, context: builtins.dict[str, Any] = None
    ) -> builtins.list[SecurityThreat]:
        """Validate data and return list of detected threats."""
        raise NotImplementedError


class XSSValidator(SecurityValidator):
    """XSS attack validator."""

    def __init__(self):
        self.xss_patterns = [
            re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"vbscript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE),
            re.compile(r"<iframe[^>]*>", re.IGNORECASE),
            re.compile(r"<object[^>]*>", re.IGNORECASE),
            re.compile(r"<embed[^>]*>", re.IGNORECASE),
            re.compile(r"<meta[^>]*http-equiv", re.IGNORECASE),
            re.compile(r'<link[^>]*href\s*=\s*["\']?javascript:', re.IGNORECASE),
        ]

    def validate(
        self, data: str, context: builtins.dict[str, Any] = None
    ) -> builtins.list[SecurityThreat]:
        """Check for XSS patterns."""
        threats = []

        for pattern in self.xss_patterns:
            if pattern.search(data):
                threats.append(SecurityThreat.XSS)
                break

        return threats


class SQLInjectionValidator(SecurityValidator):
    """SQL injection attack validator."""

    def __init__(self):
        self.sql_patterns = [
            re.compile(r"\b(union\s+select|select\s+.*\s+from)\b", re.IGNORECASE),
            re.compile(r"\b(insert\s+into|update\s+.*\s+set|delete\s+from)\b", re.IGNORECASE),
            re.compile(r"\b(drop\s+table|create\s+table|alter\s+table)\b", re.IGNORECASE),
            re.compile(r"\b(exec\s*\(|execute\s*\(|sp_executesql)\b", re.IGNORECASE),
            re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE),
            re.compile(r"(\%3B)|(;)", re.IGNORECASE),
            re.compile(r"\b(or\s+1\s*=\s*1|and\s+1\s*=\s*1)\b", re.IGNORECASE),
            re.compile(r"\b(having\s+.*\s+count|group\s+by\s+.*\s+having)\b", re.IGNORECASE),
        ]

    def validate(
        self, data: str, context: builtins.dict[str, Any] = None
    ) -> builtins.list[SecurityThreat]:
        """Check for SQL injection patterns."""
        threats = []

        for pattern in self.sql_patterns:
            if pattern.search(data):
                threats.append(SecurityThreat.SQL_INJECTION)
                break

        return threats


class PathTraversalValidator(SecurityValidator):
    """Path traversal attack validator."""

    def __init__(self):
        self.traversal_patterns = [
            re.compile(r"\.\.[\\/]", re.IGNORECASE),
            re.compile(r"%2e%2e%2f", re.IGNORECASE),
            re.compile(r"%2e%2e%5c", re.IGNORECASE),
            re.compile(r"\.\.%2f", re.IGNORECASE),
            re.compile(r"\.\.%5c", re.IGNORECASE),
            re.compile(r"%2e%2e[\\/]", re.IGNORECASE),
            re.compile(r"\.\.\\", re.IGNORECASE),
        ]

    def validate(
        self, data: str, context: builtins.dict[str, Any] = None
    ) -> builtins.list[SecurityThreat]:
        """Check for path traversal patterns."""
        threats = []

        for pattern in self.traversal_patterns:
            if pattern.search(data):
                threats.append(SecurityThreat.PATH_TRAVERSAL)
                break

        return threats


class CommandInjectionValidator(SecurityValidator):
    """Command injection attack validator."""

    def __init__(self):
        self.command_patterns = [
            re.compile(r"[;&|`$\(\)]", re.IGNORECASE),
            re.compile(r"\b(nc|netcat|wget|curl|ping|nslookup|dig)\b", re.IGNORECASE),
            re.compile(r"\b(cat|type|more|less|head|tail)\b", re.IGNORECASE),
            re.compile(r"\b(rm|del|rmdir|rd|format|fdisk)\b", re.IGNORECASE),
            re.compile(r"\b(chmod|chown|chgrp|passwd)\b", re.IGNORECASE),
        ]

    def validate(
        self, data: str, context: builtins.dict[str, Any] = None
    ) -> builtins.list[SecurityThreat]:
        """Check for command injection patterns."""
        threats = []

        for pattern in self.command_patterns:
            if pattern.search(data):
                threats.append(SecurityThreat.COMMAND_INJECTION)
                break

        return threats


class CORSHandler:
    """CORS request handler."""

    def __init__(self, config: CORSConfig):
        self.config = config

    def handle_cors(self, request: GatewayRequest) -> GatewayResponse | None:
        """Handle CORS request."""
        if not self.config.enabled:
            return None

        origin = request.get_header("Origin")
        method = request.method.value

        # Handle preflight requests
        if method == "OPTIONS":
            return self._handle_preflight(request, origin)

        # Handle actual requests
        return self._handle_actual_request(request, origin)

    def _handle_preflight(self, request: GatewayRequest, origin: str) -> GatewayResponse:
        """Handle CORS preflight request."""

        response = GatewayResponse(status_code=200, body=b"")

        # Check origin
        if self._is_origin_allowed(origin):
            response.set_header("Access-Control-Allow-Origin", origin or "*")

            if self.config.allow_credentials:
                response.set_header("Access-Control-Allow-Credentials", "true")

        # Set allowed methods
        requested_method = request.get_header("Access-Control-Request-Method")
        if requested_method and requested_method in self.config.allow_methods:
            response.set_header(
                "Access-Control-Allow-Methods", ", ".join(self.config.allow_methods)
            )

        # Set allowed headers
        requested_headers = request.get_header("Access-Control-Request-Headers")
        if requested_headers:
            allowed_headers = self._filter_allowed_headers(requested_headers)
            if allowed_headers:
                response.set_header("Access-Control-Allow-Headers", allowed_headers)

        # Set max age
        response.set_header("Access-Control-Max-Age", str(self.config.max_age))

        # Vary header
        if self.config.vary_origin and origin:
            response.set_header("Vary", "Origin")

        return response

    def _handle_actual_request(self, request: GatewayRequest, origin: str) -> None:
        """Handle actual CORS request by adding headers to context."""
        if not self._is_origin_allowed(origin):
            return

        cors_headers = {}

        # Set origin
        cors_headers["Access-Control-Allow-Origin"] = origin or "*"

        # Set credentials
        if self.config.allow_credentials:
            cors_headers["Access-Control-Allow-Credentials"] = "true"

        # Set exposed headers
        if self.config.expose_headers:
            cors_headers["Access-Control-Expose-Headers"] = ", ".join(self.config.expose_headers)

        # Vary header
        if self.config.vary_origin and origin:
            cors_headers["Vary"] = "Origin"

        # Store headers in request context
        request.context.setdefault("cors_headers", {}).update(cors_headers)

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed."""
        if not origin:
            return True  # Allow requests without origin (same-origin)

        if "*" in self.config.allow_origins:
            return True

        return origin in self.config.allow_origins

    def _filter_allowed_headers(self, requested_headers: str) -> str:
        """Filter requested headers against allowed headers."""
        requested = [h.strip().lower() for h in requested_headers.split(",")]
        allowed = [h.lower() for h in self.config.allow_headers]

        filtered = [h for h in requested if h in allowed]
        return ", ".join(filtered)


class SecurityHeadersHandler:
    """Security headers handler."""

    def __init__(self, config: SecurityHeadersConfig):
        self.config = config

    def add_security_headers(self, response: GatewayResponse):
        """Add security headers to response."""
        # Content Security Policy
        if self.config.csp_enabled:
            header_name = (
                "Content-Security-Policy-Report-Only"
                if self.config.csp_report_only
                else "Content-Security-Policy"
            )
            response.set_header(header_name, self.config.csp_policy)

        # HSTS
        if self.config.hsts_enabled:
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            response.set_header("Strict-Transport-Security", hsts_value)

        # X-Frame-Options
        if self.config.x_frame_options:
            response.set_header("X-Frame-Options", self.config.x_frame_options)

        # X-Content-Type-Options
        if self.config.x_content_type_options:
            response.set_header("X-Content-Type-Options", "nosniff")

        # X-XSS-Protection
        if self.config.x_xss_protection:
            response.set_header("X-XSS-Protection", self.config.x_xss_protection)

        # Referrer-Policy
        if self.config.referrer_policy:
            response.set_header("Referrer-Policy", self.config.referrer_policy)

        # Permissions-Policy
        if self.config.permissions_policy:
            response.set_header("Permissions-Policy", self.config.permissions_policy)

        # Custom headers
        for name, value in self.config.custom_headers.items():
            response.set_header(name, value)


class InputValidator:
    """Input validation handler."""

    def __init__(self, config: ValidationConfig):
        self.config = config
        self.validators = [
            XSSValidator(),
            SQLInjectionValidator(),
            PathTraversalValidator(),
            CommandInjectionValidator(),
        ]

    def validate_request(self, request: GatewayRequest) -> builtins.list[SecurityEvent]:
        """Validate entire request."""
        events = []

        if not self.config.enabled:
            return events

        # Validate headers
        if self.config.validate_headers:
            events.extend(self._validate_headers(request))

        # Validate query parameters
        if self.config.validate_query_params:
            events.extend(self._validate_query_params(request))

        # Validate path
        if self.config.validate_path:
            events.extend(self._validate_path(request))

        # Validate body
        if self.config.validate_body and request.body:
            events.extend(self._validate_body(request))

        return events

    def _validate_headers(self, request: GatewayRequest) -> builtins.list[SecurityEvent]:
        """Validate request headers."""
        events = []

        for name, value in request.headers.items():
            # Check header size
            if len(f"{name}: {value}") > self.config.max_header_size:
                events.append(
                    self._create_event(
                        SecurityThreat.HEADER_INJECTION,
                        "HIGH",
                        request,
                        {"header": name, "reason": "Header size exceeded"},
                    )
                )
                continue

            # Validate header value
            threats = self._validate_string(value)
            for threat in threats:
                events.append(
                    self._create_event(
                        threat,
                        "MEDIUM",
                        request,
                        {"header": name, "value": value[:100]},
                    )
                )

        return events

    def _validate_query_params(self, request: GatewayRequest) -> builtins.list[SecurityEvent]:
        """Validate query parameters."""
        events = []

        for name, value in request.query_params.items():
            # Check parameter size
            if len(f"{name}={value}") > self.config.max_query_param_size:
                events.append(
                    self._create_event(
                        SecurityThreat.HEADER_INJECTION,
                        "MEDIUM",
                        request,
                        {"parameter": name, "reason": "Parameter size exceeded"},
                    )
                )
                continue

            # Validate parameter value
            threats = self._validate_string(value)
            for threat in threats:
                events.append(
                    self._create_event(
                        threat,
                        "MEDIUM",
                        request,
                        {"parameter": name, "value": value[:100]},
                    )
                )

        return events

    def _validate_path(self, request: GatewayRequest) -> builtins.list[SecurityEvent]:
        """Validate request path."""
        events = []

        path = request.path

        # Check path length
        if len(path) > self.config.max_path_length:
            events.append(
                self._create_event(
                    SecurityThreat.PATH_TRAVERSAL,
                    "MEDIUM",
                    request,
                    {"reason": "Path length exceeded"},
                )
            )

        # Validate path content
        threats = self._validate_string(path)
        for threat in threats:
            events.append(self._create_event(threat, "HIGH", request, {"path": path}))

        return events

    def _validate_body(self, request: GatewayRequest) -> builtins.list[SecurityEvent]:
        """Validate request body."""
        events = []

        if not request.body:
            return events

        # Check body size
        body_str = (
            request.body
            if isinstance(request.body, str)
            else request.body.decode("utf-8", errors="ignore")
        )

        if len(body_str) > self.config.max_body_size:
            events.append(
                self._create_event(
                    SecurityThreat.DESERIALIZATION,
                    "HIGH",
                    request,
                    {"reason": "Body size exceeded"},
                )
            )
            return events

        # Check content type
        content_type = request.get_header("Content-Type", "").split(";")[0].strip().lower()
        if content_type and content_type not in self.config.allowed_content_types:
            events.append(
                self._create_event(
                    SecurityThreat.DESERIALIZATION,
                    "MEDIUM",
                    request,
                    {
                        "content_type": content_type,
                        "reason": "Unsupported content type",
                    },
                )
            )

        # Validate body content
        threats = self._validate_string(body_str)
        for threat in threats:
            events.append(
                self._create_event(threat, "HIGH", request, {"body_sample": body_str[:200]})
            )

        return events

    def _validate_string(self, data: str) -> builtins.list[SecurityThreat]:
        """Validate string data using all validators."""
        threats = []

        # Check for null bytes
        if self.config.block_null_bytes and "\x00" in data:
            threats.append(SecurityThreat.COMMAND_INJECTION)

        # Check for control characters
        if self.config.block_control_chars:
            for char in data:
                if ord(char) < 32 and char not in ["\t", "\n", "\r"]:
                    threats.append(SecurityThreat.HEADER_INJECTION)
                    break

        # Run through validators
        for validator in self.validators:
            validator_threats = validator.validate(data)
            threats.extend(validator_threats)

        # Remove duplicates
        return list(set(threats))

    def _create_event(
        self,
        threat: SecurityThreat,
        severity: str,
        request: GatewayRequest,
        details: builtins.dict[str, Any],
    ) -> SecurityEvent:
        """Create security event."""
        return SecurityEvent(
            timestamp=time.time(),
            threat_type=threat,
            severity=severity,
            source_ip=request.get_header("X-Forwarded-For", "").split(",")[0].strip()
            or request.get_header("X-Real-IP", "unknown"),
            user_agent=request.get_header("User-Agent", "unknown"),
            request_path=request.path,
            details=details,
        )


class SecurityMiddleware:
    """Security middleware for API Gateway."""

    def __init__(
        self,
        cors_config: CORSConfig = None,
        headers_config: SecurityHeadersConfig = None,
        validation_config: ValidationConfig = None,
        attack_prevention_config: AttackPreventionConfig = None,
    ):
        self.cors_config = cors_config or CORSConfig()
        self.headers_config = headers_config or SecurityHeadersConfig()
        self.validation_config = validation_config or ValidationConfig()
        self.attack_prevention_config = attack_prevention_config or AttackPreventionConfig()

        self.cors_handler = CORSHandler(self.cors_config)
        self.headers_handler = SecurityHeadersHandler(self.headers_config)
        self.input_validator = InputValidator(self.validation_config)

        # Attack tracking
        self.attack_counts: builtins.dict[str, builtins.list[float]] = {}

    def process_request(self, request: GatewayRequest) -> GatewayResponse | None:
        """Process request for security."""
        try:
            # Handle CORS
            cors_response = self.cors_handler.handle_cors(request)
            if cors_response:
                self.headers_handler.add_security_headers(cors_response)
                return cors_response

            # Validate input
            security_events = self.input_validator.validate_request(request)

            # Check for attacks
            if security_events:
                blocked_events = self._handle_security_events(security_events, request)
                if blocked_events:
                    return self._create_security_response(blocked_events[0])

            # Store CORS headers for response
            self.cors_handler._handle_actual_request(request, request.get_header("Origin"))

            return None  # Continue processing

        except Exception as e:
            logger.error(f"Error in security middleware: {e}")
            return None

    def process_response(
        self, response: GatewayResponse, request: GatewayRequest
    ) -> GatewayResponse:
        """Process response for security."""
        try:
            # Add security headers
            self.headers_handler.add_security_headers(response)

            # Add CORS headers
            cors_headers = request.context.get("cors_headers", {})
            for name, value in cors_headers.items():
                response.set_header(name, value)

        except Exception as e:
            logger.error(f"Error processing security response: {e}")

        return response

    def _handle_security_events(
        self, events: builtins.list[SecurityEvent], request: GatewayRequest
    ) -> builtins.list[SecurityEvent]:
        """Handle security events and determine if request should be blocked."""
        blocked_events = []
        source_ip = events[0].source_ip if events else "unknown"

        for event in events:
            # Log event
            if self.attack_prevention_config.log_attacks:
                logger.log(
                    getattr(logging, self.attack_prevention_config.log_level),
                    f"Security threat detected: {event.threat_type.value} from {event.source_ip} - {event.details}",
                )

            # Check if should block
            if self._should_block_attack(event, source_ip):
                event.blocked = True
                blocked_events.append(event)

        return blocked_events

    def _should_block_attack(self, event: SecurityEvent, source_ip: str) -> bool:
        """Determine if attack should be blocked."""
        if not self.attack_prevention_config.enabled:
            return False

        # Always block high and critical severity attacks
        if event.severity in ["HIGH", "CRITICAL"]:
            return True

        # Rate limit attacks
        if self.attack_prevention_config.attack_rate_limit:
            current_time = time.time()
            window_start = current_time - self.attack_prevention_config.attack_window_size

            # Clean old entries
            if source_ip in self.attack_counts:
                self.attack_counts[source_ip] = [
                    t for t in self.attack_counts[source_ip] if t > window_start
                ]
            else:
                self.attack_counts[source_ip] = []

            # Add current attack
            self.attack_counts[source_ip].append(current_time)

            # Check rate limit
            if (
                len(self.attack_counts[source_ip])
                >= self.attack_prevention_config.max_attacks_per_window
            ):
                return True

        return False

    def _create_security_response(self, event: SecurityEvent) -> GatewayResponse:
        """Create security block response."""

        response = GatewayResponse(status_code=403, body=b"Forbidden: Security policy violation")

        self.headers_handler.add_security_headers(response)

        return response


# Convenience functions
def create_basic_security() -> SecurityMiddleware:
    """Create basic security middleware."""
    return SecurityMiddleware()


def create_strict_security() -> SecurityMiddleware:
    """Create strict security middleware."""
    cors_config = CORSConfig(allow_origins=["https://example.com"], allow_credentials=False)

    headers_config = SecurityHeadersConfig(
        csp_policy="default-src 'self'; script-src 'self'; style-src 'self'",
        x_frame_options="DENY",
    )

    validation_config = ValidationConfig(
        max_body_size=1024 * 1024,
        allowed_content_types={"application/json"},  # 1MB
    )

    attack_prevention_config = AttackPreventionConfig(max_attacks_per_window=5)

    return SecurityMiddleware(
        cors_config, headers_config, validation_config, attack_prevention_config
    )


def create_permissive_cors() -> SecurityMiddleware:
    """Create security middleware with permissive CORS."""
    cors_config = CORSConfig(allow_origins=["*"], allow_credentials=True, allow_headers=["*"])

    return SecurityMiddleware(cors_config=cors_config)
