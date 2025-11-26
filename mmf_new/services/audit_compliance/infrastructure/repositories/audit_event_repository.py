"""Audit event repository implementation."""

from datetime import datetime, timedelta
from typing import Any, Optional

from mmf_new.framework.infrastructure.database_manager import DatabaseManager
from mmf_new.framework.infrastructure.repository import SQLAlchemyRepository

from ...domain.contracts import IAuditEventRepository
from ...domain.models import SecurityAuditEvent


class AuditEventRepository(SQLAlchemyRepository[SecurityAuditEvent], IAuditEventRepository):
    """SQLAlchemy implementation of audit event repository."""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager.get_session, SecurityAuditEvent)
        self.db_manager = db_manager

    async def find_by_principal(
        self,
        principal_id: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SecurityAuditEvent]:
        """Find audit events by principal ID."""
        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.principal_id == principal_id
            )

            if start_time:
                query = query.filter(SecurityAuditEvent.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityAuditEvent.timestamp <= end_time)

            query = query.order_by(SecurityAuditEvent.timestamp.desc()).limit(limit)
            result = await query.all()
            return result

    async def find_by_resource(
        self,
        resource: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SecurityAuditEvent]:
        """Find audit events by resource."""
        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.resource == resource
            )

            if start_time:
                query = query.filter(SecurityAuditEvent.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityAuditEvent.timestamp <= end_time)

            query = query.order_by(SecurityAuditEvent.timestamp.desc()).limit(limit)
            result = await query.all()
            return result

    async def find_by_event_type(
        self,
        event_type: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SecurityAuditEvent]:
        """Find audit events by event type."""
        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.event_type == event_type
            )

            if start_time:
                query = query.filter(SecurityAuditEvent.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityAuditEvent.timestamp <= end_time)

            query = query.order_by(SecurityAuditEvent.timestamp.desc()).limit(limit)
            result = await query.all()
            return result

    async def find_by_correlation_id(self, correlation_id: str) -> list[SecurityAuditEvent]:
        """Find audit events by correlation ID."""
        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.correlation_id == correlation_id
            )
            query = query.order_by(SecurityAuditEvent.timestamp.asc())
            result = await query.all()
            return result

    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[SecurityAuditEvent]:
        """Find audit events by multiple criteria."""
        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent)

            # Apply filters based on criteria
            if "principal_id" in criteria:
                query = query.filter(SecurityAuditEvent.principal_id == criteria["principal_id"])

            if "resource" in criteria:
                query = query.filter(SecurityAuditEvent.resource == criteria["resource"])

            if "event_type" in criteria:
                query = query.filter(SecurityAuditEvent.event_type == criteria["event_type"])

            if "level" in criteria:
                query = query.filter(SecurityAuditEvent.level == criteria["level"])

            if "action" in criteria:
                query = query.filter(SecurityAuditEvent.action == criteria["action"])

            if "start_time" in criteria:
                query = query.filter(SecurityAuditEvent.timestamp >= criteria["start_time"])

            if "end_time" in criteria:
                query = query.filter(SecurityAuditEvent.timestamp <= criteria["end_time"])

            # Apply limit if specified
            limit = criteria.get("limit", 1000)
            query = query.order_by(SecurityAuditEvent.timestamp.desc()).limit(limit)

            result = await query.all()
            return result

    async def get_event_count_by_type(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, int]:
        """Get count of events grouped by type."""
        async with self.db_manager.get_session() as session:
            query = session.query(
                SecurityAuditEvent.event_type,
                session.query(SecurityAuditEvent)
                .filter(SecurityAuditEvent.event_type == SecurityAuditEvent.event_type)
                .count()
                .label("count"),
            )

            if start_time:
                query = query.filter(SecurityAuditEvent.timestamp >= start_time)
            if end_time:
                query = query.filter(SecurityAuditEvent.timestamp <= end_time)

            query = query.group_by(SecurityAuditEvent.event_type)
            result = await query.all()

            return {row.event_type: row.count for row in result}

    async def get_recent_critical_events(
        self, hours: int = 24, limit: int = 50
    ) -> list[SecurityAuditEvent]:
        """Get recent critical security events."""
        from mmf_new.core.domain import AuditLevel

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        async with self.db_manager.get_session() as session:
            query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.level == AuditLevel.CRITICAL,
                SecurityAuditEvent.timestamp >= cutoff_time,
            )
            query = query.order_by(SecurityAuditEvent.timestamp.desc()).limit(limit)
            result = await query.all()
            return result

    async def archive_old_events(self, days_to_keep: int = 90) -> int:
        """Archive events older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        async with self.db_manager.get_session() as session:
            # First, get count of events to be archived
            count_query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.timestamp < cutoff_date
            )
            count = await count_query.count()

            # Archive the events (in a real implementation, you might move to archive table)
            # For now, we'll just delete them
            delete_query = session.query(SecurityAuditEvent).filter(
                SecurityAuditEvent.timestamp < cutoff_date
            )
            await delete_query.delete(synchronize_session=False)
            await session.commit()

            return count

    async def get_security_metrics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get security metrics for monitoring."""
        async with self.db_manager.get_session() as session:
            base_query = session.query(SecurityAuditEvent)

            if start_time:
                base_query = base_query.filter(SecurityAuditEvent.timestamp >= start_time)
            if end_time:
                base_query = base_query.filter(SecurityAuditEvent.timestamp <= end_time)

            # Total events
            total_events = await base_query.count()

            # Events by level
            level_query = base_query.with_entities(
                SecurityAuditEvent.level,
                session.query(SecurityAuditEvent)
                .filter(SecurityAuditEvent.level == SecurityAuditEvent.level)
                .count()
                .label("count"),
            ).group_by(SecurityAuditEvent.level)

            level_counts = {row.level.value: row.count for row in await level_query.all()}

            # Most active resources
            resource_query = (
                base_query.with_entities(
                    SecurityAuditEvent.resource,
                    session.query(SecurityAuditEvent)
                    .filter(SecurityAuditEvent.resource == SecurityAuditEvent.resource)
                    .count()
                    .label("count"),
                )
                .group_by(SecurityAuditEvent.resource)
                .order_by(
                    session.query(SecurityAuditEvent)
                    .filter(SecurityAuditEvent.resource == SecurityAuditEvent.resource)
                    .count()
                    .desc()
                )
                .limit(10)
            )

            top_resources = [
                {"resource": row.resource, "count": row.count} for row in await resource_query.all()
            ]

            return {
                "total_events": total_events,
                "events_by_level": level_counts,
                "top_resources": top_resources,
                "period": {
                    "start": start_time.isoformat() if start_time else None,
                    "end": end_time.isoformat() if end_time else None,
                },
            }
