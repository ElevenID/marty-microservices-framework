"""Service factory for audit service."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mmf_new.services.audit.application.commands import (
    GenerateAuditReportCommand,
    GenerateAuditReportResponse,
    LogApiCallCommand,
    LogApiCallResponse,
    LogRequestCommand,
    LogRequestResponse,
    QueryAuditEventsCommand,
    QueryAuditEventsResponse,
)
from mmf_new.services.audit.di_config import AuditConfig, AuditDIContainer

logger = logging.getLogger(__name__)


class AuditService:
    """High-level audit service API."""

    def __init__(self, container: AuditDIContainer):
        """Initialize audit service.

        Args:
            container: DI container
        """
        self.container = container
        self._initialized = False

    async def initialize(self, session_factory) -> None:
        """Initialize the audit service.

        Args:
            session_factory: Database session factory
        """
        await self.container.initialize(session_factory)
        self._initialized = True
        logger.info("Audit service initialized")

    async def shutdown(self) -> None:
        """Shutdown the audit service."""
        await self.container.shutdown()
        self._initialized = False
        logger.info("Audit service shutdown")

    async def log_request(self, command: LogRequestCommand) -> LogRequestResponse:
        """Log an audit request.

        Args:
            command: Log request command

        Returns:
            Log request response
        """
        self._check_initialized()
        use_case = self.container.get_log_request_use_case()
        return await use_case.execute(command)

    async def log_api_call(self, command: LogApiCallCommand) -> LogApiCallResponse:
        """Log an API call.

        Args:
            command: Log API call command

        Returns:
            Log API call response
        """
        self._check_initialized()
        use_case = self.container.get_log_api_call_use_case()
        return await use_case.execute(command)

    async def query_events(self, command: QueryAuditEventsCommand) -> QueryAuditEventsResponse:
        """Query audit events.

        Args:
            command: Query command

        Returns:
            Query response
        """
        self._check_initialized()
        use_case = self.container.get_query_audit_events_use_case()
        return await use_case.execute(command)

    async def generate_report(
        self, command: GenerateAuditReportCommand
    ) -> GenerateAuditReportResponse:
        """Generate an audit report.

        Args:
            command: Generate report command

        Returns:
            Generate report response
        """
        self._check_initialized()
        use_case = self.container.get_generate_audit_report_use_case()
        return await use_case.execute(command)

    async def flush(self) -> None:
        """Flush all destinations."""
        self._check_initialized()
        destinations = self.container.get_destinations()
        for destination in destinations:
            try:
                await destination.flush()
            except Exception as e:
                logger.error("Error flushing destination: %s", e)

    async def health_check(self) -> dict[str, bool]:
        """Check health of all destinations.

        Returns:
            Dictionary of destination health statuses
        """
        self._check_initialized()
        destinations = self.container.get_destinations()
        health_status = {}

        for destination in destinations:
            dest_name = destination.__class__.__name__
            try:
                health_status[dest_name] = await destination.health_check()
            except Exception as e:
                logger.error("Error checking health of %s: %s", dest_name, e)
                health_status[dest_name] = False

        return health_status

    def _check_initialized(self) -> None:
        """Check if service is initialized."""
        if not self._initialized:
            msg = "Audit service not initialized. Call initialize() first."
            raise RuntimeError(msg)


def create_audit_service(config: AuditConfig) -> AuditService:
    """Create an audit service instance.

    Args:
        config: Audit configuration

    Returns:
        Audit service instance
    """
    container = AuditDIContainer(config)
    return AuditService(container)


@asynccontextmanager
async def audit_context(config: AuditConfig, session_factory) -> AsyncGenerator[AuditService, None]:
    """Context manager for audit service lifecycle.

    Args:
        config: Audit configuration
        session_factory: Database session factory

    Yields:
        Initialized audit service
    """
    service = create_audit_service(config)
    await service.initialize(session_factory)
    try:
        yield service
    finally:
        await service.shutdown()


def create_default_audit_config(
    database_url: str,
    environment: str = "development",
) -> AuditConfig:
    """Create default audit configuration.

    Args:
        database_url: Database connection URL
        environment: Environment name (development, staging, production)

    Returns:
        Audit configuration
    """
    is_production = environment == "production"

    return AuditConfig(
        database_url=database_url,
        batch_size=100 if is_production else 10,
        flush_interval_seconds=30 if is_production else 5,
        immediate_mode=not is_production,  # Immediate in dev, batched in prod
        enabled_destinations=["database", "console"] if not is_production else ["database", "siem"],
        file_log_directory=f"./logs/audit/{environment}",
        console_use_colors=not is_production,
        console_format="pretty" if not is_production else "json",
        console_detail_level="full" if not is_production else "compact",
        encryption_enabled=True,
    )
