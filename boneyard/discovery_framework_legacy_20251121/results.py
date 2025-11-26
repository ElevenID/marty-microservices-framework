from __future__ import annotations

"""
Pared-down container objects used across discovery flows.

Separating the result model keeps the client implementations lean and avoids
cyclic imports once the discovery package is broken into focused modules.
"""

import builtins
from dataclasses import dataclass, field
from typing import Any

from .config import ServiceQuery
from .core import ServiceInstance


@dataclass
class DiscoveryResult:
    """Result of a service discovery operation."""

    instances: builtins.list[ServiceInstance]
    query: ServiceQuery
    source: str  # Registry source
    cached: bool = False
    cache_age: float = 0.0
    resolution_time: float = 0.0

    # Selection information
    selected_instance: ServiceInstance | None = None
    load_balancer_used: bool = False

    # Metadata
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
