"""
Service Discovery Adapters Layer
"""

from .consul_adapter import ConsulAdapter
from .memory_registry import MemoryRegistry

__all__ = ["ConsulAdapter", "MemoryRegistry"]
