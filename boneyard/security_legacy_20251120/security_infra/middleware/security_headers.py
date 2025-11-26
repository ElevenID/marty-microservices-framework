"""
Security Headers Middleware for Microservices Framework

Implements comprehensive security headers to protect against common web vulnerabilities:
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer Policy
- Permissions Policy
- Cross-Origin policies
"""

import builtins
import logging
import secrets
import string
from dataclasses import dataclass, field

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class SecurityHeadersConfig:
    """Configuration for security headers"""

    # Content Security Policy
    csp_default_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_script_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_style_src: builtins.list[str] = field(default_factory=lambda: ["'self'", "'unsafe-inline'"])
    csp_img_src: builtins.list[str] = field(default_factory=lambda: ["'self'", "data:", "https:"])
    csp_font_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_connect_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_object_src: builtins.list[str] = field(default_factory=lambda: ["'none'"])
    csp_media_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_frame_src: builtins.list[str] = field(default_factory=lambda: ["'none'"])
    csp_child_src: builtins.list[str] = field(default_factory=lambda: ["'none'"])
    csp_worker_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_manifest_src: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_base_uri: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_form_action: builtins.list[str] = field(default_factory=lambda: ["'self'"])
    csp_frame_ancestors: builtins.list[str] = field(default_factory=lambda: ["'none'"])
    csp_upgrade_insecure_requests: bool = True
    csp_block_all_mixed_content: bool = True
    csp_report_uri: str | None = None
    csp_report_to: str | None = None

    # HTTP Strict Transport Security
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # X-Frame-Options
    x_frame_options: str = "DENY"  # DENY, SAMEORIGIN, or ALLOW-FROM uri

    # X-Content-Type-Options
    x_content_type_options: str = "nosniff"

    # X-XSS-Protection (deprecated but still used by some browsers)
    x_xss_protection: str = "1; mode=block"

    # Referrer Policy
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Permissions Policy (Feature Policy replacement)
    permissions_policy: builtins.dict[str, builtins.list[str] | str] = field(
        default_factory=lambda: {
            "camera": "('none')",
            "microphone": "('none')",
            "geolocation": "('none')",
            "interest-cohort": "()",  # Disable FLoC
            "payment": "('none')",
            "usb": "('none')",
            "bluetooth": "('none')",
            "accelerometer": "('none')",
            "gyroscope": "('none')",
            "magnetometer": "('none')",
        }
    )

    # Cross-Origin policies
    cross_origin_embedder_policy: str = "require-corp"
    cross_origin_opener_policy: str = "same-origin"
    cross_origin_resource_policy: str = "same-origin"

    # CORS settings
    cors_allow_credentials: bool = False
    cors_allow_origins: builtins.list[str] = field(default_factory=list)
    cors_allow_methods: builtins.list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"]
    )
    cors_allow_headers: builtins.list[str] = field(default_factory=lambda: ["*"])
    cors_expose_headers: builtins.list[str] = field(default_factory=list)
    cors_max_age: int = 600

    # Additional security headers
    x_permitted_cross_domain_policies: str = "none"
    expect_ct: str | None = None  # Certificate Transparency

    # Environment-specific settings
    enforce_https: bool = True
    development_mode: bool = False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers"""

    def __init__(
        self,
        app,
        config: SecurityHeadersConfig,
        excluded_paths: builtins.list[str] | None = None,
    ):
        super().__init__(app)
        self.config = config
        self.excluded_paths = excluded_paths or []

        # Precompile headers for better performance
        self.static_headers = self._compile_static_headers()

    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        response = await call_next(request)

        # Skip security headers for excluded paths (e.g., webhooks from external services)
        if request.url.path in self.excluded_paths:
            return response

        # Add all security headers
        self._add_security_headers(request, response)

        return response

    def _add_security_headers(self, request: Request, response: Response):
        """Add all security headers to the response"""

        # Add static headers
        for header, value in self.static_headers.items():
            response.headers[header] = value

        # Add Content Security Policy
        csp_header = self._build_csp_header(request)
        if csp_header:
            response.headers["Content-Security-Policy"] = csp_header

        # Add CORS headers if configured
        if self.config.cors_allow_origins:
            self._add_cors_headers(request, response)

        # Add conditional headers
        self._add_conditional_headers(request, response)

    def _compile_static_headers(self) -> builtins.dict[str, str]:
        """Compile static security headers that don't change per request"""
        headers = {}

        # X-Content-Type-Options
        if self.config.x_content_type_options:
            headers["X-Content-Type-Options"] = self.config.x_content_type_options

        # X-Frame-Options
        if self.config.x_frame_options:
            headers["X-Frame-Options"] = self.config.x_frame_options

        # X-XSS-Protection
        if self.config.x_xss_protection:
            headers["X-XSS-Protection"] = self.config.x_xss_protection

        # Referrer-Policy
        if self.config.referrer_policy:
            headers["Referrer-Policy"] = self.config.referrer_policy

        # Permissions-Policy
        if self.config.permissions_policy:
            permissions_header = self._build_permissions_policy()
            if permissions_header:
                headers["Permissions-Policy"] = permissions_header

        # Cross-Origin policies
        if self.config.cross_origin_embedder_policy:
            headers["Cross-Origin-Embedder-Policy"] = self.config.cross_origin_embedder_policy

        if self.config.cross_origin_opener_policy:
            headers["Cross-Origin-Opener-Policy"] = self.config.cross_origin_opener_policy

        if self.config.cross_origin_resource_policy:
            headers["Cross-Origin-Resource-Policy"] = self.config.cross_origin_resource_policy

        # X-Permitted-Cross-Domain-Policies
        if self.config.x_permitted_cross_domain_policies:
            headers["X-Permitted-Cross-Domain-Policies"] = (
                self.config.x_permitted_cross_domain_policies
            )

        # Expect-CT
        if self.config.expect_ct:
            headers["Expect-CT"] = self.config.expect_ct

        return headers

    def _build_csp_header(self, request: Request) -> str:
        """Build Content Security Policy header"""
        directives = []

        # Default source
        if self.config.csp_default_src:
            directives.append(f"default-src {' '.join(self.config.csp_default_src)}")

        # Script source
        if self.config.csp_script_src:
            directives.append(f"script-src {' '.join(self.config.csp_script_src)}")

        # Style source
        if self.config.csp_style_src:
            directives.append(f"style-src {' '.join(self.config.csp_style_src)}")

        # Image source
        if self.config.csp_img_src:
            directives.append(f"img-src {' '.join(self.config.csp_img_src)}")

        # Font source
        if self.config.csp_font_src:
            directives.append(f"font-src {' '.join(self.config.csp_font_src)}")

        # Connect source
        if self.config.csp_connect_src:
            directives.append(f"connect-src {' '.join(self.config.csp_connect_src)}")

        # Object source
        if self.config.csp_object_src:
            directives.append(f"object-src {' '.join(self.config.csp_object_src)}")

        # Media source
        if self.config.csp_media_src:
            directives.append(f"media-src {' '.join(self.config.csp_media_src)}")

        # Frame source
        if self.config.csp_frame_src:
            directives.append(f"frame-src {' '.join(self.config.csp_frame_src)}")

        # Child source
        if self.config.csp_child_src:
            directives.append(f"child-src {' '.join(self.config.csp_child_src)}")

        # Worker source
        if self.config.csp_worker_src:
            directives.append(f"worker-src {' '.join(self.config.csp_worker_src)}")

        # Manifest source
        if self.config.csp_manifest_src:
            directives.append(f"manifest-src {' '.join(self.config.csp_manifest_src)}")

        # Base URI
        if self.config.csp_base_uri:
            directives.append(f"base-uri {' '.join(self.config.csp_base_uri)}")

        # Form action
        if self.config.csp_form_action:
            directives.append(f"form-action {' '.join(self.config.csp_form_action)}")

        # Frame ancestors
        if self.config.csp_frame_ancestors:
            directives.append(f"frame-ancestors {' '.join(self.config.csp_frame_ancestors)}")

        # Upgrade insecure requests
        if self.config.csp_upgrade_insecure_requests:
            directives.append("upgrade-insecure-requests")

        # Block all mixed content
        if self.config.csp_block_all_mixed_content:
            directives.append("block-all-mixed-content")

        # Report URI
        if self.config.csp_report_uri:
            directives.append(f"report-uri {self.config.csp_report_uri}")

        # Report to
        if self.config.csp_report_to:
            directives.append(f"report-to {self.config.csp_report_to}")

        return "; ".join(directives)

    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy header"""
        policies = []

        for feature, allowlist in self.config.permissions_policy.items():
            if isinstance(allowlist, list):
                allowlist_str = " ".join(f'"{origin}"' for origin in allowlist)
                policies.append(f"{feature}=({allowlist_str})")
            else:
                policies.append(f"{feature}={allowlist}")

        return ", ".join(policies)

    def _add_cors_headers(self, request: Request, response: Response):
        """Add CORS headers if configured"""
        origin = request.headers.get("origin")

        # Check if origin is allowed
        if origin and (
            "*" in self.config.cors_allow_origins or origin in self.config.cors_allow_origins
        ):
            response.headers["Access-Control-Allow-Origin"] = origin
        elif "*" in self.config.cors_allow_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"

        # Add other CORS headers
        if self.config.cors_allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        if self.config.cors_allow_methods:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(
                self.config.cors_allow_methods
            )

        if self.config.cors_allow_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(
                self.config.cors_allow_headers
            )

        if self.config.cors_expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(
                self.config.cors_expose_headers
            )

        if self.config.cors_max_age:
            response.headers["Access-Control-Max-Age"] = str(self.config.cors_max_age)

    def _add_conditional_headers(self, request: Request, response: Response):
        """Add conditional headers based on request/environment"""

        # HSTS (only for HTTPS)
        if self.config.hsts_enabled and (
            request.url.scheme == "https" or not self.config.enforce_https
        ):
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Development mode adjustments
        if self.config.development_mode:
            # Relax some policies in development
            if "Content-Security-Policy" in response.headers:
                csp = response.headers["Content-Security-Policy"]
                # Allow unsafe-eval for development tools
                if "'unsafe-eval'" not in csp:
                    response.headers["Content-Security-Policy"] = csp.replace(
                        "script-src", "script-src 'unsafe-eval'"
                    )


def create_security_headers_config(
    environment: str = "production",
    api_only: bool = False,
    allow_origins: builtins.list[str] | None = None,
) -> SecurityHeadersConfig:
    """Factory function to create security headers configuration"""

    config = SecurityHeadersConfig()

    # Environment-specific adjustments
    if environment == "development":
        config.development_mode = True
        config.enforce_https = False
        config.hsts_enabled = False
        # Allow localhost and development tools
        config.csp_script_src.extend(["'unsafe-eval'", "'unsafe-inline'"])
        config.csp_connect_src.extend(["ws://localhost:*", "http://localhost:*"])

    elif environment == "testing":
        config.enforce_https = False
        config.hsts_enabled = False
        # Relax some policies for testing
        config.x_frame_options = "SAMEORIGIN"

    # API-only adjustments
    if api_only:
        # Stricter CSP for API-only services
        config.csp_default_src = ["'none'"]
        config.csp_script_src = ["'none'"]
        config.csp_style_src = ["'none'"]
        config.csp_img_src = ["'none'"]
        config.csp_font_src = ["'none'"]
        config.csp_connect_src = ["'self'"]
        config.csp_object_src = ["'none'"]
        config.csp_media_src = ["'none'"]
        config.csp_frame_src = ["'none'"]
        config.csp_child_src = ["'none'"]
        config.csp_worker_src = ["'none'"]
        config.csp_manifest_src = ["'none'"]

        # API doesn't need frame protection
        config.x_frame_options = "DENY"

    # CORS configuration
    if allow_origins:
        config.cors_allow_origins = allow_origins
        # Enable credentials for specific origins
        if "*" not in allow_origins:
            config.cors_allow_credentials = True

    return config


def create_security_headers_middleware(
    environment: str = "production",
    api_only: bool = False,
    allow_origins: builtins.list[str] | None = None,
    excluded_paths: builtins.list[str] | None = None,
) -> SecurityHeadersMiddleware:
    """Factory function to create security headers middleware"""

    config = create_security_headers_config(
        environment=environment, api_only=api_only, allow_origins=allow_origins
    )

    return SecurityHeadersMiddleware(config, excluded_paths=excluded_paths)


# Utility functions for CSP nonce generation


def generate_csp_nonce() -> str:
    """Generate a cryptographically secure nonce for CSP"""
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


# FastAPI dependency for CSP nonce
async def get_csp_nonce(request: Request) -> str:
    """FastAPI dependency to get or generate CSP nonce"""
    if not hasattr(request.state, "csp_nonce"):
        request.state.csp_nonce = generate_csp_nonce()
    return request.state.csp_nonce
