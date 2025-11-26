import pytest_asyncio
from mmf_new.framework.testing.infrastructure.database import TestDatabaseManager

@pytest_asyncio.fixture
async def test_database():
    """Provide test database."""
    db = TestDatabaseManager()
    await db.create_tables()
    try:
        yield db
    finally:
        await db.cleanup()

@pytest_asyncio.fixture
async def test_session(test_database):  # pylint: disable=redefined-outer-name
    """Provide test database session."""
    async with test_database.get_session() as session:
        yield session
