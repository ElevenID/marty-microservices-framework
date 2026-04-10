"""
Service discovery service for monitoring registered services.
"""

import asyncio
import builtins
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import list

import httpx
from sqlalchemy import select

from ..config import get_settings
from ..database import AsyncSessionLocal, Service

logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Service information dataclass."""

    name: str
    address: str
    port: int
    health_check_url: str | None = None
    status: str = "unknown"
    tags: builtins.list[str] = None
    metadata: builtins.dict = None
    last_seen: datetime | None = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class ServiceDiscoveryService:
    """Service discovery and health monitoring service."""

    def __init__(self):
        self.settings = get_settings()
        self.services: builtins.dict[str, ServiceInfo] = {}
        self.running = False
        self.task: asyncio.Task | None = None
        self.http_client: httpx.AsyncClient | None = None

    async def start(self):
        """Start the service discovery service."""
        if self.running:
            return

        self.running = True
        self.http_client = httpx.AsyncClient(timeout=10.0)

        # Load existing services from database
        await self._load_services_from_db()

        # Start monitoring task
        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info("Service discovery service started")

    async def stop(self):
        """Stop the service discovery service."""
        if not self.running:
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        if self.http_client:
            await self.http_client.aclose()

        logger.info("Service discovery service stopped")

    async def register_service(self, service_info: ServiceInfo) -> bool:
        """Register a new service."""
        try:
            async with AsyncSessionLocal() as session:
                # Upsert: insert or update on conflict to avoid TOCTOU race
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                values = dict(
                    name=service_info.name,
                    address=service_info.address,
                    port=service_info.port,
                    health_check_url=service_info.health_check_url,
                    tags=service_info.tags,
                    metadata=service_info.metadata,
                    last_seen=datetime.utcnow(),
                )
                stmt = (
                    pg_insert(Service)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["name"],
                        set_=dict(
                            address=service_info.address,
                            port=service_info.port,
                            health_check_url=service_info.health_check_url,
                            tags=service_info.tags,
                            metadata=service_info.metadata,
                            last_seen=datetime.utcnow(),
                        ),
                    )
                )
                await session.execute(stmt)
                await session.commit()

                # Update in-memory cache
                self.services[service_info.name] = service_info

                logger.info(f"Service registered: {service_info.name}")
                return True

        except Exception as exc:
            logger.error(f"Failed to register service {service_info.name}: {exc}")
            return False

    async def deregister_service(self, service_name: str) -> bool:
        """Deregister a service."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Service).where(Service.name == service_name)
                result = await session.execute(stmt)
                service = result.scalar_one_or_none()

                if service:
                    await session.delete(service)
                    await session.commit()

                    # Remove from in-memory cache
                    self.services.pop(service_name, None)

                    logger.info(f"Service deregistered: {service_name}")
                    return True

        except Exception as exc:
            logger.error(f"Failed to deregister service {service_name}: {exc}")

        return False

    async def get_services(self) -> builtins.list[ServiceInfo]:
        """Get all registered services."""
        return list(self.services.values())

    async def get_service(self, service_name: str) -> ServiceInfo | None:
        """Get a specific service by name."""
        return self.services.get(service_name)

    async def _load_services_from_db(self):
        """Load services from database."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Service)
                result = await session.execute(stmt)
                services = result.scalars().all()

                for service in services:
                    service_info = ServiceInfo(
                        name=service.name,
                        address=service.address,
                        port=service.port,
                        health_check_url=service.health_check_url,
                        status=service.status,
                        tags=service.tags or [],
                        metadata=service.metadata or {},
                        last_seen=service.last_seen,
                    )
                    self.services[service.name] = service_info

                logger.info(f"Loaded {len(services)} services from database")

        except Exception as exc:
            logger.error(f"Failed to load services from database: {exc}")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self._check_service_health()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in monitoring loop: {exc}")
                await asyncio.sleep(5)

    async def _check_service_health(self):
        """Check health of all registered services."""
        for service_name, service_info in self.services.items():
            try:
                await self._check_single_service_health(service_info)
            except Exception as exc:
                logger.error(f"Failed to check health for {service_name}: {exc}")

    async def _check_single_service_health(self, service_info: ServiceInfo):
        """Check health of a single service."""
        if not service_info.health_check_url:
            # If no health check URL, try to ping the service
            health_url = f"http://{service_info.address}:{service_info.port}/health"
        else:
            health_url = service_info.health_check_url

        try:
            response = await self.http_client.get(health_url)
            if response.status_code == 200:
                service_info.status = "healthy"
            else:
                service_info.status = "unhealthy"

            service_info.last_seen = datetime.utcnow()

            # Update database
            async with AsyncSessionLocal() as session:
                stmt = select(Service).where(Service.name == service_info.name)
                result = await session.execute(stmt)
                db_service = result.scalar_one_or_none()

                if db_service:
                    db_service.status = service_info.status
                    db_service.last_seen = service_info.last_seen
                    await session.commit()

        except Exception:
            service_info.status = "unhealthy"

            # Mark as unhealthy in database
            async with AsyncSessionLocal() as session:
                stmt = select(Service).where(Service.name == service_info.name)
                result = await session.execute(stmt)
                db_service = result.scalar_one_or_none()

                if db_service:
                    db_service.status = "unhealthy"
                    await session.commit()
