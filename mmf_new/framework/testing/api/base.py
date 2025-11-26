import logging
import pytest
from unittest.mock import AsyncMock, Mock
from mmf_new.framework.testing.infrastructure.database import TestDatabaseManager
from mmf_new.framework.testing.infrastructure.events import TestEventCollector

class AsyncTestCase:
    """Base class for async test cases."""

    @pytest.fixture(autouse=True)
    async def setup_async_test(self):
        """Setup async test environment."""
        # Disable logging during tests
        logging.getLogger("mmf_new").setLevel(logging.WARNING)

        # Setup test database
        self.test_db = TestDatabaseManager()
        await self.test_db.create_tables()

        # Setup test event bus (mocked)
        self.test_event_bus = AsyncMock()

        # Setup event collector
        self.event_collector = TestEventCollector()

        # Setup test metrics (mocked)
        self.test_metrics = Mock()

        yield

        # Cleanup
        await self.test_db.cleanup()
