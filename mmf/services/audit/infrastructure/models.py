"""Database models for audit service."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AuditLogRecord(Base):
    """Database model for audit log records."""

    __tablename__ = "audit_logs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core event information
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    message = Column(Text)

    # Actor information
    user_id = Column(String(255), index=True)
    username = Column(String(255))
    session_id = Column(String(255), index=True)
    api_key_id = Column(String(255))
    client_id = Column(String(255))

    # Request information
    source_ip = Column(INET)
    user_agent = Column(Text)
    request_id = Column(String(255), index=True)
    method = Column(String(10))
    endpoint = Column(String(500))

    # Resource and action
    resource_type = Column(String(100), index=True)
    resource_id = Column(String(255))
    action = Column(String(255))

    # Context
    service_name = Column(String(100), index=True)
    environment = Column(String(50), index=True)
    correlation_id = Column(String(255), index=True)
    trace_id = Column(String(255), index=True)

    # Performance metrics
    duration_ms = Column(Float)
    response_size = Column(Integer)
    status_code = Column(Integer)

    # Error information
    error_code = Column(String(100))
    error_message = Column(Text)

    # Additional data
    details = Column(JSONB)
    encrypted_fields = Column(JSONB)

    # Security correlation
    security_event_id = Column(String(36), index=True)

    # Metadata
    event_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
