"""Dependency injection configuration for audit service."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from mmf.core.domain.audit_types import AuditSeverity
from mmf.services.audit.application.use_cases import (
    GenerateAuditReportUseCase,
    LogApiCallUseCase,
    LogRequestUseCase,
    QueryAuditEventsUseCase,
)
from mmf.services.audit.domain.contracts import IAuditDestination
from mmf.services.audit.infrastructure.adapters.console_destination import (
    ConsoleAuditDestination,
)
from mmf.services.audit.infrastructure.adapters.database_destination import (
    DatabaseAuditDestination,
)
from mmf.services.audit.infrastructure.adapters.encryption_adapter import (
    AuditEncryptionAdapter,
)
from mmf.services.audit.infrastructure.adapters.file_destination import (
    FileAuditDestination,
)
from mmf.services.audit.infrastructure.adapters.siem_destination import (
    SIEMAuditDestination,
)
from mmf.services.audit.infrastructure.repositories.audit_repository import (
    AuditRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditConfig:
    """Configuration for audit service."""

    # Database configuration
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 50

    # Batching configuration
    batch_size: int = 100
    flush_interval_seconds: int = 30
    immediate_mode: bool = False  # True for dev, False for prod

    # Destination configuration
    enabled_destinations: list[str] = field(
        default_factory=lambda: ["database", "console"]
    )  # database, file, console, siem

    # File destination configuration
    file_log_directory: str = "./logs/audit"
    file_max_size_mb: int = 100
    file_max_files: int = 10
    file_compress: bool = True

    # Console destination configuration
    console_use_colors: bool = True
    console_format: str = "pretty"  # pretty or json
    console_detail_level: str = "compact"  # full, compact, minimal

    # SIEM configuration
    siem_adapter: object | None = None  # Optional ElasticsearchSIEMAdapter

    # Auto-forwarding configuration
    auto_forward_threshold: AuditSeverity = AuditSeverity.HIGH
    compliance_logger: object | None = None  # Optional audit_compliance logger

    # Encryption configuration
    encryption_enabled: bool = True


class AuditDIContainer:
    """Dependency injection container for audit service."""

    def __init__(self, config: AuditConfig):
        """Initialize DI container.

        Args:
            config: Audit configuration
        """
        self.config = config
        self._session_factory: Callable | None = None
        self._repository: AuditRepository | None = None
        self._destinations: list[IAuditDestination] = []
        self._encryption_adapter: AuditEncryptionAdapter | None = None
        self._initialized = False

    async def initialize(self, session_factory: Callable) -> None:
        """Initialize container components.

        Args:
            session_factory: Database session factory
        """
        if self._initialized:
            return

        self._session_factory = session_factory

        # Initialize repository
        self._repository = AuditRepository(session_factory)

        # Initialize encryption adapter
        if self.config.encryption_enabled:
            self._encryption_adapter = AuditEncryptionAdapter()

        # Initialize destinations based on configuration
        await self._initialize_destinations()

        self._initialized = True
        logger.info(
            "Audit DI container initialized with destinations: %s", self.config.enabled_destinations
        )

    async def shutdown(self) -> None:
        """Shutdown container and cleanup resources."""
        # Close all destinations
        for destination in self._destinations:
            try:
                await destination.close()
            except Exception as e:
                logger.error("Error closing destination: %s", e)

        self._initialized = False
        logger.info("Audit DI container shutdown complete")

    async def _initialize_destinations(self) -> None:
        """Initialize configured destinations."""
        self._destinations = []

        for dest_name in self.config.enabled_destinations:
            try:
                destination = await self._create_destination(dest_name)
                if destination:
                    self._destinations.append(destination)
                    logger.info("Initialized audit destination: %s", dest_name)
            except Exception as e:
                logger.error("Failed to initialize destination %s: %s", dest_name, e)

    async def _create_destination(self, dest_name: str) -> IAuditDestination | None:
        """Create destination instance by name.

        Args:
            dest_name: Name of destination (database, file, console, siem)

        Returns:
            Destination instance or None
        """
        if dest_name == "database":
            return DatabaseAuditDestination(
                session_factory=self._session_factory,
                batch_size=self.config.batch_size,
                enable_batching=not self.config.immediate_mode,
            )
        elif dest_name == "file":
            return FileAuditDestination(
                log_directory=self.config.file_log_directory,
                max_file_size_mb=self.config.file_max_size_mb,
                max_files=self.config.file_max_files,
                compress_rotated=self.config.file_compress,
            )
        elif dest_name == "console":
            return ConsoleAuditDestination(
                use_colors=self.config.console_use_colors,
                format_style=self.config.console_format,
                detail_level=self.config.console_detail_level,
            )
        elif dest_name == "siem":
            return SIEMAuditDestination(siem_adapter=self.config.siem_adapter)
        else:
            logger.warning("Unknown destination type: %s", dest_name)
            return None

    def get_repository(self) -> AuditRepository:
        """Get audit repository.

        Returns:
            Audit repository instance
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)
        return self._repository

    def get_destinations(self) -> list[IAuditDestination]:
        """Get all configured destinations.

        Returns:
            List of destination instances
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)
        return self._destinations

    def get_encryption_adapter(self) -> AuditEncryptionAdapter | None:
        """Get encryption adapter.

        Returns:
            Encryption adapter or None
        """
        return self._encryption_adapter

    def get_log_request_use_case(self) -> LogRequestUseCase:
        """Get log request use case.

        Returns:
            Use case instance
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)

        return LogRequestUseCase(
            repository=self._repository,
            destinations=self._destinations,
            auto_forward_threshold=self.config.auto_forward_threshold,
            compliance_logger=self.config.compliance_logger,
        )

    def get_log_api_call_use_case(self) -> LogApiCallUseCase:
        """Get log API call use case.

        Returns:
            Use case instance
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)

        return LogApiCallUseCase(
            repository=self._repository,
            destinations=self._destinations,
            auto_forward_threshold=self.config.auto_forward_threshold,
            compliance_logger=self.config.compliance_logger,
        )

    def get_query_audit_events_use_case(self) -> QueryAuditEventsUseCase:
        """Get query audit events use case.

        Returns:
            Use case instance
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)

        return QueryAuditEventsUseCase(repository=self._repository)

    def get_generate_audit_report_use_case(self) -> GenerateAuditReportUseCase:
        """Get generate audit report use case.

        Returns:
            Use case instance
        """
        if not self._initialized:
            msg = "Container not initialized"
            raise RuntimeError(msg)

        return GenerateAuditReportUseCase(repository=self._repository)
