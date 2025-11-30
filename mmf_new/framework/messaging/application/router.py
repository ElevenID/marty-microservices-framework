from __future__ import annotations

import logging

from mmf_new.framework.messaging.domain.models import (
    Message,
    RoutingConfig,
    RoutingRule,
)
from mmf_new.framework.messaging.domain.ports import IMessageRouter


class MessageRouter(IMessageRouter):
    """Message router implementation."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.rules: list[RoutingRule] = config.rules.copy()
        self.logger = logging.getLogger(__name__)

    async def route(self, message: Message) -> tuple[str, str]:
        """Route message and return (exchange, routing_key)."""
        # Check rules in priority order
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if await self._matches_rule(message, rule):
                return rule.exchange, rule.routing_key

        # Use default routing
        exchange = self.config.default_exchange or message.exchange
        routing_key = self.config.default_routing_key or message.routing_key
        return exchange, routing_key

    async def add_rule(self, rule: RoutingRule) -> None:
        """Add routing rule."""
        self.rules.append(rule)

    async def remove_rule(self, pattern: str) -> None:
        """Remove routing rule."""
        self.rules = [r for r in self.rules if r.pattern != pattern]

    async def get_rules(self) -> list[RoutingRule]:
        """Get all routing rules."""
        return self.rules.copy()

    async def _matches_rule(self, message: Message, rule: RoutingRule) -> bool:
        """Check if message matches routing rule."""
        # Simple pattern matching - in real implementation this would be more sophisticated
        return rule.pattern in message.routing_key or rule.pattern == "*"
