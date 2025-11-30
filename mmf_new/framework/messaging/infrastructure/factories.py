"""
Messaging Infrastructure Factories

This module provides factories for creating messaging components.
It is part of the Infrastructure layer.
"""

from __future__ import annotations

from mmf_new.framework.messaging.domain.models import (
    BackendConfig,
    BackendType,
    MessagingError,
)
from mmf_new.framework.messaging.domain.ports import IMessageBackend
from mmf_new.framework.messaging.infrastructure.adapters.faststream import (
    FastStreamBackend,
)
from mmf_new.framework.messaging.infrastructure.adapters.memory import (
    MemoryMessageBackend,
)


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
            BackendType.PUBSUB,
        ):
            return FastStreamBackend(config)
        else:
            # In real implementation, create other backend types
            raise MessagingError(f"Unsupported backend type: {config.type}")
