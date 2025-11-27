"""
Security Framework Adapter

This module provides the main entry point for initializing and accessing the security framework.
It replaces the legacy SecurityHardeningFramework and SecurityServiceFactory.
"""

from __future__ import annotations

import logging

import bcrypt

from mmf_new.core.security.domain.config import SecurityConfig
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.core.security.ports.common import IAuditor
from mmf_new.framework.authorization.bootstrap import create_role_based_authorizer
from mmf_new.framework.infrastructure.dependency_injection import (
    get_service,
    has_service,
    register_instance,
)
from mmf_new.services.audit_compliance.di_config import (
    get_container as get_audit_container,
)
from mmf_new.services.audit_compliance.service_factory import AuditComplianceService

# Import service factories/managers
from mmf_new.services.identity import (
    AuthenticationMethod,
    BasicAuthAdapter,
    BasicAuthConfig,
    authentication_manager,
)

from ..ports.service_mesh import IServiceMeshManager
from ..ports.threat_detection import IThreatDetector, IVulnerabilityScanner

# Import adapters
from .implementations import (
    AuditServiceAdapter,
    CoreAuthorizerAdapter,
    IdentityServiceAuthenticator,
)
from .service_mesh.istio_mesh_manager import IstioMeshManager
from .threat_detection.event_processor import EventProcessorThreatDetector
from .threat_detection.ml_analyzer import MLThreatDetector
from .threat_detection.pattern_detector import PatternBasedThreatDetector
from .threat_detection.scanner import VulnerabilityScanner

logger = logging.getLogger(__name__)


class SecurityHardeningFramework:
    """
    Modern security hardening framework that integrates all security components
    using hexagonal architecture and dependency injection.
    """

    def __init__(self, config: SecurityConfig):
        self.config = config
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all security services and register them in the DI container."""
        if self._initialized:
            logger.warning("Security framework already initialized")
            return

        logger.info("Initializing Security Hardening Framework...")

        # 1. Initialize and register Authenticator
        self._initialize_authenticator()

        # 2. Initialize and register Authorizer
        self._initialize_authorizer()

        # 3. Initialize and register Auditor
        self._initialize_auditor()

        # 4. Initialize and register Secret Manager
        self._initialize_secret_manager()

        # 5. Initialize and register Service Mesh Manager
        self._initialize_service_mesh_manager()

        # 6. Initialize and register Threat Detector
        self._initialize_threat_detector()

        self._initialized = True
        logger.info("Security Hardening Framework initialized successfully")

    def _initialize_authenticator(self) -> None:
        """Initialize authentication service."""
        # Use the singleton authentication_manager from identity service

        # Register Basic Auth Provider
        config = BasicAuthConfig()
        basic_provider = BasicAuthAdapter(config)

        # Add demo user manually (since there is no public API for it in the adapter yet)

        password = "demo_pass"
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=config.bcrypt_rounds)
        )

        basic_provider._users["demo_user"] = {
            "user_id": "user_demo_user",
            "email": "demo@example.com",
            "roles": ["admin"],
            "permissions": ["read", "write"],
            "password_hash": password_hash.decode("utf-8"),
            "created_at": "2023-01-01T00:00:00Z",
            "password_changed_at": "2023-01-01T00:00:00Z",
            "is_active": True,
        }

        authentication_manager.register_provider(
            AuthenticationMethod.BASIC, basic_provider, is_default=True
        )

        # Wrap it in our adapter
        authenticator = IdentityServiceAuthenticator(authentication_manager)
        register_instance(IAuthenticator, authenticator)
        logger.debug("Registered IAuthenticator")

    def _initialize_authorizer(self) -> None:
        """Initialize authorization service."""
        # Create a default authorizer (e.g., RBAC)
        # In a real scenario, we might choose based on config
        core_authorizer = create_role_based_authorizer()
        authorizer = CoreAuthorizerAdapter(core_authorizer)
        register_instance(IAuthorizer, authorizer)
        logger.debug("Registered IAuthorizer")

    def _initialize_auditor(self) -> None:
        """Initialize audit service."""
        # Create AuditComplianceService
        # Assuming it can be instantiated or retrieved
        # For now, we'll instantiate it directly or get from DI if already there
        if has_service(AuditComplianceService):
            audit_service = get_service(AuditComplianceService)
        else:
            # Pass the container to AuditComplianceService
            container = get_audit_container()
            audit_service = AuditComplianceService(container=container)
            register_instance(AuditComplianceService, audit_service)

        auditor = AuditServiceAdapter(audit_service)
        register_instance(IAuditor, auditor)
        logger.debug("Registered IAuditor")

    def _initialize_secret_manager(self) -> None:
        """Initialize secret manager."""
        # TODO: Implement secret manager initialization
        # For now, we skip or register a placeholder if needed

    def _initialize_service_mesh_manager(self) -> None:
        """Initialize service mesh manager."""
        if self.config.service_mesh_config.enabled:
            mesh_manager = IstioMeshManager(self.config.service_mesh_config)
            register_instance(IServiceMeshManager, mesh_manager)
            logger.debug("Registered IServiceMeshManager")
        else:
            logger.debug("Service mesh integration disabled")

    def _initialize_threat_detector(self) -> None:
        """Initialize threat detection services."""
        if not self.config.enable_threat_detection:
            logger.debug("Threat detection disabled")
            return

        # 1. Initialize Event Processor (Primary Detector)
        event_processor = EventProcessorThreatDetector(self.config.threat_detection_config)

        # 2. Initialize ML Detector (if enabled)
        if self.config.threat_detection_config.enable_ml_detection:
            ml_detector = MLThreatDetector(self.config.threat_detection_config)
            register_instance(MLThreatDetector, ml_detector)

        # 3. Initialize Pattern Detector
        pattern_detector = PatternBasedThreatDetector(self.config.service_name)
        register_instance(PatternBasedThreatDetector, pattern_detector)

        # Register the primary threat detector (Event Processor)
        register_instance(IThreatDetector, event_processor)
        register_instance(EventProcessorThreatDetector, event_processor)

        # 4. Initialize Vulnerability Scanner
        scanner = VulnerabilityScanner(self.config.service_name)
        register_instance(IVulnerabilityScanner, scanner)

        logger.debug("Registered IThreatDetector and IVulnerabilityScanner")


class SecurityServiceFactory:
    """
    Factory for creating/retrieving security services.
    Maintained for backward compatibility but delegates to DI container.
    """

    @staticmethod
    def get_authenticator() -> IAuthenticator:
        return get_service(IAuthenticator)

    @staticmethod
    def get_authorizer() -> IAuthorizer:
        return get_service(IAuthorizer)

    @staticmethod
    def get_auditor() -> IAuditor:
        return get_service(IAuditor)

    @staticmethod
    def get_service_mesh_manager() -> IServiceMeshManager:
        return get_service(IServiceMeshManager)

    @staticmethod
    def get_threat_detector() -> IThreatDetector:
        return get_service(IThreatDetector)

    @staticmethod
    def get_vulnerability_scanner() -> IVulnerabilityScanner:
        return get_service(IVulnerabilityScanner)


def initialize_security_system(config: SecurityConfig) -> SecurityHardeningFramework:
    """Helper function to initialize the security system."""
    framework = SecurityHardeningFramework(config)
    framework.initialize()
    register_instance(SecurityHardeningFramework, framework)
    return framework
