"""
Dependency Injection Configuration for Audit Compliance Service

This module configures all dependencies for the audit compliance service
following the hexagonal architecture pattern with proper DI container setup.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mmf_new.framework.infrastructure.cache import CacheBackend, CacheConfig, CacheFactory, CacheManager
from mmf_new.framework.infrastructure.database_manager import DatabaseManager
from mmf_new.framework.infrastructure.framework_metrics import FrameworkMetrics
from mmf_new.core.di import AsyncBaseDIContainer

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


class AuditComplianceDIContainer(AsyncBaseDIContainer):
    """
    Dependency injection container for audit compliance service.

    Manages the lifecycle and dependencies of all service components
    following the hexagonal architecture pattern.
    """

    def __init__(self, config: AuditComplianceConfig):
        super().__init__()
        self.config = config
        
        # Infrastructure
        self._database_manager: DatabaseManager | None = None
        self._cache_manager: CacheManager | None = None
        self._metrics: FrameworkMetrics | None = None
        
        # Adapters
        self._audit_event_repository: IAuditEventRepository | None = None
        self._audit_event_cache: AuditEventCache | None = None
        self._siem_adapter: ISIEMAdapter | None = None
        self._compliance_metrics: AuditComplianceMetricsAdapter | None = None
        self._compliance_scanner: IComplianceScanner | None = None
        self._threat_analyzer: IThreatAnalyzer | None = None
        self._security_report_generator: ISecurityReportGenerator | None = None
        
        # Use Cases
        self._log_audit_event_use_case: LogAuditEventUseCase | None = None
        self._collect_security_event_use_case: CollectSecurityEventUseCase | None = None
        self._scan_compliance_use_case: ScanComplianceUseCase | None = None
        self._analyze_threat_pattern_use_case: AnalyzeThreatPatternUseCase | None = None
        self._generate_security_report_use_case: GenerateSecurityReportUseCase | None = None

    async def initialize(self) -> None:
        logger.info("Initializing audit compliance DI container")
        
        # Initialize Infrastructure
        self._database_manager = DatabaseManager(
            database_url=self.config.database_url,
            pool_size=self.config.database_pool_size,
            max_overflow=self.config.database_max_overflow,
        )
        
        cache_config = CacheConfig(
            backend=CacheBackend.REDIS if self.config.redis_url else CacheBackend.MEMORY,
            url=self.config.redis_url,
            default_ttl=self.config.cache_ttl_seconds
        )
        self._cache_manager = CacheFactory.create_manager(cache_config)
        
        self._metrics = FrameworkMetrics()
        
        # Initialize Adapters
        self._audit_event_repository = AuditEventRepository(
            database_manager=self._database_manager, metrics=self._metrics
        )
        
        audit_cache_config = {
            "max_events": self.config.cache_max_events,
            "ttl_seconds": self.config.cache_ttl_seconds,
        }
        self._audit_event_cache = AuditEventCache(
            cache_manager=self._cache_manager,
            metrics=self._metrics,
            config=audit_cache_config,
        )
        
        siem_config = {
            "elasticsearch_url": self.config.elasticsearch_url,
            "index_name": self.config.elasticsearch_index,
            "timeout": self.config.elasticsearch_timeout,
        }
        self._siem_adapter = ElasticsearchSIEMAdapter(
            metrics=self._metrics, config=siem_config
        )
        
        self._compliance_metrics = AuditComplianceMetricsAdapter(
            base_metrics=self._metrics
        )
        
        scanner_config = {"supported_frameworks": self.config.compliance_frameworks}
        self._compliance_scanner = ComplianceScannerAdapter(
            database_manager=self._database_manager,
            metrics=self._compliance_metrics,
            config=scanner_config,
        )
        
        analyzer_config = {
            "confidence_threshold": self.config.threat_confidence_threshold,
            "max_events_to_analyze": self.config.max_events_to_analyze,
            "analysis_window_hours": self.config.threat_analysis_window_hours,
        }
        self._threat_analyzer = ThreatAnalyzerAdapter(
            database_manager=self._database_manager,
            metrics=self._compliance_metrics,
            config=analyzer_config,
        )
        
        report_config = {
            "output_directory": self.config.reports_output_directory,
            "include_charts": self.config.reports_include_charts,
            "include_recommendations": self.config.reports_include_recommendations,
        }
        self._security_report_generator = SecurityReportGeneratorAdapter(
            database_manager=self._database_manager,
            metrics=self._compliance_metrics,
            config=report_config,
        )
        
        # Initialize Use Cases
        self._log_audit_event_use_case = LogAuditEventUseCase(
            audit_repository=self._audit_event_repository,
            audit_cache=self._audit_event_cache,
            siem_adapter=self._siem_adapter,
        )
        
        self._collect_security_event_use_case = CollectSecurityEventUseCase(
            audit_repository=self._audit_event_repository,
            siem_adapter=self._siem_adapter,
            threat_analyzer=self._threat_analyzer,
        )
        
        self._scan_compliance_use_case = ScanComplianceUseCase(
            compliance_scanner=self._compliance_scanner,
            audit_repository=self._audit_event_repository,
        )
        
        self._analyze_threat_pattern_use_case = AnalyzeThreatPatternUseCase(
            threat_analyzer=self._threat_analyzer,
            audit_repository=self._audit_event_repository,
        )
        
        self._generate_security_report_use_case = GenerateSecurityReportUseCase(
            report_generator=self._security_report_generator,
            audit_repository=self._audit_event_repository,
            compliance_scanner=self._compliance_scanner,
        )
        
        # Async initialization
        if self.config.redis_url:
            await self._cache_manager.start()

        await self._database_manager.initialize()
        self._metrics.initialize()
        
        self._mark_initialized()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._cache_manager:
            await self._cache_manager.shutdown()
        if self._database_manager:
            await self._database_manager.shutdown()
        self._mark_cleanup()

    @property
    def database_manager(self) -> DatabaseManager:
        self._ensure_initialized()
        assert self._database_manager is not None
        return self._database_manager

    @property
    def cache_manager(self) -> CacheManager:
        self._ensure_initialized()
        assert self._cache_manager is not None
        return self._cache_manager

    @property
    def metrics(self) -> FrameworkMetrics:
        self._ensure_initialized()
        assert self._metrics is not None
        return self._metrics

    @property
    def audit_event_repository(self) -> IAuditEventRepository:
        self._ensure_initialized()
        assert self._audit_event_repository is not None
        return self._audit_event_repository

    @property
    def audit_event_cache(self) -> AuditEventCache:
        self._ensure_initialized()
        assert self._audit_event_cache is not None
        return self._audit_event_cache

    @property
    def siem_adapter(self) -> ISIEMAdapter:
        self._ensure_initialized()
        assert self._siem_adapter is not None
        return self._siem_adapter

    @property
    def compliance_metrics(self) -> AuditComplianceMetricsAdapter:
        self._ensure_initialized()
        assert self._compliance_metrics is not None
        return self._compliance_metrics

    @property
    def compliance_scanner(self) -> IComplianceScanner:
        self._ensure_initialized()
        assert self._compliance_scanner is not None
        return self._compliance_scanner

    @property
    def threat_analyzer(self) -> IThreatAnalyzer:
        self._ensure_initialized()
        assert self._threat_analyzer is not None
        return self._threat_analyzer

    @property
    def security_report_generator(self) -> ISecurityReportGenerator:
        self._ensure_initialized()
        assert self._security_report_generator is not None
        return self._security_report_generator

    @property
    def log_audit_event_use_case(self) -> LogAuditEventUseCase:
        self._ensure_initialized()
        assert self._log_audit_event_use_case is not None
        return self._log_audit_event_use_case

    @property
    def collect_security_event_use_case(self) -> CollectSecurityEventUseCase:
        self._ensure_initialized()
        assert self._collect_security_event_use_case is not None
        return self._collect_security_event_use_case

    @property
    def scan_compliance_use_case(self) -> ScanComplianceUseCase:
        self._ensure_initialized()
        assert self._scan_compliance_use_case is not None
        return self._scan_compliance_use_case

    @property
    def analyze_threat_pattern_use_case(self) -> AnalyzeThreatPatternUseCase:
        self._ensure_initialized()
        assert self._analyze_threat_pattern_use_case is not None
        return self._analyze_threat_pattern_use_case

    @property
    def generate_security_report_use_case(self) -> GenerateSecurityReportUseCase:
        self._ensure_initialized()
        assert self._generate_security_report_use_case is not None
        return self._generate_security_report_use_case


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
        await _container.cleanup()
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
