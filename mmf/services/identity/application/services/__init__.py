"""
Application layer services for identity management.

This module contains high-level services that orchestrate business logic
and coordinate between different parts of the application.
"""

from .authentication_manager import AuthenticationManager, authentication_manager

__all__ = [
    "AuthenticationManager",
    "authentication_manager",
]
