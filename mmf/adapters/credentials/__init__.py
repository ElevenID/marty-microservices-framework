"""
Credential Adapters

This module provides adapters for credential management.
"""

import logging
import os
from enum import Enum

from mmf.adapters.credentials.spruceid import (
    SpruceIDCredentialIssuer,
    SpruceIDCredentialVerifier,
    SpruceIDCredentialWallet,
    SpruceIDKeyManager,
)

# Try to import Multipaz adapters, but don't fail if dependencies are missing
try:
    from mmf.adapters.credentials.multipaz import (
        MultipazCredentialIssuer,
        MultipazCredentialVerifier,
        MultipazCredentialWallet,
        MultipazKeyManager,
    )

    MULTIPAZ_AVAILABLE = True
except ImportError:
    MULTIPAZ_AVAILABLE = False

# Try to import Persistence adapters
try:
    from mmf.adapters.credentials.persistence import (
        SQLAlchemyCredentialWallet,
        SQLAlchemyKeyManager,
    )

    PERSISTENCE_AVAILABLE = True
except ImportError:
    PERSISTENCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class AdapterMode(Enum):
    SPRUCEID = "spruceid"
    MULTIPAZ = "multipaz"


def get_adapter_mode() -> AdapterMode:
    """Get the configured adapter mode."""
    mode = os.getenv("ADAPTER_MODE", "spruceid").lower()
    if mode == "multipaz":
        return AdapterMode.MULTIPAZ
    return AdapterMode.SPRUCEID


def get_storage_mode() -> str:
    """Get the configured storage mode."""
    return os.getenv("STORAGE_MODE", "memory").lower()


# Singleton instances
_key_manager = None
_issuer = None
_wallet = None
_verifier = None


def _initialize_adapters():
    global _key_manager, _issuer, _wallet, _verifier

    if _key_manager is not None:
        return

    mode = get_adapter_mode()
    storage = get_storage_mode()

    logger.info(f"Initializing credential adapters in {mode.value} mode with {storage} storage")

    # 1. Create Core Adapters
    if mode == AdapterMode.MULTIPAZ:
        if not MULTIPAZ_AVAILABLE:
            logger.warning("Multipaz adapters not available, falling back to SpruceID")
            _key_manager = SpruceIDKeyManager()
            _issuer = SpruceIDCredentialIssuer(_key_manager)
            _wallet = SpruceIDCredentialWallet(_key_manager)
            _verifier = SpruceIDCredentialVerifier()
        else:
            _key_manager = MultipazKeyManager()
            _issuer = MultipazCredentialIssuer(_key_manager)
            _wallet = MultipazCredentialWallet(_key_manager)
            _verifier = MultipazCredentialVerifier()
    else:
        _key_manager = SpruceIDKeyManager()
        _issuer = SpruceIDCredentialIssuer(_key_manager)
        _wallet = SpruceIDCredentialWallet(_key_manager)
        _verifier = SpruceIDCredentialVerifier()

    # 2. Wrap with Persistence if enabled
    if storage == "postgres" and PERSISTENCE_AVAILABLE:
        # We need a session factory here. For now, we'll assume the adapter handles session creation
        # or we pass a session. This is a simplification.
        # In a real app, we'd inject a session factory or scoped session.
        # For this demo, we might skip the actual DB connection wiring in this factory
        # and just show the wrapping logic if we had the session.

        # Since we don't have a global session factory ready here, we will log a warning
        # and skip wrapping for now, or we would need to import the DB setup.
        # Let's assume we can't easily wrap without the session context here.
        logger.warning(
            "Postgres storage requested but session factory not available in factory. Using in-memory/delegate storage."
        )
        pass


def get_key_manager():
    _initialize_adapters()
    return _key_manager


def get_issuer():
    _initialize_adapters()
    return _issuer


def get_wallet():
    _initialize_adapters()
    return _wallet


def get_verifier():
    _initialize_adapters()
    return _verifier


__all__ = [
    "AdapterMode",
    "get_key_manager",
    "get_issuer",
    "get_wallet",
    "get_verifier",
]
