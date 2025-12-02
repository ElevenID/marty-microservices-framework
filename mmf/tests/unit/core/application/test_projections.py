from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.application.projections import Projection, ProjectionManager
from mmf.core.domain.entity import DomainEvent


class TestProjections:
    @pytest.fixture
    def mock_store(self):
        return MagicMock()

    @pytest.fixture
    def projection_manager(self, mock_store):
        return ProjectionManager(mock_store)

    def test_projection_base(self):
        class MyProjection(Projection):
            async def handle_event(self, event):
                self._update_metadata(event)

            async def reset(self):
                self._version = 0

        proj = MyProjection("test_proj")
        assert proj.projection_name == "test_proj"
        assert proj.version == 0
        assert proj.last_processed_event is None
        assert isinstance(proj.last_updated, datetime)

    @pytest.mark.asyncio
    async def test_projection_update_metadata(self):
        class MyProjection(Projection):
            async def handle_event(self, event):
                self._update_metadata(event)

            async def reset(self):
                pass

        proj = MyProjection("test_proj")
        event = DomainEvent(event_id="evt_1")

        await proj.handle_event(event)

        assert proj.version == 1
        assert proj.last_processed_event == "evt_1"

    @pytest.mark.asyncio
    async def test_manager_register_subscribe(self, projection_manager):
        proj = MagicMock(spec=Projection)
        proj.projection_name = "test_proj"

        projection_manager.subscribe_to_event("TestEvent", proj)

        assert "test_proj" in projection_manager._projections
        assert proj in projection_manager._event_handlers["TestEvent"]

    @pytest.mark.asyncio
    async def test_manager_handle_event(self, projection_manager):
        proj = MagicMock(spec=Projection)
        proj.projection_name = "test_proj"
        proj.handle_event = AsyncMock()

        projection_manager.subscribe_to_event("TestEvent", proj)

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        await projection_manager.handle_event(event)

        proj.handle_event.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_manager_rebuild_projection(self, projection_manager):
        proj = MagicMock(spec=Projection)
        proj.projection_name = "test_proj"
        proj.reset = AsyncMock()
        proj.handle_event = AsyncMock()

        projection_manager.register_projection(proj)

        events = [DomainEvent(), DomainEvent()]
        await projection_manager.rebuild_projection("test_proj", events)

        proj.reset.assert_called_once()
        assert proj.handle_event.call_count == 2

    @pytest.mark.asyncio
    async def test_manager_rebuild_projection_not_found(self, projection_manager):
        with pytest.raises(ValueError, match="Projection unknown not found"):
            await projection_manager.rebuild_projection("unknown", [])

    @pytest.mark.asyncio
    async def test_manager_subscribe_existing_projection(self, projection_manager):
        proj = MagicMock(spec=Projection)
        proj.projection_name = "test_proj"

        projection_manager.register_projection(proj)
        projection_manager.subscribe_to_event("TestEvent", proj)

        assert projection_manager._projections["test_proj"] == proj
        assert len(projection_manager._event_handlers["TestEvent"]) == 1

    @pytest.mark.asyncio
    async def test_manager_handle_event_no_subscribers(self, projection_manager):
        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        # Should not raise error
        await projection_manager.handle_event(event)
