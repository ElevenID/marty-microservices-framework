"""
Application layer for Morty service.

This layer contains the application's use cases and coordinates between the domain layer
and the external world through ports (interfaces). It implements the business workflows
and orchestrates domain services and entities.

Key principles:
- Defines input ports (interfaces) that external adapters implement
- Defines output ports (interfaces) that infrastructure adapters implement
- Contains use cases that orchestrate domain logic
- Handles cross-cutting concerns like transactions and events
- Depends only on domain interfaces, not infrastructure
"""
