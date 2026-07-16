"""
Messaging Infrastructure Factories

This module provides factories for creating messaging components.
It is part of the Infrastructure layer.
"""

from __future__ import annotations

from mmf.core.messaging import (
    BackendConfig,
    BackendType,
    IMessageBackend,
    MessagingError,
)
from mmf.framework.messaging.infrastructure.adapters.memory import MemoryMessageBackend


class BackendFactory:
    """Factory for creating message backends."""

    @staticmethod
    def create_backend(config: BackendConfig) -> IMessageBackend:
        """Create a message backend based on configuration."""
        if config.type == BackendType.MEMORY:
            return MemoryMessageBackend(config)
        elif config.type in (
            BackendType.KAFKA,
            BackendType.RABBITMQ,
            BackendType.REDIS,
            BackendType.NATS,
        ):
            from mmf.framework.messaging.infrastructure.adapters.faststream_adapter import (
                FastStreamBackend,
            )

            return FastStreamBackend(config)
        else:
            # In real implementation, create other backend types
            raise MessagingError(f"Unsupported backend type: {config.type}")
