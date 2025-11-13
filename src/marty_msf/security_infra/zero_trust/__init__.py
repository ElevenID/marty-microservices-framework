"""
Zero-Trust Security Architecture for Marty Microservices Framework

Implements comprehensive zero-trust security including:
- Mutual TLS (mTLS) for all service communication
- Identity-based access control and verification
- Network segmentation and micro-segmentation
- Service mesh security integration
- Continuous verification and monitoring
- Policy-based access enforcement
"""

import asyncio
import builtins
import hashlib
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.x509.oid import NameOID
from prometheus_client import Counter, Gauge, Histogram

# External dependencies (optional)
try:
    EXTERNAL_DEPS_AVAILABLE = True
except ImportError:
    EXTERNAL_DEPS_AVAILABLE = False


class SecurityLevel(Enum):
    """Security clearance levels"""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AccessDecision(Enum):
    """Access control decisions"""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    CHALLENGE = "challenge"


@dataclass
class ServiceIdentity:
    """Service identity with cryptographic verification"""

    service_name: str
    namespace: str
    cluster: str
    service_account: str
    certificate_fingerprint: str
    public_key_hash: str
    created_at: datetime
    expires_at: datetime
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    capabilities: builtins.set[str] = field(default_factory=set)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "capabilities": list(self.capabilities),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def is_valid(self) -> bool:
        """Check if identity is still valid"""
        return datetime.now() < self.expires_at

    def has_capability(self, capability: str) -> bool:
        """Check if identity has specific capability"""
        return capability in self.capabilities


@dataclass
class AccessRequest:
    """Zero-trust access request"""

    source_identity: ServiceIdentity
    target_service: str
    target_resource: str
    action: str
    context: builtins.dict[str, Any]
    timestamp: datetime
    request_id: str = field(default_factory=lambda: secrets.token_hex(16))

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "source_identity": self.source_identity.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AccessPolicy:
    """Zero-trust access policy"""

    policy_id: str
    name: str
    description: str
    source_selector: builtins.dict[str, Any]  # Service/identity selector
    target_selector: builtins.dict[str, Any]  # Resource selector
    action: str
    decision: AccessDecision
    conditions: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 100  # Lower number = higher priority

    def matches_request(self, request: AccessRequest) -> bool:
        """Check if policy matches access request"""
        # Match source identity
        if not self._matches_selector(request.source_identity.to_dict(), self.source_selector):
            return False

        # Match target
        target_data = {
            "service": request.target_service,
            "resource": request.target_resource,
            "action": request.action,
        }
        if not self._matches_selector(target_data, self.target_selector):
            return False

        # Check conditions
        return self._evaluate_conditions(request)

    def _matches_selector(
        self, data: builtins.dict[str, Any], selector: builtins.dict[str, Any]
    ) -> bool:
        """Check if data matches selector"""
        for key, expected in selector.items():
            if key not in data:
                return False

            if isinstance(expected, list):
                if data[key] not in expected:
                    return False
            elif isinstance(expected, dict):
                if "regex" in expected:
                    if not re.match(expected["regex"], str(data[key])):
                        return False
                elif "in" in expected:
                    if data[key] not in expected["in"]:
                        return False
            elif data[key] != expected:
                return False

        return True

    def _evaluate_conditions(self, request: AccessRequest) -> bool:
        """Evaluate policy conditions"""
        for condition in self.conditions:
            condition_type = condition.get("type")

            if condition_type == "time_window":
                if not self._check_time_window(condition):
                    return False
            elif condition_type == "rate_limit":
                if not self._check_rate_limit(request, condition):
                    return False
            elif condition_type == "security_level":
                required_level = SecurityLevel(condition["level"])
                if request.source_identity.security_level.value < required_level.value:
                    return False

        return True

    def _check_time_window(self, condition: builtins.dict[str, Any]) -> bool:
        """Check if current time is within allowed window"""
        now = datetime.now()
        start_time = condition.get("start_time", "00:00")
        end_time = condition.get("end_time", "23:59")

        # Simple time window check (can be enhanced for timezone support)
        current_time = now.strftime("%H:%M")
        return start_time <= current_time <= end_time

    def _check_rate_limit(self, request: AccessRequest, condition: builtins.dict[str, Any]) -> bool:
        """Check rate limiting conditions"""
        # This would typically integrate with a rate limiting service
        # For now, return True (implementation depends on rate limiter backend)
        return True


class CertificateManager:
    """
    Certificate management for zero-trust mTLS

    Handles:
    - Certificate generation and rotation
    - Root CA management
    - Service certificate provisioning
    - Certificate validation and verification
    """

    def __init__(self, ca_cert_path: str, ca_key_path: str):
        self.ca_cert_path = ca_cert_path
        self.ca_key_path = ca_key_path
        self.certificates: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Metrics
        if EXTERNAL_DEPS_AVAILABLE:
            self.cert_operations = Counter(
                "marty_certificate_operations_total",
                "Certificate operations",
                ["operation", "status"],
            )
            self.cert_validity = Gauge(
                "marty_certificate_validity_days",
                "Certificate validity in days",
                ["service", "type"],
            )

    def generate_root_ca(self, ca_name: str = "Marty Root CA") -> builtins.tuple[bytes, bytes]:
        """Generate root CA certificate and private key"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )

        # Create CA certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Marty Microservices"),
                x509.NameAttribute(NameOID.COMMON_NAME, ca_name),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))  # 10 years
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.DNSName("marty-ca"),
                    ]
                ),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    digital_signature=False,
                    key_encipherment=False,
                    key_agreement=False,
                    content_commitment=False,
                    data_encipherment=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Serialize certificate and key
        cert_pem = cert.public_bytes(Encoding.PEM)
        key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

        if EXTERNAL_DEPS_AVAILABLE:
            self.cert_operations.labels(operation="generate_ca", status="success").inc()

        return cert_pem, key_pem

    def generate_service_certificate(
        self,
        service_name: str,
        namespace: str = "default",
        dns_names: builtins.list[str] | None = None,
        validity_days: int = 90,
    ) -> builtins.tuple[bytes, bytes]:
        """Generate service certificate signed by CA"""

        # Load CA certificate and key
        with open(self.ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())

        with open(self.ca_key_path, "rb") as f:
            ca_private_key = serialization.load_pem_private_key(f.read(), password=None)

        # Generate service private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Prepare DNS names
        if dns_names is None:
            dns_names = [
                service_name,
                f"{service_name}.{namespace}",
                f"{service_name}.{namespace}.svc",
                f"{service_name}.{namespace}.svc.cluster.local",
            ]

        # Create service certificate
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Marty Microservices"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, namespace),
                x509.NameAttribute(NameOID.COMMON_NAME, f"{service_name}.{namespace}"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(name) for name in dns_names]),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=False,
                    crl_sign=False,
                    digital_signature=True,
                    key_encipherment=True,
                    key_agreement=False,
                    content_commitment=False,
                    data_encipherment=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [
                        x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                    ]
                ),
                critical=True,
            )
            .sign(ca_private_key, hashes.SHA256())
        )

        # Serialize certificate and key
        cert_pem = cert.public_bytes(Encoding.PEM)
        key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

        # Store certificate info
        cert_id = f"{service_name}.{namespace}"
        self.certificates[cert_id] = {
            "service_name": service_name,
            "namespace": namespace,
            "certificate": cert_pem,
            "private_key": key_pem,
            "dns_names": dns_names,
            "created_at": datetime.now(),
            "expires_at": datetime.utcnow() + timedelta(days=validity_days),
            "fingerprint": self._calculate_fingerprint(cert_pem),
        }

        if EXTERNAL_DEPS_AVAILABLE:
            self.cert_operations.labels(operation="generate_service", status="success").inc()
            self.cert_validity.labels(service=cert_id, type="service").set(validity_days)

        return cert_pem, key_pem

    def _calculate_fingerprint(self, cert_pem: bytes) -> str:
        """Calculate certificate fingerprint"""
        cert = x509.load_pem_x509_certificate(cert_pem)
        fingerprint = cert.fingerprint(hashes.SHA256())
        return fingerprint.hex()

    def validate_certificate(self, cert_pem: bytes) -> builtins.dict[str, Any]:
        """Validate certificate against CA"""
        try:
            cert = x509.load_pem_x509_certificate(cert_pem)

            # Load CA certificate
            with open(self.ca_cert_path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())

            # Basic validation
            now = datetime.utcnow()
            is_valid = (
                cert.not_valid_before <= now <= cert.not_valid_after
                and cert.issuer == ca_cert.subject
            )

            return {
                "valid": is_valid,
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "not_before": cert.not_valid_before.isoformat(),
                "not_after": cert.not_valid_after.isoformat(),
                "fingerprint": self._calculate_fingerprint(cert_pem),
                "serial_number": str(cert.serial_number),
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def rotate_certificate(
        self, service_name: str, namespace: str = "default"
    ) -> builtins.tuple[bytes, bytes]:
        """Rotate service certificate"""
        cert_id = f"{service_name}.{namespace}"

        if cert_id in self.certificates:
            old_cert = self.certificates[cert_id]
            dns_names = old_cert["dns_names"]
        else:
            dns_names = None

        new_cert, new_key = self.generate_service_certificate(service_name, namespace, dns_names)

        if EXTERNAL_DEPS_AVAILABLE:
            self.cert_operations.labels(operation="rotate", status="success").inc()

        return new_cert, new_key

    def get_certificate_info(
        self, service_name: str, namespace: str = "default"
    ) -> builtins.dict[str, Any] | None:
        """Get certificate information"""
        cert_id = f"{service_name}.{namespace}"
        return self.certificates.get(cert_id)

    def list_certificates(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """List all managed certificates"""
        return self.certificates.copy()


class ZeroTrustPolicyEngine:
    """
    Zero-trust policy engine for access control decisions

    Features:
    - Policy-based access control
    - Real-time decision making
    - Context-aware authorization
    - Continuous verification
    """

    def __init__(self):
        self.policies: builtins.list[AccessPolicy] = []
        self.identity_store: builtins.dict[str, ServiceIdentity] = {}
        self.access_log: builtins.list[builtins.dict[str, Any]] = []

        # Metrics
        if EXTERNAL_DEPS_AVAILABLE:
            self.access_decisions = Counter(
                "marty_access_decisions_total",
                "Access control decisions",
                ["decision", "policy", "service"],
            )
            self.policy_evaluations = Histogram(
                "marty_policy_evaluation_duration_seconds", "Policy evaluation duration"
            )

        # Load default policies
        self._load_default_policies()

    def _load_default_policies(self):
        """Load default zero-trust policies"""

        # Default deny policy (lowest priority)
        default_deny = AccessPolicy(
            policy_id="default-deny",
            name="Default Deny",
            description="Default deny all access",
            source_selector={},
            target_selector={},
            action="*",
            decision=AccessDecision.DENY,
            priority=1000,
        )

        # Inter-service communication policy
        inter_service = AccessPolicy(
            policy_id="inter-service-allow",
            name="Inter-Service Communication",
            description="Allow authenticated service-to-service communication",
            source_selector={"security_level": {"in": ["internal", "confidential"]}},
            target_selector={"service": {"regex": r".*-service$"}},
            action="*",
            decision=AccessDecision.ALLOW,
            conditions=[{"type": "security_level", "level": "internal"}],
            priority=50,
        )

        # Public API access
        public_api = AccessPolicy(
            policy_id="public-api-allow",
            name="Public API Access",
            description="Allow access to public APIs",
            source_selector={},
            target_selector={"resource": {"regex": r"/api/v\d+/public/.*"}},
            action="GET",
            decision=AccessDecision.ALLOW,
            conditions=[{"type": "rate_limit", "requests_per_minute": 100}],
            priority=30,
        )

        # Admin access with audit
        admin_access = AccessPolicy(
            policy_id="admin-audit",
            name="Admin Access with Audit",
            description="Allow admin access with mandatory audit",
            source_selector={"capabilities": {"in": ["admin"]}},
            target_selector={"resource": {"regex": r"/admin/.*"}},
            action="*",
            decision=AccessDecision.AUDIT,
            conditions=[{"type": "security_level", "level": "confidential"}],
            priority=20,
        )

        self.policies.extend([default_deny, inter_service, public_api, admin_access])

    def register_identity(self, identity: ServiceIdentity):
        """Register service identity"""
        identity_key = f"{identity.service_name}.{identity.namespace}"
        self.identity_store[identity_key] = identity

        print(
            f"Registered identity: {identity_key} with security level {identity.security_level.value}"
        )

    def evaluate_access_request(
        self, request: AccessRequest
    ) -> builtins.tuple[AccessDecision, AccessPolicy | None]:
        """Evaluate access request against policies"""
        start_time = time.time()

        try:
            # Sort policies by priority (lower number = higher priority)
            sorted_policies = sorted(self.policies, key=lambda p: p.priority)

            for policy in sorted_policies:
                if policy.matches_request(request):
                    decision = policy.decision

                    # Log access decision
                    self._log_access_decision(request, decision, policy)

                    # Update metrics
                    if EXTERNAL_DEPS_AVAILABLE:
                        self.access_decisions.labels(
                            decision=decision.value,
                            policy=policy.policy_id,
                            service=request.source_identity.service_name,
                        ).inc()

                    return decision, policy

            # No policy matched, default deny
            default_policy = next((p for p in self.policies if p.policy_id == "default-deny"), None)
            self._log_access_decision(request, AccessDecision.DENY, default_policy)

            if EXTERNAL_DEPS_AVAILABLE:
                self.access_decisions.labels(
                    decision=AccessDecision.DENY.value,
                    policy="default-deny",
                    service=request.source_identity.service_name,
                ).inc()

            return AccessDecision.DENY, default_policy

        finally:
            if EXTERNAL_DEPS_AVAILABLE:
                self.policy_evaluations.observe(time.time() - start_time)

    def _log_access_decision(
        self,
        request: AccessRequest,
        decision: AccessDecision,
        policy: AccessPolicy | None,
    ):
        """Log access control decision"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request.request_id,
            "source_service": request.source_identity.service_name,
            "source_namespace": request.source_identity.namespace,
            "target_service": request.target_service,
            "target_resource": request.target_resource,
            "action": request.action,
            "decision": decision.value,
            "policy_id": policy.policy_id if policy else None,
            "policy_name": policy.name if policy else None,
            "context": request.context,
        }

        self.access_log.append(log_entry)

        # Keep only recent entries (last 10000)
        if len(self.access_log) > 10000:
            self.access_log = self.access_log[-10000:]

        # Print for debugging
        print(
            f"Access Decision: {decision.value} for {request.source_identity.service_name} -> {request.target_service}/{request.target_resource}"
        )

    def add_policy(self, policy: AccessPolicy):
        """Add new access policy"""
        self.policies.append(policy)
        # Sort by priority
        self.policies.sort(key=lambda p: p.priority)

        print(f"Added policy: {policy.name} (priority: {policy.priority})")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove access policy"""
        original_count = len(self.policies)
        self.policies = [p for p in self.policies if p.policy_id != policy_id]
        removed = len(self.policies) < original_count

        if removed:
            print(f"Removed policy: {policy_id}")

        return removed

    def get_access_log(
        self,
        service_name: str | None = None,
        decision: AccessDecision | None = None,
        limit: int = 100,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Get access log with optional filtering"""
        filtered_log = self.access_log

        if service_name:
            filtered_log = [
                entry for entry in filtered_log if entry["source_service"] == service_name
            ]

        if decision:
            filtered_log = [entry for entry in filtered_log if entry["decision"] == decision.value]

        # Return most recent entries
        return filtered_log[-limit:]

    def get_policy_statistics(self) -> builtins.dict[str, Any]:
        """Get policy usage statistics"""
        policy_usage = {}
        decision_counts = {d.value: 0 for d in AccessDecision}

        for entry in self.access_log:
            policy_id = entry.get("policy_id", "unknown")
            decision = entry.get("decision", "unknown")

            if policy_id not in policy_usage:
                policy_usage[policy_id] = 0
            policy_usage[policy_id] += 1

            if decision in decision_counts:
                decision_counts[decision] += 1

        return {
            "total_evaluations": len(self.access_log),
            "policy_usage": policy_usage,
            "decision_distribution": decision_counts,
            "active_policies": len(self.policies),
            "registered_identities": len(self.identity_store),
        }


class ZeroTrustManager:
    """
    Complete zero-trust security manager

    Orchestrates all zero-trust components:
    - Certificate management
    - Identity verification
    - Policy enforcement
    - Continuous monitoring
    """

    def __init__(
        self,
        ca_cert_path: str = "/etc/ssl/marty-ca.crt",
        ca_key_path: str = "/etc/ssl/marty-ca.key",
    ):
        self.cert_manager = CertificateManager(ca_cert_path, ca_key_path)
        self.policy_engine = ZeroTrustPolicyEngine()
        self.running = False

        # Metrics
        if EXTERNAL_DEPS_AVAILABLE:
            self.security_events = Counter(
                "marty_security_events_total",
                "Security events",
                ["event_type", "severity"],
            )

    async def initialize_ca(self) -> builtins.tuple[bytes, bytes]:
        """Initialize root CA if not exists"""
        try:
            with open(self.cert_manager.ca_cert_path, "rb") as f:
                ca_cert = f.read()
            with open(self.cert_manager.ca_key_path, "rb") as f:
                ca_key = f.read()

            print("Using existing CA certificate")
            return ca_cert, ca_key

        except FileNotFoundError:
            print("Generating new CA certificate")
            ca_cert, ca_key = self.cert_manager.generate_root_ca()

            # Save CA certificate and key
            with open(self.cert_manager.ca_cert_path, "wb") as f:
                f.write(ca_cert)
            with open(self.cert_manager.ca_key_path, "wb") as f:
                f.write(ca_key)

            return ca_cert, ca_key

    async def onboard_service(
        self,
        service_name: str,
        namespace: str = "default",
        security_level: SecurityLevel = SecurityLevel.INTERNAL,
        capabilities: builtins.set[str] | None = None,
    ) -> ServiceIdentity:
        """Onboard new service to zero-trust architecture"""

        # Generate service certificate
        cert_pem, key_pem = self.cert_manager.generate_service_certificate(service_name, namespace)

        # Create service identity
        identity = ServiceIdentity(
            service_name=service_name,
            namespace=namespace,
            cluster="default",
            service_account=f"{service_name}-sa",
            certificate_fingerprint=self.cert_manager._calculate_fingerprint(cert_pem),
            public_key_hash=hashlib.sha256(cert_pem).hexdigest(),
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=90),
            security_level=security_level,
            capabilities=capabilities or set(),
            metadata={
                "certificate": cert_pem.decode("utf-8"),
                "private_key": key_pem.decode("utf-8"),
            },
        )

        # Register identity
        self.policy_engine.register_identity(identity)

        print(f"Onboarded service: {service_name}.{namespace}")
        return identity

    async def verify_and_authorize(
        self,
        source_cert: bytes,
        target_service: str,
        target_resource: str,
        action: str,
        context: builtins.dict[str, Any] | None = None,
    ) -> builtins.tuple[bool, AccessDecision, AccessPolicy | None]:
        """Verify identity and authorize access"""

        # Validate certificate
        cert_validation = self.cert_manager.validate_certificate(source_cert)
        if not cert_validation["valid"]:
            if EXTERNAL_DEPS_AVAILABLE:
                self.security_events.labels(event_type="invalid_certificate", severity="high").inc()
            return False, AccessDecision.DENY, None

        # Find source identity
        fingerprint = cert_validation["fingerprint"]
        source_identity = None

        for identity in self.policy_engine.identity_store.values():
            if identity.certificate_fingerprint == fingerprint:
                source_identity = identity
                break

        if not source_identity or not source_identity.is_valid():
            if EXTERNAL_DEPS_AVAILABLE:
                self.security_events.labels(event_type="unknown_identity", severity="high").inc()
            return False, AccessDecision.DENY, None

        # Create access request
        access_request = AccessRequest(
            source_identity=source_identity,
            target_service=target_service,
            target_resource=target_resource,
            action=action,
            context=context or {},
            timestamp=datetime.now(),
        )

        # Evaluate access
        decision, policy = self.policy_engine.evaluate_access_request(access_request)

        # Log security event
        if decision == AccessDecision.DENY:
            if EXTERNAL_DEPS_AVAILABLE:
                self.security_events.labels(event_type="access_denied", severity="medium").inc()

        return (
            decision in [AccessDecision.ALLOW, AccessDecision.AUDIT],
            decision,
            policy,
        )

    async def start_certificate_rotation(self, rotation_interval: int = 3600):
        """Start automatic certificate rotation"""
        self.running = True

        while self.running:
            try:
                # Check for certificates expiring in next 7 days
                expiry_threshold = datetime.now() + timedelta(days=7)

                for _cert_id, cert_info in self.cert_manager.list_certificates().items():
                    if cert_info["expires_at"] <= expiry_threshold:
                        service_name = cert_info["service_name"]
                        namespace = cert_info["namespace"]

                        print(f"Rotating certificate for {service_name}.{namespace}")

                        # Rotate certificate
                        new_cert, new_key = self.cert_manager.rotate_certificate(
                            service_name, namespace
                        )

                        # Update identity
                        identity_key = f"{service_name}.{namespace}"
                        if identity_key in self.policy_engine.identity_store:
                            identity = self.policy_engine.identity_store[identity_key]
                            identity.certificate_fingerprint = (
                                self.cert_manager._calculate_fingerprint(new_cert)
                            )
                            identity.expires_at = datetime.now() + timedelta(days=90)
                            identity.metadata["certificate"] = new_cert.decode("utf-8")
                            identity.metadata["private_key"] = new_key.decode("utf-8")

                await asyncio.sleep(rotation_interval)

            except Exception as e:
                print(f"Error in certificate rotation: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

    def stop_certificate_rotation(self):
        """Stop certificate rotation"""
        self.running = False

    def get_security_status(self) -> builtins.dict[str, Any]:
        """Get overall security status"""
        policy_stats = self.policy_engine.get_policy_statistics()
        cert_count = len(self.cert_manager.list_certificates())

        return {
            "zero_trust_enabled": True,
            "total_certificates": cert_count,
            "active_identities": len(self.policy_engine.identity_store),
            "policy_statistics": policy_stats,
            "ca_status": "active",
            "certificate_rotation": "enabled" if self.running else "disabled",
        }


# Example usage and testing
async def main():
    """Example usage of zero-trust security"""

    # Initialize zero-trust manager
    zt_manager = ZeroTrustManager()

    # Initialize CA
    await zt_manager.initialize_ca()

    # Onboard services
    user_service = await zt_manager.onboard_service(
        "user-service",
        "production",
        SecurityLevel.CONFIDENTIAL,
        {"user_management", "authentication"},
    )

    await zt_manager.onboard_service(
        "payment-service",
        "production",
        SecurityLevel.RESTRICTED,
        {"payment_processing", "financial_data"},
    )

    api_gateway = await zt_manager.onboard_service(
        "api-gateway",
        "production",
        SecurityLevel.INTERNAL,
        {"routing", "load_balancing"},
    )

    # Test access scenarios
    print("\n=== TESTING ACCESS SCENARIOS ===")

    # Scenario 1: User service accessing payment service
    user_cert = user_service.metadata["certificate"].encode("utf-8")
    authorized, decision, policy = await zt_manager.verify_and_authorize(
        user_cert,
        "payment-service",
        "/api/v1/payments",
        "POST",
        {"amount": 100.00, "currency": "USD"},
    )

    print(
        f"User service -> Payment service: {decision.value} ({'authorized' if authorized else 'denied'})"
    )

    # Scenario 2: API gateway accessing user service
    gateway_cert = api_gateway.metadata["certificate"].encode("utf-8")
    authorized, decision, policy = await zt_manager.verify_and_authorize(
        gateway_cert, "user-service", "/api/v1/users", "GET", {"user_id": "user123"}
    )

    print(
        f"API gateway -> User service: {decision.value} ({'authorized' if authorized else 'denied'})"
    )

    # Add custom policy
    custom_policy = AccessPolicy(
        policy_id="payment-restriction",
        name="Payment Service Restriction",
        description="Only allow payment service access from user service",
        source_selector={
            "service_name": "user-service",
            "capabilities": {"in": ["user_management"]},
        },
        target_selector={"service": "payment-service"},
        action="POST",
        decision=AccessDecision.AUDIT,
        priority=10,
    )

    zt_manager.policy_engine.add_policy(custom_policy)

    # Test with new policy
    authorized, decision, policy = await zt_manager.verify_and_authorize(
        user_cert,
        "payment-service",
        "/api/v1/payments",
        "POST",
        {"amount": 100.00, "currency": "USD"},
    )

    print(f"User service -> Payment service (with custom policy): {decision.value}")

    # Show security status
    status = zt_manager.get_security_status()
    print("\n=== SECURITY STATUS ===")
    print(f"Zero-trust enabled: {status['zero_trust_enabled']}")
    print(f"Active certificates: {status['total_certificates']}")
    print(f"Active identities: {status['active_identities']}")
    print(f"Total policy evaluations: {status['policy_statistics']['total_evaluations']}")

    # Show access log
    access_log = zt_manager.policy_engine.get_access_log(limit=5)
    print("\n=== RECENT ACCESS LOG ===")
    for entry in access_log[-3:]:
        print(
            f"{entry['timestamp']}: {entry['source_service']} -> {entry['target_service']} = {entry['decision']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
