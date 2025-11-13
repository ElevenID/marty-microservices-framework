"""
Service module initialization for Morty service.

This file makes the service discoverable by the hexagonal factory.
"""

# Make submodules available for dynamic import
from . import application, domain, infrastructure

__all__ = ["application", "domain", "infrastructure"]
