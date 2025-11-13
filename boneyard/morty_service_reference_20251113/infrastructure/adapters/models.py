"""
SQLAlchemy models for the Morty service.

These models represent the database schema and are used by the database adapters.
They are separate from domain entities to maintain clean separation of concerns.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TaskModel(Base):
    """SQLAlchemy model for tasks."""

    __tablename__ = "tasks"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    priority = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    assignee_id = Column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    # Relationships
    assignee = relationship("UserModel", back_populates="assigned_tasks", lazy="select")

    def __repr__(self):
        return f"<TaskModel(id={self.id}, title='{self.title}', status='{self.status}')>"


class UserModel(Base):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id = Column(PostgresUUID(as_uuid=True), primary_key=True)
    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, nullable=False, default=1)

    # Relationships
    assigned_tasks = relationship("TaskModel", back_populates="assignee", lazy="select")

    def __repr__(self):
        return f"<UserModel(id={self.id}, email='{self.email}', active={self.active})>"
