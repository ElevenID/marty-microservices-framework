"""
Trust Store Configuration

This module defines configuration models for the trust store and PKD (Public Key Directory).
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PKDConfig:
    """Public Key Directory configuration."""

    service_url: str = ""
    enabled: bool = True
    update_interval_hours: int = 24
    max_retries: int = 3
    timeout_seconds: int = 30

    def __post_init__(self):
        if self.update_interval_hours <= 0:
            raise ValueError("PKD update interval must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("PKD timeout must be positive")


@dataclass
class TrustAnchorConfig:
    """Trust Anchor configuration."""

    certificate_store_path: str = "/app/data/trust"
    update_interval_hours: int = 24
    validation_timeout_seconds: int = 30
    enable_online_verification: bool = False

    def __post_init__(self):
        if self.update_interval_hours <= 0:
            raise ValueError("Trust anchor update interval must be positive")


@dataclass
class TrustStoreConfig:
    """Trust store and PKD configuration."""

    pkd: PKDConfig = field(default_factory=PKDConfig)
    trust_anchor: TrustAnchorConfig = field(default_factory=TrustAnchorConfig)

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> TrustStoreConfig:
        pkd_data = data.get("pkd", {})
        pkd = PKDConfig(
            service_url=pkd_data.get("service_url", ""),
            enabled=pkd_data.get("enabled", True),
            update_interval_hours=pkd_data.get("update_interval_hours", 24),
            max_retries=pkd_data.get("max_retries", 3),
            timeout_seconds=pkd_data.get("timeout_seconds", 30),
        )

        trust_data = data.get("trust_anchor", {})
        trust_anchor = TrustAnchorConfig(
            certificate_store_path=trust_data.get("certificate_store_path", "/app/data/trust"),
            update_interval_hours=trust_data.get("update_interval_hours", 24),
            validation_timeout_seconds=trust_data.get("validation_timeout_seconds", 30),
            enable_online_verification=trust_data.get("enable_online_verification", False),
        )

        return cls(pkd=pkd, trust_anchor=trust_anchor)
