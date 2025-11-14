"""
Extended Messaging System Components.

This module provides the extended messaging capabilities including:
- Unified Event Bus with multiple backend support
- Extended backend implementations (NATS, AWS SNS)
- Enhanced Saga integration
- Pattern-specific abstractions
"""

# Enhanced event bus integration - use this instead of the old unified event bus
from mmf_new.core.events.enhanced_event_bus import (
    EnhancedEventBus as UnifiedEventBusImpl,
)

from .aws_sns_backend import AWSSNSBackend, AWSSNSConfig

# Core extended messaging architecture
from .extended_architecture import (
    MessageBackendType,
    MessagingPattern,
    PatternSelector,
    UnifiedEventBus,
)

# Backend implementations
from .nats_backend import NATSBackend, NATSConfig, NATSMessage

# Enhanced Saga integration
# TODO: Re-enable once patterns module is migrated
# from .saga_integration import (
#     DistributedSagaManager,
#     EnhancedSagaOrchestrator,
#     create_distributed_saga_manager,
# )

__all__ = [
    # Core types and interfaces
    "MessageBackendType",
    "MessagingPattern",
    "PatternSelector",
    "UnifiedEventBus",
    # Backend implementations
    "NATSBackend",
    "NATSConfig",
    "NATSMessage",
    "AWSSNSBackend",
    "AWSSNSConfig",
    # Unified event bus (enhanced event bus is the recommended implementation)
    "UnifiedEventBusImpl",
    # Enhanced Saga integration - disabled until patterns migration
    # "DistributedSagaManager",
    # "EnhancedSagaOrchestrator",
    # "create_distributed_saga_manager",
]
