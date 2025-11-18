"""
Dependency Injection Configuration for Audit Compliance Service

This module configures all dependencies for the audit compliance service
following the hexagonal architecture pattern with proper DI container setup.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mmf_new.core.infrastructure.cache_manager import CacheManager
from mmf_new.core.infrastructure.database_manager import DatabaseManager
from mmf_new.core.infrastructure.framework_metrics import FrameworkMetrics

# Application use cases
from .application.use_cases import (
    AnalyzeThreatPatternUseCase,
    CollectSecurityEventUseCase,
    GenerateSecurityReportUseCase,
    LogAuditEventUseCase,
    ScanComplianceUseCase,
)

# Domain contracts (ports)
from .domain.contracts import (
    IAuditEventRepository,
    IAuditor,
    IComplianceScanner,
    ISecurityReportGenerator,
    ISIEMAdapter,
    IThreatAnalyzer,
)

# Infrastructure adapters
from .infrastructure import (
    AuditComplianceMetricsAdapter,
    AuditEventCache,
    AuditEventRepository,
    ComplianceScannerAdapter,
    ElasticsearchSIEMAdapter,
    SecurityReportGeneratorAdapter,
    ThreatAnalyzerAdapter,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditComplianceConfig:
    """Configuration for audit compliance service."""

    # Database configuration
    database_url: str = "postgresql://localhost/audit_compliance"
    database_pool_size: int = 20
    database_max_overflow: int = 50

    # Cache configuration
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 86400  # 24 hours
    cache_max_events: int = 10000

    # Elasticsearch configuration
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "security-events"
    elasticsearch_timeout: int = 30

    # Threat analysis configuration
    threat_confidence_threshold: float = 0.7
    threat_analysis_window_hours: int = 24
    max_events_to_analyze: int = 1000

    # Report generation configuration
    reports_output_directory: str = "./security_reports"
    reports_include_charts: bool = True
    reports_include_recommendations: bool = True

    # Compliance scanning configuration
    compliance_frameworks: list = None

    def __post_init__(self):
        if self.compliance_frameworks is None:
            self.compliance_frameworks = ["GDPR", "HIPAA", "SOX", "PCI_DSS", "ISO27001", "NIST"]


class AuditComplianceDIContainer:
    """
    Dependency injection container for audit compliance service.

    Manages the lifecycle and dependencies of all service components
    following the hexagonal architecture pattern.
    """

    def __init__(self, config: AuditComplianceConfig):
        self.config = config
        self._instances: dict[str, Any] = {}
        logger.info("Initializing audit compliance DI container")

    # Core infrastructure services

    def get_database_manager(self) -> DatabaseManager:
        """Get database manager instance."""
        if "database_manager" not in self._instances:
            self._instances["database_manager"] = DatabaseManager(
                database_url=self.config.database_url,
                pool_size=self.config.database_pool_size,
                max_overflow=self.config.database_max_overflow,
            )
            logger.info("Database manager initialized")
        return self._instances["database_manager"]

    def get_cache_manager(self) -> CacheManager:
        """Get cache manager instance."""
        if "cache_manager" not in self._instances:
            self._instances["cache_manager"] = CacheManager(
                redis_url=self.config.redis_url, default_ttl=self.config.cache_ttl_seconds
            )
            logger.info("Cache manager initialized")
        return self._instances["cache_manager"]

    def get_metrics(self) -> FrameworkMetrics:
        """Get framework metrics instance."""
        if "metrics" not in self._instances:
            self._instances["metrics"] = FrameworkMetrics()
            logger.info("Framework metrics initialized")
        return self._instances["metrics"]

    # Infrastructure adapters (implementing domain contracts)

    def get_audit_event_repository(self) -> IAuditEventRepository:
        """Get audit event repository implementation."""
        if "audit_event_repository" not in self._instances:
            self._instances["audit_event_repository"] = AuditEventRepository(
                database_manager=self.get_database_manager(), metrics=self.get_metrics()
            )
            logger.info("Audit event repository initialized")
        return self._instances["audit_event_repository"]

    def get_audit_event_cache(self) -> AuditEventCache:
        """Get audit event cache implementation."""
        if "audit_event_cache" not in self._instances:
            cache_config = {
                "max_events": self.config.cache_max_events,
                "ttl_seconds": self.config.cache_ttl_seconds,
            }
            self._instances["audit_event_cache"] = AuditEventCache(
                cache_manager=self.get_cache_manager(),
                metrics=self.get_metrics(),
                config=cache_config,
            )
            logger.info("Audit event cache initialized")
        return self._instances["audit_event_cache"]

    def get_siem_adapter(self) -> ISIEMAdapter:
        """Get SIEM adapter implementation."""
        if "siem_adapter" not in self._instances:
            siem_config = {
                "elasticsearch_url": self.config.elasticsearch_url,
                "index_name": self.config.elasticsearch_index,
                "timeout": self.config.elasticsearch_timeout,
            }
            self._instances["siem_adapter"] = ElasticsearchSIEMAdapter(
                metrics=self.get_metrics(), config=siem_config
            )
            logger.info("SIEM adapter initialized")
        return self._instances["siem_adapter"]

    def get_compliance_metrics(self) -> AuditComplianceMetricsAdapter:
        """Get audit compliance metrics adapter."""
        if "compliance_metrics" not in self._instances:
            self._instances["compliance_metrics"] = AuditComplianceMetricsAdapter(
                base_metrics=self.get_metrics()
            )
            logger.info("Compliance metrics adapter initialized")
        return self._instances["compliance_metrics"]

    def get_compliance_scanner(self) -> IComplianceScanner:
        """Get compliance scanner implementation."""
        if "compliance_scanner" not in self._instances:
            scanner_config = {"supported_frameworks": self.config.compliance_frameworks}
            self._instances["compliance_scanner"] = ComplianceScannerAdapter(
                database_manager=self.get_database_manager(),
                metrics=self.get_compliance_metrics(),
                config=scanner_config,
            )
            logger.info("Compliance scanner initialized")
        return self._instances["compliance_scanner"]

    def get_threat_analyzer(self) -> IThreatAnalyzer:
        """Get threat analyzer implementation."""
        if "threat_analyzer" not in self._instances:
            analyzer_config = {
                "confidence_threshold": self.config.threat_confidence_threshold,
                "max_events_to_analyze": self.config.max_events_to_analyze,
                "analysis_window_hours": self.config.threat_analysis_window_hours,
            }
            self._instances["threat_analyzer"] = ThreatAnalyzerAdapter(
                database_manager=self.get_database_manager(),
                metrics=self.get_compliance_metrics(),
                config=analyzer_config,
            )
            logger.info("Threat analyzer initialized")
        return self._instances["threat_analyzer"]

    def get_security_report_generator(self) -> ISecurityReportGenerator:
        """Get security report generator implementation."""
        if "security_report_generator" not in self._instances:
            generator_config = {
                "output_directory": self.config.reports_output_directory,
                "include_charts": self.config.reports_include_charts,
                "include_recommendations": self.config.reports_include_recommendations,
            }
            self._instances["security_report_generator"] = SecurityReportGeneratorAdapter(
                database_manager=self.get_database_manager(),
                metrics=self.get_compliance_metrics(),
                config=generator_config,
            )
            logger.info("Security report generator initialized")
        return self._instances["security_report_generator"]

    # Application use cases (orchestrators)

    def get_log_audit_event_use_case(self) -> LogAuditEventUseCase:
        """Get log audit event use case."""
        if "log_audit_event_use_case" not in self._instances:
            self._instances["log_audit_event_use_case"] = LogAuditEventUseCase(
                audit_repository=self.get_audit_event_repository(),
                audit_cache=self.get_audit_event_cache(),
                siem_adapter=self.get_siem_adapter(),
                metrics=self.get_compliance_metrics(),
            )
            logger.info("Log audit event use case initialized")
        return self._instances["log_audit_event_use_case"]

    def get_scan_compliance_use_case(self) -> ScanComplianceUseCase:
        """Get scan compliance use case."""
        if "scan_compliance_use_case" not in self._instances:
            self._instances["scan_compliance_use_case"] = ScanComplianceUseCase(
                compliance_scanner=self.get_compliance_scanner(),
                audit_repository=self.get_audit_event_repository(),
                metrics=self.get_compliance_metrics(),
            )
            logger.info("Scan compliance use case initialized")
        return self._instances["scan_compliance_use_case"]

    def get_analyze_threat_pattern_use_case(self) -> AnalyzeThreatPatternUseCase:
        """Get analyze threat pattern use case."""
        if "analyze_threat_pattern_use_case" not in self._instances:
            self._instances["analyze_threat_pattern_use_case"] = AnalyzeThreatPatternUseCase(
                threat_analyzer=self.get_threat_analyzer(),
                audit_repository=self.get_audit_event_repository(),
                metrics=self.get_compliance_metrics(),
            )
            logger.info("Analyze threat pattern use case initialized")
        return self._instances["analyze_threat_pattern_use_case"]

    def get_generate_security_report_use_case(self) -> GenerateSecurityReportUseCase:
        """Get generate security report use case."""
        if "generate_security_report_use_case" not in self._instances:
            self._instances["generate_security_report_use_case"] = GenerateSecurityReportUseCase(
                report_generator=self.get_security_report_generator(),
                audit_repository=self.get_audit_event_repository(),
                compliance_scanner=self.get_compliance_scanner(),
                threat_analyzer=self.get_threat_analyzer(),
                metrics=self.get_compliance_metrics(),
            )
            logger.info("Generate security report use case initialized")
        return self._instances["generate_security_report_use_case"]

    def get_collect_security_event_use_case(self) -> CollectSecurityEventUseCase:
        """Get collect security event use case."""
        if "collect_security_event_use_case" not in self._instances:
            self._instances["collect_security_event_use_case"] = CollectSecurityEventUseCase(
                siem_adapter=self.get_siem_adapter(),
                audit_repository=self.get_audit_event_repository(),
                metrics=self.get_compliance_metrics(),
            )
            logger.info("Collect security event use case initialized")
        return self._instances["collect_security_event_use_case"]

    # Service lifecycle management

    async def initialize(self):
        """Initialize all services asynchronously."""
        logger.info("Starting audit compliance service initialization")

        try:
            # Initialize core infrastructure
            await self.get_database_manager().initialize()
            await self.get_cache_manager().initialize()

            # Initialize metrics
            self.get_metrics().initialize()

            # Verify all adapters are properly configured
            self._verify_adapters()

            logger.info("Audit compliance service initialization completed successfully")

        except Exception as e:
            logger.error(f"Failed to initialize audit compliance service: {e}")
            raise

    async def shutdown(self):
        """Shutdown all services gracefully."""
        logger.info("Starting audit compliance service shutdown")

        try:
            # Shutdown in reverse order
            if "database_manager" in self._instances:
                await self._instances["database_manager"].shutdown()

            if "cache_manager" in self._instances:
                await self._instances["cache_manager"].shutdown()

            # Clear instances
            self._instances.clear()

            logger.info("Audit compliance service shutdown completed")

        except Exception as e:
            logger.error(f"Error during audit compliance service shutdown: {e}")
            raise

    def _verify_adapters(self):
        """Verify all adapters are properly instantiated."""
        critical_services = [
            "audit_event_repository",
            "compliance_scanner",
            "threat_analyzer",
            "security_report_generator",
        ]

        for service_name in critical_services:
            if service_name not in self._instances:
                logger.warning(f"Critical service not initialized: {service_name}")

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all components."""
        status = {
            "overall_status": "healthy",
            "initialized_services": len(self._instances),
            "services": {},
        }

        # Check each service
        for service_name, service_instance in self._instances.items():
            try:
                # Basic health check - service exists and is callable
                service_status = "healthy" if service_instance else "unhealthy"
                status["services"][service_name] = service_status

                if service_status == "unhealthy":
                    status["overall_status"] = "degraded"

            except Exception as e:
                status["services"][service_name] = f"error: {str(e)}"
                status["overall_status"] = "unhealthy"

        return status


# Global container instance (singleton pattern)
_container: AuditComplianceDIContainer | None = None


def get_container(config: AuditComplianceConfig | None = None) -> AuditComplianceDIContainer:
    """
    Get the global audit compliance DI container instance.

    Args:
        config: Configuration for the container (used only on first call)

    Returns:
        AuditComplianceDIContainer instance
    """
    global _container

    if _container is None:
        if config is None:
            config = AuditComplianceConfig()
        _container = AuditComplianceDIContainer(config)
        logger.info("Created new audit compliance DI container")

    return _container


def reset_container():
    """Reset the global container (useful for testing)."""
    global _container
    _container = None
    logger.info("Reset audit compliance DI container")


# Convenience functions for common use cases


async def initialize_audit_compliance_service(
    config: AuditComplianceConfig | None = None,
) -> AuditComplianceDIContainer:
    """
    Initialize the complete audit compliance service.

    Args:
        config: Optional configuration, uses defaults if not provided

    Returns:
        Initialized DI container
    """
    container = get_container(config)
    await container.initialize()
    return container


async def shutdown_audit_compliance_service():
    """Shutdown the audit compliance service."""
    global _container
    if _container:
        await _container.shutdown()
        _container = None


# Configuration factory functions


def create_development_config() -> AuditComplianceConfig:
    """Create development configuration."""
    return AuditComplianceConfig(
        database_url="postgresql://localhost/audit_compliance_dev",
        redis_url="redis://localhost:6379/1",
        elasticsearch_url="http://localhost:9200",
        reports_output_directory="./dev_reports",
    )


def create_production_config() -> AuditComplianceConfig:
    """Create production configuration."""
    return AuditComplianceConfig(
        database_url="postgresql://prod-db:5432/audit_compliance",
        redis_url="redis://prod-redis:6379/0",
        elasticsearch_url="http://prod-elasticsearch:9200",
        database_pool_size=50,
        database_max_overflow=100,
        cache_max_events=50000,
        reports_output_directory="/var/log/security_reports",
    )


def create_test_config() -> AuditComplianceConfig:
    """Create test configuration."""
    return AuditComplianceConfig(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/2",
        elasticsearch_url="http://localhost:9200",
        cache_max_events=1000,
        reports_output_directory="./test_reports",
    )
