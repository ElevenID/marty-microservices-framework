"""
Audit logging framework for enterprise microservices.
This module provides comprehensive audit logging capabilities including:
- Structured audit event logging
- Encryption for sensitive data
- Multiple output destinations (file, database, SIEM)
- Event correlation and tracing
- Compliance and retention management
- Security event detection
"""

import base64
import builtins
import hashlib
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events for microservices."""

    # Authentication and Authorization
    AUTH_LOGIN_SUCCESS = "auth_login_success"
    AUTH_LOGIN_FAILURE = "auth_login_failure"
    AUTH_LOGOUT = "auth_logout"
    AUTH_TOKEN_CREATED = "auth_token_created"
    AUTH_TOKEN_REFRESHED = "auth_token_refreshed"
    AUTH_TOKEN_REVOKED = "auth_token_revoked"
    AUTH_SESSION_EXPIRED = "auth_session_expired"
    AUTHZ_ACCESS_GRANTED = "authz_access_granted"
    AUTHZ_ACCESS_DENIED = "authz_access_denied"
    AUTHZ_PERMISSION_CHANGED = "authz_permission_changed"
    AUTHZ_ROLE_ASSIGNED = "authz_role_assigned"
    AUTHZ_ROLE_REMOVED = "authz_role_removed"
    # API and Service Operations
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    API_ERROR = "api_error"
    API_RATE_LIMITED = "api_rate_limited"
    SERVICE_CALL = "service_call"
    SERVICE_ERROR = "service_error"
    SERVICE_TIMEOUT = "service_timeout"
    # Data Operations
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_BACKUP = "data_backup"
    DATA_RESTORE = "data_restore"
    # Database Operations
    DB_CONNECTION = "db_connection"
    DB_QUERY = "db_query"
    DB_TRANSACTION = "db_transaction"
    DB_MIGRATION = "db_migration"
    # Security Events
    SECURITY_INTRUSION_ATTEMPT = "security_intrusion_attempt"
    SECURITY_MALICIOUS_REQUEST = "security_malicious_request"
    SECURITY_VULNERABILITY_DETECTED = "security_vulnerability_detected"
    SECURITY_POLICY_VIOLATION = "security_policy_violation"
    SECURITY_ENCRYPTION_FAILURE = "security_encryption_failure"
    # System Events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SYSTEM_ERROR = "system_error"
    SYSTEM_HEALTH_CHECK = "system_health_check"
    # Admin Operations
    ADMIN_USER_CREATED = "admin_user_created"
    ADMIN_USER_DELETED = "admin_user_deleted"
    ADMIN_CONFIG_UPDATED = "admin_config_updated"
    ADMIN_SYSTEM_MAINTENANCE = "admin_system_maintenance"
    # Compliance Events
    COMPLIANCE_DATA_ACCESS = "compliance_data_access"
    COMPLIANCE_DATA_RETENTION = "compliance_data_retention"
    COMPLIANCE_AUDIT_EXPORT = "compliance_audit_export"
    COMPLIANCE_POLICY_UPDATE = "compliance_policy_update"


class AuditSeverity(Enum):
    """Audit event severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditOutcome(Enum):
    """Audit event outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class AuditContext:
    """Context information for audit events."""

    service_name: str
    environment: str
    version: str
    instance_id: str
    correlation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    """Comprehensive audit event structure."""

    # Core event information
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AuditEventType = AuditEventType.API_REQUEST
    severity: AuditSeverity = AuditSeverity.INFO
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Actor information
    user_id: str | None = None
    username: str | None = None
    session_id: str | None = None
    api_key_id: str | None = None
    client_id: str | None = None
    # Request information
    source_ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    method: str | None = None
    endpoint: str | None = None
    # Resource and action
    resource_type: str | None = None
    resource_id: str | None = None
    action: str = ""
    # Event details
    message: str = ""
    details: builtins.dict[str, Any] = field(default_factory=dict)
    # Context and tracing
    context: AuditContext | None = None
    # Performance metrics
    duration_ms: float | None = None
    response_size: int | None = None
    # Error information
    error_code: str | None = None
    error_message: str | None = None
    stack_trace: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert audit event to dictionary."""
        data = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, Enum):
                    data[key] = value.value
                elif isinstance(value, datetime):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
        return data

    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    def get_hash(self) -> str:
        """Get hash of event for integrity verification."""
        event_string = (
            f"{self.event_id}{self.timestamp.isoformat()}{self.event_type.value}{self.action}"
        )
        return hashlib.sha256(event_string.encode()).hexdigest()


class AuditEventBuilder:
    """Builder pattern for creating audit events."""

    def __init__(self, context: AuditContext | None = None):
        self._event = AuditEvent()
        if context:
            self._event.context = context

    def event_type(self, event_type: AuditEventType) -> "AuditEventBuilder":
        self._event.event_type = event_type
        return self

    def severity(self, severity: AuditSeverity) -> "AuditEventBuilder":
        self._event.severity = severity
        return self

    def outcome(self, outcome: AuditOutcome) -> "AuditEventBuilder":
        self._event.outcome = outcome
        return self

    def user(self, user_id: str, username: str | None = None) -> "AuditEventBuilder":
        self._event.user_id = user_id
        self._event.username = username
        return self

    def session(self, session_id: str) -> "AuditEventBuilder":
        self._event.session_id = session_id
        return self

    def api_key(self, api_key_id: str) -> "AuditEventBuilder":
        self._event.api_key_id = api_key_id
        return self

    def client(self, client_id: str) -> "AuditEventBuilder":
        self._event.client_id = client_id
        return self

    def request(
        self,
        source_ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        method: str | None = None,
        endpoint: str | None = None,
    ) -> "AuditEventBuilder":
        if source_ip:
            self._event.source_ip = source_ip
        if user_agent:
            self._event.user_agent = user_agent
        if request_id:
            self._event.request_id = request_id
        if method:
            self._event.method = method
        if endpoint:
            self._event.endpoint = endpoint
        return self

    def resource(self, resource_type: str, resource_id: str | None = None) -> "AuditEventBuilder":
        self._event.resource_type = resource_type
        self._event.resource_id = resource_id
        return self

    def action(self, action: str) -> "AuditEventBuilder":
        self._event.action = action
        return self

    def message(self, message: str) -> "AuditEventBuilder":
        self._event.message = message
        return self

    def detail(self, key: str, value: Any) -> "AuditEventBuilder":
        self._event.details[key] = value
        return self

    def details(self, details: builtins.dict[str, Any]) -> "AuditEventBuilder":
        self._event.details.update(details)
        return self

    def performance(
        self, duration_ms: float, response_size: int | None = None
    ) -> "AuditEventBuilder":
        self._event.duration_ms = duration_ms
        self._event.response_size = response_size
        return self

    def error(
        self,
        error_code: str | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
    ) -> "AuditEventBuilder":
        if error_code:
            self._event.error_code = error_code
        if error_message:
            self._event.error_message = error_message
        if stack_trace:
            self._event.stack_trace = stack_trace
        return self

    def correlation_id(self, correlation_id: str) -> "AuditEventBuilder":
        if not self._event.context:
            self._event.context = AuditContext("", "", "", "")
        self._event.context.correlation_id = correlation_id
        return self

    def trace_id(self, trace_id: str) -> "AuditEventBuilder":
        if not self._event.context:
            self._event.context = AuditContext("", "", "", "")
        self._event.context.trace_id = trace_id
        return self

    def build(self) -> AuditEvent:
        """Build the audit event."""
        return self._event


class AuditEncryption:
    """Handles encryption/decryption of sensitive audit data."""

    def __init__(self, encryption_key: bytes | None = None):
        self.encryption_key = encryption_key or self._derive_key()
        self.sensitive_fields = {
            "password",
            "token",
            "secret",
            "key",
            "api_key",
            "credit_card",
            "ssn",
            "email",
            "phone",
            "address",
        }

    def _derive_key(self) -> bytes:
        """Derive encryption key from environment or generate one."""
        key_material = os.environ.get(
            "AUDIT_ENCRYPTION_KEY", "default-audit-key-change-in-production"
        )
        salt = os.environ.get("AUDIT_SALT", "audit-salt-12345").encode()
        kdf = Scrypt(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(key_material.encode())

    def encrypt_sensitive_data(self, data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """Encrypt sensitive fields in audit data."""
        if not data:
            return data
        encrypted_data = data.copy()
        for key, value in data.items():
            if self._is_sensitive_field(key) and isinstance(value, str):
                encrypted_data[key] = self._encrypt_value(value)
                encrypted_data[f"{key}_encrypted"] = True
        return encrypted_data

    def decrypt_sensitive_data(self, data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """Decrypt sensitive fields in audit data."""
        if not data:
            return data
        decrypted_data = data.copy()
        for key, _value in data.items():
            if key.endswith("_encrypted"):
                field_name = key.replace("_encrypted", "")
                if field_name in data and isinstance(data[field_name], str):
                    decrypted_data[field_name] = self._decrypt_value(data[field_name])
                    del decrypted_data[key]
        return decrypted_data

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field contains sensitive data."""
        field_lower = field_name.lower()
        return any(sensitive in field_lower for sensitive in self.sensitive_fields)

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a single value."""
        try:
            # Generate random IV
            iv = os.urandom(16)
            # Create cipher
            cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            # Pad data to block size
            padded_data = value.encode("utf-8")
            padding_length = 16 - (len(padded_data) % 16)
            padded_data += bytes([padding_length]) * padding_length
            # Encrypt
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            # Return base64 encoded IV + encrypted data
            return base64.b64encode(iv + encrypted_data).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encrypt audit data: {e}")
            return f"[ENCRYPTION_FAILED:{value[:10]}...]"

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a single value."""
        try:
            # Decode base64
            raw_data = base64.b64decode(encrypted_value.encode("utf-8"))
            # Extract IV and encrypted data
            iv = raw_data[:16]
            encrypted = raw_data[16:]
            # Create cipher
            cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            # Decrypt
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            # Remove padding
            padding_length = padded_data[-1]
            data = padded_data[:-padding_length]
            return data.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decrypt audit data: {e}")
            return "[DECRYPTION_FAILED]"


class AuditDestination(ABC):
    """Abstract base class for audit logging destinations."""

    @abstractmethod
    async def log_event(self, event: AuditEvent) -> None:
        """Log audit event to destination."""

    @abstractmethod
    async def search_events(
        self, criteria: builtins.dict[str, Any], limit: int = 100
    ) -> AsyncGenerator[AuditEvent, None]:
        """Search audit events."""

    @abstractmethod
    async def close(self) -> None:
        """Close destination connection."""
