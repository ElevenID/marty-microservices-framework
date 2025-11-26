"""
Event Sourcing Module

This module provides event sourcing capabilities including event stores,
aggregate roots, and event stream management.
"""

from .core import AggregateRoot, EventStore, InMemoryEventStore

__all__ = ["AggregateRoot", "EventStore", "InMemoryEventStore"]
