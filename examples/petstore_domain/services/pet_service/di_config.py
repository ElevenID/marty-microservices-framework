"""Dependency Injection configuration for Pet Service.

This module wires all dependencies following the Hexagonal Architecture pattern,
using the framework's BaseDIContainer for consistent lifecycle management.
"""

import logging
import os

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.application.use_cases.create_pet import (
    CreatePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.delete_pet import (
    DeletePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.get_pet import (
    GetPetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.list_pets import (
    ListPetsUseCase,
)
from examples.petstore_domain.services.pet_service.infrastructure.adapters.output.in_memory_repository import (
    InMemoryPetRepository,
)
from examples.petstore_domain.services.pet_service.infrastructure.adapters.output.postgres_repository import (
    PostgresPetRepository,
)
from examples.petstore_domain.services.pet_service.infrastructure.metrics import (
    PetMetrics,
    get_pet_metrics,
)
from mmf.core.di import BaseDIContainer
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus, KafkaConfig

logger = logging.getLogger(__name__)


class PetServiceDIContainer(BaseDIContainer):
    """Dependency injection container for Pet Service.

    This container wires all pet service dependencies following the
    Hexagonal Architecture pattern. It manages:
    - Infrastructure adapters (repositories)
    - Application use cases (CRUD operations)
    - Lifecycle management (initialization and cleanup)

    Example:
        ```python
        container = PetServiceDIContainer()
        container.initialize()

        # Use container to get components
        create_use_case = container.create_pet_use_case

        # Cleanup on shutdown
        container.cleanup()
        ```
    """

    def __init__(self) -> None:
        """Initialize DI container."""
        super().__init__()

        # Infrastructure (driven adapters - out)
        self._pet_repository: PetRepositoryPort | None = None
        self._event_bus: EnhancedEventBus | None = None
        self._metrics: PetMetrics | None = None

        # Application (use cases)
        self._create_pet_use_case: CreatePetUseCase | None = None
        self._get_pet_use_case: GetPetUseCase | None = None
        self._list_pets_use_case: ListPetsUseCase | None = None
        self._delete_pet_use_case: DeletePetUseCase | None = None

    def initialize(self) -> None:
        """Wire all dependencies.

        This method creates all infrastructure adapters and wires them to
        application use cases. Must be called once after __init__.
        """
        logger.info("Initializing Pet Service DI Container")
        # Initialize infrastructure adapters
        db_connection_string = os.getenv("DB_CONNECTION_STRING")
        if db_connection_string:
            logger.info("Using PostgreSQL repository")
            self._pet_repository = PostgresPetRepository(db_connection_string)
        else:
            logger.info("Using In-Memory repository")
            self._pet_repository = InMemoryPetRepository()

        # Initialize event bus
        kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
        kafka_config = KafkaConfig(bootstrap_servers=kafka_bootstrap_servers)
        self._event_bus = EnhancedEventBus(kafka_config=kafka_config)
        # In a real app, we would await self._event_bus.start() here, but initialize is synchronous.
        # We might need an async_initialize method or start it in the main entrypoint.

        # Initialize metrics
        self._metrics = get_pet_metrics()

        # Initialize use cases with their dependencies
        self._create_pet_use_case = CreatePetUseCase(
            pet_repository=self._pet_repository,
            event_bus=self._event_bus,
        )
        self._get_pet_use_case = GetPetUseCase(
            pet_repository=self._pet_repository,
        )
        self._list_pets_use_case = ListPetsUseCase(
            pet_repository=self._pet_repository,
        )
        self._delete_pet_use_case = DeletePetUseCase(
            pet_repository=self._pet_repository,
        )

        self._mark_initialized()
        logger.info("Pet Service DI Container initialized successfully")

    def cleanup(self) -> None:
        """Release all resources.

        For the in-memory repository, this clears the storage.
        In a production scenario, this would close database connections, etc.
        """
        logger.info("Cleaning up Pet Service DI Container")

        if isinstance(self._pet_repository, InMemoryPetRepository):
            self._pet_repository.clear()

        self._mark_cleanup()
        logger.info("Pet Service DI Container cleanup complete")

    # =========================================================================
    # Repository Properties
    # =========================================================================

    @property
    def pet_repository(self) -> PetRepositoryPort:
        """Get the pet repository adapter.

        Returns:
            The pet repository implementation
        """
        self._ensure_initialized()
        assert self._pet_repository is not None
        return self._pet_repository

    @property
    def event_bus(self) -> EnhancedEventBus:
        """Get the event bus instance.

        Returns:
            The event bus instance
        """
        self._ensure_initialized()
        assert self._event_bus is not None
        return self._event_bus

    # =========================================================================
    # Use Case Properties
    # =========================================================================

    @property
    def create_pet_use_case(self) -> CreatePetUseCase:
        """Get the create pet use case.

        Returns:
            The create pet use case instance
        """
        self._ensure_initialized()
        assert self._create_pet_use_case is not None
        return self._create_pet_use_case

    @property
    def get_pet_use_case(self) -> GetPetUseCase:
        """Get the get pet use case.

        Returns:
            The get pet use case instance
        """
        self._ensure_initialized()
        assert self._get_pet_use_case is not None
        return self._get_pet_use_case

    @property
    def list_pets_use_case(self) -> ListPetsUseCase:
        """Get the list pets use case.

        Returns:
            The list pets use case instance
        """
        self._ensure_initialized()
        assert self._list_pets_use_case is not None
        return self._list_pets_use_case

    @property
    def delete_pet_use_case(self) -> DeletePetUseCase:
        """Get the delete pet use case.

        Returns:
            The delete pet use case instance
        """
        self._ensure_initialized()
        assert self._delete_pet_use_case is not None
        return self._delete_pet_use_case

    @property
    def metrics(self) -> PetMetrics | None:
        """Get the pet metrics instance.

        Returns:
            The pet metrics instance
        """
        self._ensure_initialized()
        return self._metrics
