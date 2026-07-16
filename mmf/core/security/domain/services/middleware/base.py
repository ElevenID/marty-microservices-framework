"""
Base Middleware Interface

Defines the contract for security middleware components.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseMiddleware(ABC):
    """Base class for security middleware."""

    @abstractmethod
    async def process(
        self,
        request_context: dict[str, Any],
        next_middleware: Any = None,
    ) -> dict[str, Any]:
        """
        Process the request.

        Args:
            request_context: The request context.
            next_middleware: The next middleware in the chain (callable).

        Returns:
            The processed request context.
        """
