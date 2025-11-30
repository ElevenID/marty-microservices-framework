"""
Security Framework Adapter

This module provides the main entry point for initializing and accessing the security framework.
It replaces the legacy SecurityHardeningFramework and SecurityServiceFactory.
"""

from __future__ import annotations

import logging

from mmf_new.core.security.domain.config import SecurityConfig
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.core.security.ports.common import IAuditor
from mmf_new.core.security.ports.service_mesh import IServiceMeshManager
from mmf_new.core.security.ports.threat_detection import (
    IThreatDetector,
    IVulnerabilityScanner,
)
from mmf_new.framework.infrastructure.dependency_injection import (
    get_service,
    register_instance,
)
from mmf_new.framework.security.adapters.audit.factory import AuditFactory
from mmf_new.framework.security.adapters.authentication.factory import (
    AuthenticationFactory,
)
from mmf_new.framework.security.adapters.authorization.factory import (
    AuthorizationFactory,
)
from mmf_new.framework.security.adapters.secrets.factory import SecretsFactory
from mmf_new.framework.security.adapters.service_mesh.factory import ServiceMeshFactory
from mmf_new.framework.security.adapters.threat_detection.factory import (
    ThreatDetectionFactory,
)

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
        registrations = AuthenticationFactory.create_registrations()
        for entry in registrations:
            register_instance(entry.interface, entry.instance)
        logger.debug("Registered IAuthenticator")

    def _initialize_authorizer(self) -> None:
        """Initialize authorization service."""
        registrations = AuthorizationFactory.create_registrations()
        for entry in registrations:
            register_instance(entry.interface, entry.instance)
        logger.debug("Registered IAuthorizer")

    def _initialize_auditor(self) -> None:
        """Initialize audit service."""
        registrations = AuditFactory.create_registrations()
        for entry in registrations:
            register_instance(entry.interface, entry.instance)
        logger.debug("Registered IAuditor")

    def _initialize_secret_manager(self) -> None:
        """Initialize secret manager."""
        registrations = SecretsFactory.create_registrations(self.config)
        for entry in registrations:
            register_instance(entry.interface, entry.instance)
        logger.debug("Registered ISecretManager")

    def _initialize_service_mesh_manager(self) -> None:
        """Initialize service mesh manager."""
        mesh_manager = ServiceMeshFactory.create_manager(self.config.service_mesh_config)
        if mesh_manager:
            register_instance(IServiceMeshManager, mesh_manager)
            logger.debug("Registered IServiceMeshManager")
        else:
            logger.debug("Service mesh integration disabled")

    def _initialize_threat_detector(self) -> None:
        """Initialize threat detection services."""
        if not self.config.enable_threat_detection:
            logger.debug("Threat detection disabled")
            return

        registrations = ThreatDetectionFactory.create_registrations(self.config)
        for entry in registrations:
            register_instance(entry.interface, entry.instance)

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
