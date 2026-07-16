"""
Workflow Persistence Models.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WorkflowModel(Base):
    """SQLAlchemy model for workflow state."""

    __tablename__ = "workflows"

    id = Column(String, primary_key=True)
    correlation_id = Column(String, index=True)
    status = Column(String, nullable=False)
    context_data = Column(Text)  # JSON string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))
    version = Column(Integer, default=1)
