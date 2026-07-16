"""Unit tests for Messaging Middleware Chain."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.messaging import IMessageMiddleware, Message, MiddlewareStage
from mmf.framework.messaging.application.middleware import MiddlewareChain


class MockMiddleware(IMessageMiddleware):
    """Mock middleware for testing."""

    def __init__(self, stage: MiddlewareStage, priority: int = 100, transform_body: str = None):
        self._stage = stage
        self._priority = priority
        self._transform_body = transform_body
        self.called = False
        self.received_message = None
        self.received_context = None

    def get_stage(self) -> MiddlewareStage:
        return self._stage

    def get_priority(self) -> int:
        return self._priority

    async def process(self, message: Message, context: dict) -> Message:
        self.called = True
        self.received_message = message
        self.received_context = context
        if self._transform_body:
            message.body = {**message.body, "transformed_by": self._transform_body}
        return message


class FailingMiddleware(IMessageMiddleware):
    """Middleware that raises an exception."""

    def __init__(self, stage: MiddlewareStage):
        self._stage = stage

    def get_stage(self) -> MiddlewareStage:
        return self._stage

    def get_priority(self) -> int:
        return 100

    async def process(self, message: Message, context: dict) -> Message:
        raise RuntimeError("Middleware failure")


@pytest.fixture
def middleware_chain():
    """Create a middleware chain instance."""
    return MiddlewareChain()


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(body={"key": "value"})


@pytest.mark.unit
class TestMiddlewareChain:
    """Tests for MiddlewareChain class."""

    def test_add_middleware(self, middleware_chain):
        """Test adding middleware to the chain."""
        middleware = MockMiddleware(MiddlewareStage.PRE_PUBLISH)
        middleware_chain.add_middleware(middleware)

        assert MiddlewareStage.PRE_PUBLISH in middleware_chain.middleware
        assert middleware in middleware_chain.middleware[MiddlewareStage.PRE_PUBLISH]

    def test_add_middleware_sorted_by_priority(self, middleware_chain):
        """Test that middleware is sorted by priority."""
        low_priority = MockMiddleware(MiddlewareStage.PRE_PUBLISH, priority=200)
        high_priority = MockMiddleware(MiddlewareStage.PRE_PUBLISH, priority=50)

        middleware_chain.add_middleware(low_priority)
        middleware_chain.add_middleware(high_priority)

        chain = middleware_chain.middleware[MiddlewareStage.PRE_PUBLISH]
        assert chain[0] == high_priority  # Lower priority number = earlier execution
        assert chain[1] == low_priority

    @pytest.mark.asyncio
    async def test_process_empty_chain(self, middleware_chain, sample_message):
        """Test processing through empty chain returns original message."""
        result = await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)
        assert result is sample_message

    @pytest.mark.asyncio
    async def test_process_calls_middleware(self, middleware_chain, sample_message):
        """Test that process calls the middleware."""
        middleware = MockMiddleware(MiddlewareStage.PRE_PUBLISH)
        middleware_chain.add_middleware(middleware)

        await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)

        assert middleware.called is True
        assert middleware.received_message is sample_message

    @pytest.mark.asyncio
    async def test_process_passes_context(self, middleware_chain, sample_message):
        """Test that context is passed to middleware."""
        middleware = MockMiddleware(MiddlewareStage.PRE_PUBLISH)
        middleware_chain.add_middleware(middleware)
        context = {"user_id": "123", "trace_id": "abc"}

        await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH, context)

        assert middleware.received_context == context

    @pytest.mark.asyncio
    async def test_process_default_context(self, middleware_chain, sample_message):
        """Test that default empty context is used when none provided."""
        middleware = MockMiddleware(MiddlewareStage.PRE_PUBLISH)
        middleware_chain.add_middleware(middleware)

        await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)

        assert middleware.received_context == {}

    @pytest.mark.asyncio
    async def test_process_only_matching_stage(self, middleware_chain, sample_message):
        """Test that only middleware for the specified stage is called."""
        pre_publish = MockMiddleware(MiddlewareStage.PRE_PUBLISH)
        post_publish = MockMiddleware(MiddlewareStage.POST_PUBLISH)

        middleware_chain.add_middleware(pre_publish)
        middleware_chain.add_middleware(post_publish)

        await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)

        assert pre_publish.called is True
        assert post_publish.called is False

    @pytest.mark.asyncio
    async def test_process_chain_transforms_message(self, middleware_chain, sample_message):
        """Test that middleware can transform the message."""
        first = MockMiddleware(MiddlewareStage.PRE_PUBLISH, priority=10, transform_body="first")
        second = MockMiddleware(MiddlewareStage.PRE_PUBLISH, priority=20, transform_body="second")

        middleware_chain.add_middleware(first)
        middleware_chain.add_middleware(second)

        result = await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)

        # Both should have transformed
        assert "transformed_by" in result.body
        assert result.body["transformed_by"] == "second"  # Last one wins

    @pytest.mark.asyncio
    async def test_process_continues_after_middleware_failure(
        self, middleware_chain, sample_message
    ):
        """Test that chain continues processing after a middleware failure."""
        failing = FailingMiddleware(MiddlewareStage.PRE_PUBLISH)
        succeeding = MockMiddleware(MiddlewareStage.PRE_PUBLISH, priority=200)

        middleware_chain.add_middleware(failing)
        middleware_chain.add_middleware(succeeding)

        # Should not raise, should continue
        result = await middleware_chain.process(sample_message, MiddlewareStage.PRE_PUBLISH)

        assert succeeding.called is True
        assert result is sample_message
