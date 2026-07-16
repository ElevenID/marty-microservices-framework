"""SQLAlchemy models for Identity Service."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AuthenticatedUserModel(Base):
    """Database model for AuthenticatedUser."""

    __tablename__ = "authenticated_users"

    user_id = Column(String, primary_key=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    roles = Column(JSON, default=list)
    permissions = Column(JSON, default=list)
    session_id = Column(String, nullable=True)
    auth_method = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)  # 'metadata' is reserved in SQLAlchemy
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": set(self.roles) if self.roles else set(),
            "permissions": set(self.permissions) if self.permissions else set(),
            "session_id": self.session_id,
            "auth_method": self.auth_method,
            "expires_at": self.expires_at,
            "metadata": self.metadata_,
            "created_at": self.created_at,
        }
