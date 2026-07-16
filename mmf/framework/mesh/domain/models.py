"""
Mesh Domain Models.
"""

import builtins
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteMatch:
    """Route matching criteria."""

    headers: builtins.dict[str, str] = field(default_factory=dict)
    path_prefix: str = ""
    path_exact: str = ""
    path_regex: str = ""
    method: str = ""
    query_params: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class RouteDestination:
    """Route destination configuration."""

    service_name: str
    weight: int = 100
    headers_to_add: builtins.dict[str, str] = field(default_factory=dict)
    headers_to_remove: builtins.list[str] = field(default_factory=list)


@dataclass
class TrafficRule:
    """Traffic routing rule."""

    rule_id: str
    service_name: str
    match_conditions: builtins.list[builtins.dict[str, Any]]
    destination_rules: builtins.list[builtins.dict[str, Any]]
    weight: int = 100
    timeout_seconds: int = 30
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)
