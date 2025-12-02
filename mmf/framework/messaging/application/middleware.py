from __future__ import annotations

import logging
from typing import Any

from mmf.framework.messaging.domain.models import Message, MiddlewareStage
from mmf.framework.messaging.domain.ports import IMessageMiddleware


class MiddlewareChain:
    """Middleware chain for processing messages."""

    def __init__(self):
        self.middleware: dict[MiddlewareStage, list[IMessageMiddleware]] = {}
        self.logger = logging.getLogger(__name__)

    def add_middleware(self, middleware: IMessageMiddleware) -> None:
        """Add middleware to the chain."""
        stage = middleware.get_stage()
        if stage not in self.middleware:
            self.middleware[stage] = []

        # Insert in priority order (lower priority = earlier execution)
        self.middleware[stage].append(middleware)
        self.middleware[stage].sort(key=lambda m: m.get_priority())

    async def process(
        self, message: Message, stage: MiddlewareStage, context: dict[str, Any] | None = None
    ) -> Message:
        """Process message through middleware chain for a specific stage."""
        if context is None:
            context = {}

        if stage not in self.middleware:
            return message

        processed_message = message
        for middleware in self.middleware[stage]:
            try:
                processed_message = await middleware.process(processed_message, context)
            except Exception as e:
                self.logger.error(f"Middleware {type(middleware).__name__} failed: {e}")
                # Continue with other middleware or handle based on policy

        return processed_message
