"""
Base database models and mixins for the enterprise database framework.
"""

import builtins
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class BaseModel(DeclarativeBase):
    """Base model class for all database models."""

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case

        name = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
        return name

    def to_dict(self, include_relationships: bool = False) -> builtins.dict[str, Any]:
        """Convert model instance to dictionary."""
        result = {}

        # Include all columns
        for column in self.__table__.columns:
            value = getattr(self, column.name)

            # Handle datetime objects
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value

        # Include relationships if requested
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                value = getattr(self, relationship.key)
                if value is not None:
                    if hasattr(value, "to_dict"):
                        result[relationship.key] = value.to_dict()
                    elif hasattr(value, "__iter__"):
                        result[relationship.key] = [
                            item.to_dict() if hasattr(item, "to_dict") else str(item)
                            for item in value
                        ]
                    else:
                        result[relationship.key] = str(value)

        return result

    def update_from_dict(self, data: builtins.dict[str, Any], exclude: set | None = None) -> None:
        """Update model instance from dictionary."""
        exclude = exclude or set()

        for key, value in data.items():
            if key in exclude:
                continue

            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__

        # Try to find a primary key or identifier
        id_value = None
        if hasattr(self, "id"):
            id_value = self.id
        elif hasattr(self, "uuid"):
            id_value = self.uuid
        elif hasattr(self, "pk"):
            id_value = self.pk

        if id_value is not None:
            return f"<{class_name}(id={id_value})>"
        return f"<{class_name}()>"


class TimestampMixin:
    """Mixin for adding timestamp fields."""

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        doc="Timestamp when the record was created",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        server_onupdate=func.now(),
        doc="Timestamp when the record was last updated",
    )


class AuditMixin:
    """Mixin for adding audit fields."""

    created_by = Column(String(255), nullable=True, doc="User ID who created the record")

    updated_by = Column(String(255), nullable=True, doc="User ID who last updated the record")

    created_ip = Column(
        String(45),  # IPv6 length
        nullable=True,
        doc="IP address from which the record was created",
    )

    updated_ip = Column(
        String(45),  # IPv6 length
        nullable=True,
        doc="IP address from which the record was last updated",
    )

    version = Column(
        Integer, nullable=False, default=1, doc="Version number for optimistic locking"
    )


class SoftDeleteMixin:
    """Mixin for adding soft delete functionality."""

    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Whether the record is soft deleted",
    )

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the record was soft deleted",
    )

    deleted_by = Column(String(255), nullable=True, doc="User ID who soft deleted the record")

    def soft_delete(self, deleted_by: str | None = None) -> None:
        """Soft delete the record."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class UUIDMixin:
    """Mixin for adding UUID field."""

    uuid = Column(
        String(36),
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        index=True,
        doc="Unique identifier for the record",
    )


class MetadataMixin:
    """Mixin for adding metadata field."""

    metadata_ = Column(JSON, nullable=True, doc="Additional metadata for the record")

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata value."""
        if self.metadata_ is None:
            self.metadata_ = {}
        self.metadata_[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value."""
        if self.metadata_ is None:
            return default
        return self.metadata_.get(key, default)

    def remove_metadata(self, key: str) -> None:
        """Remove a metadata key."""
        if self.metadata_ and key in self.metadata_:
            del self.metadata_[key]


class FullAuditModel(BaseModel, TimestampMixin, AuditMixin, SoftDeleteMixin, UUIDMixin):
    """Full audit model with all common fields."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")


class SimpleModel(BaseModel, TimestampMixin):
    """Simple model with just timestamps."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")


# Example models for common use cases


class ServiceAuditLog(FullAuditModel):
    """Audit log for service actions."""

    __tablename__ = "service_audit_log"

    service_name = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
    user_id = Column(String(255), nullable=True)
    session_id = Column(String(255), nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)


class ServiceConfiguration(SimpleModel):
    """Service configuration storage."""

    __tablename__ = "service_configuration"

    service_name = Column(String(100), nullable=False, index=True)
    config_key = Column(String(255), nullable=False)
    config_value = Column(Text, nullable=True)
    config_type = Column(String(50), nullable=False, default="string")
    description = Column(Text, nullable=True)
    is_secret = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)


class ServiceHealthCheck(SimpleModel):
    """Service health check results."""

    __tablename__ = "service_health_check"

    service_name = Column(String(100), nullable=False, index=True)
    check_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # healthy, unhealthy, unknown
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
