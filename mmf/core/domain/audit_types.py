"""
Shared audit and security types for cross-service use.

This module contains enums and type definitions that are used across
multiple services in the audit and compliance domain.
"""

from enum import Enum


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    NIST = "nist"


class SecurityEventType(Enum):
    """Types of security events for audit logging."""

    # Authentication events
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"

    # Authorization events
    AUTHORIZATION_GRANTED = "authorization_granted"
    AUTHORIZATION_DENIED = "authorization_denied"
    AUTHORIZATION_FAILURE = "authorization_failure"

    # Token events
    TOKEN_ISSUED = "token_issued"
    TOKEN_VALIDATED = "token_validated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REVOKED = "token_revoked"

    # Permission and role events
    PERMISSION_CHECK = "permission_check"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"

    # Policy events
    POLICY_EVALUATION = "policy_evaluation"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"
    POLICY_VIOLATION = "policy_violation"

    # Data events
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"

    # Security events
    ADMIN_ACTION = "admin_action"
    SECURITY_VIOLATION = "security_violation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALWARE_DETECTION = "malware_detection"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    VULNERABILITY_DETECTED = "vulnerability_detected"
    THREAT_DETECTED = "threat_detected"

    # System events
    RATE_LIMIT_HIT = "rate_limit_hit"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    CONFIGURATION_CHANGED = "configuration_changed"
    CONFIGURATION_CHANGE = "configuration_change"  # Alias for compatibility
    SYSTEM_ERROR = "system_error"

    # Compliance events
    COMPLIANCE_VIOLATION = "compliance_violation"

    # Network events
    NETWORK_ANOMALY = "network_anomaly"
    SYSTEM_ANOMALY = "system_anomaly"


class SecurityEventSeverity(Enum):
    """Security event severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventStatus(Enum):
    """Security event status for tracking."""

    NEW = "new"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class AuditLevel(Enum):
    """Audit logging levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SecurityThreatLevel(Enum):
    """Security threat levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityLevel(Enum):
    """Security levels for different operations."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"  # pragma: allowlist secret


class AuthenticationMethod(Enum):
    """Authentication methods supported."""

    PASSWORD = "password"  # pragma: allowlist secret
    API_KEY = "api_key"  # pragma: allowlist secret
    JWT_TOKEN = "jwt_token"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"
    MULTI_FACTOR = "multi_factor"


class AuditEventType(Enum):
    """Types of audit events for microservices framework."""

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

    # Middleware Events
    MIDDLEWARE_REQUEST_START = "middleware_request_start"
    MIDDLEWARE_REQUEST_END = "middleware_request_end"
    MIDDLEWARE_ERROR = "middleware_error"
    MIDDLEWARE_TIMEOUT = "middleware_timeout"


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


class ThreatCategory(Enum):
    """Categories of security threats."""

    AUTHENTICATION_ATTACK = "authentication_attack"
    AUTHORIZATION_BYPASS = "authorization_bypass"
    DATA_EXFILTRATION = "data_exfiltration"
    INJECTION_ATTACK = "injection_attack"
    DDoS_ATTACK = "ddos_attack"
    MALWARE = "malware"
    INSIDER_THREAT = "insider_threat"
    APT = "advanced_persistent_threat"
    BRUTE_FORCE = "brute_force"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
