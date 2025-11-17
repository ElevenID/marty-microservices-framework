"""
Infrastructure layer adapters for authentication providers.

This module exports all infrastructure implementations of authentication
providers that implement the ports defined in the application layer.
"""

from .api_key_adapter import APIKeyAdapter, APIKeyConfig
from .basic_auth_adapter import BasicAuthAdapter, BasicAuthConfig

__all__ = [
    # Basic Authentication
    "BasicAuthAdapter",
    "BasicAuthConfig",
    # API Key Authentication
    "APIKeyAdapter",
    "APIKeyConfig",
]
