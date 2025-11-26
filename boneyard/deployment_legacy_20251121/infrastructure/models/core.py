"""
Core data models for infrastructure deployment.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from marty_msf.framework.deployment.core import EnvironmentType

from .enums import CloudProvider, IaCProvider, ResourceType


@dataclass
class IaCConfig:
    """Infrastructure as Code configuration."""

    provider: IaCProvider
    cloud_provider: CloudProvider
    project_name: str
    environment: EnvironmentType
    region: str = "us-east-1"
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    backend_config: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.list[str] = field(default_factory=list)
    dependencies: builtins.list[str] = field(default_factory=list)


@dataclass
class ResourceConfig:
    """Infrastructure resource configuration."""

    name: str
    type: ResourceType
    provider: CloudProvider
    properties: builtins.dict[str, Any] = field(default_factory=dict)
    dependencies: builtins.list[str] = field(default_factory=list)
    tags: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class InfrastructureStack:
    """Infrastructure stack definition."""

    name: str
    config: IaCConfig
    resources: builtins.list[ResourceConfig] = field(default_factory=list)
    modules: builtins.list[str] = field(default_factory=list)
    data_sources: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)


@dataclass
class InfrastructureState:
    """Infrastructure state information."""

    stack_name: str
    status: str
    resources: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.dict[str, Any] = field(default_factory=dict)
    last_updated: datetime | None = None
    version: str | None = None
