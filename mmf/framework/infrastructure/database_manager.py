"""Database manager implementation."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class DatabaseManager:
    """Database manager using SQLAlchemy."""

    def __init__(self, database_url: str, pool_size: int = 5, max_overflow: int = 10):
        """Initialize database manager."""
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        logger.info("Database manager initialized with URL: %s", database_url)

    def get_session(self):
        """Get a new database session."""
        return self.Session()

    def create_tables(self):
        """Create all tables defined in Base metadata."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """Drop all tables defined in Base metadata."""
        Base.metadata.drop_all(self.engine)
