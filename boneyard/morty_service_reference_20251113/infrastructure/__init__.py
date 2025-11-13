"""
Infrastructure layer for Morty service.

This layer contains the adapters that implement the ports defined in the application layer.
It handles external concerns like HTTP/gRPC APIs, databases, message queues, and third-party services.

Key principles:
- Implements the output ports defined in the application layer
- Provides concrete implementations for external dependencies
- Handles technical concerns like serialization, networking, persistence
- Depends on application abstractions, not domain directly
- Can depend on external frameworks and libraries
"""
