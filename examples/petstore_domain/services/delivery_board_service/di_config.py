"""Dependency Injection configuration for Delivery Board Service.

This module wires all dependencies following the Hexagonal Architecture pattern,
using the framework's BaseDIContainer for consistent lifecycle management.
"""

import logging
import os

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.cancel_delivery import (
    CancelDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.complete_delivery import (
    CompleteDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.create_delivery import (
    CreateDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.get_delivery import (
    GetDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.list_deliveries import (
    ListDeliveriesUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.list_trucks import (
    ListTrucksUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.update_truck import (
    UpdateTruckUseCase,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_delivery_repository import (
    InMemoryDeliveryRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_truck_repository import (
    InMemoryTruckRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.postgres_delivery_repository import (
    PostgresDeliveryRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.postgres_truck_repository import (
    PostgresTruckRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.metrics import (
    DeliveryMetrics,
    get_delivery_metrics,
)
from mmf.core.di import BaseDIContainer
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus, KafkaConfig

logger = logging.getLogger(__name__)


# Initial fleet data
INITIAL_TRUCKS = [
    Truck(
        id=TruckId(value="truck-1"),
        name="North Loop",
        capacity=4,
        region="north",
    ),
    Truck(
        id=TruckId(value="truck-2"),
        name="City Center",
        capacity=3,
        region="central",
    ),
]


class DeliveryBoardDIContainer(BaseDIContainer):
    """Dependency injection container for Delivery Board Service.

    This container wires all delivery board service dependencies following
    the Hexagonal Architecture pattern.
    """

    def __init__(self) -> None:
        """Initialize DI container."""
        super().__init__()

        # Infrastructure (driven adapters - out)
        self._delivery_repository: DeliveryRepositoryPort | None = None
        self._truck_repository: TruckRepositoryPort | None = None
        self._event_bus: EnhancedEventBus | None = None
        self._metrics: DeliveryMetrics | None = None

        # Application (use cases)
        self._create_delivery_use_case: CreateDeliveryUseCase | None = None
        self._cancel_delivery_use_case: CancelDeliveryUseCase | None = None
        self._get_delivery_use_case: GetDeliveryUseCase | None = None
        self._list_deliveries_use_case: ListDeliveriesUseCase | None = None
        self._complete_delivery_use_case: CompleteDeliveryUseCase | None = None
        self._list_trucks_use_case: ListTrucksUseCase | None = None
        self._update_truck_use_case: UpdateTruckUseCase | None = None

    def initialize(self) -> None:
        """Wire all dependencies."""
        logger.info("Initializing Delivery Board DI Container")

        # Initialize infrastructure adapters
        db_connection_string = os.getenv("DB_CONNECTION_STRING")
        if db_connection_string:
            logger.info("Using PostgreSQL repositories")
            self._delivery_repository = PostgresDeliveryRepository(db_connection_string)
            self._truck_repository = PostgresTruckRepository(db_connection_string)
        else:
            logger.info("Using In-Memory repositories")
            self._delivery_repository = InMemoryDeliveryRepository()
            self._truck_repository = InMemoryTruckRepository()

        # Initialize event bus
        kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
        kafka_config = KafkaConfig(bootstrap_servers=kafka_bootstrap_servers)
        self._event_bus = EnhancedEventBus(kafka_config=kafka_config)

        # Initialize metrics
        self._metrics = get_delivery_metrics()

        # Seed initial fleet data
        for truck in INITIAL_TRUCKS:
            self._truck_repository.save(truck)

        # Initialize use cases with their dependencies
        self._create_delivery_use_case = CreateDeliveryUseCase(
            delivery_repository=self._delivery_repository,
            truck_repository=self._truck_repository,
            event_bus=self._event_bus,
            metrics=self._metrics,
        )
        self._cancel_delivery_use_case = CancelDeliveryUseCase(
            delivery_repository=self._delivery_repository,
            truck_repository=self._truck_repository,
            event_bus=self._event_bus,
        )
        self._get_delivery_use_case = GetDeliveryUseCase(
            delivery_repository=self._delivery_repository,
        )
        self._list_deliveries_use_case = ListDeliveriesUseCase(
            delivery_repository=self._delivery_repository,
        )
        self._complete_delivery_use_case = CompleteDeliveryUseCase(
            delivery_repository=self._delivery_repository,
            truck_repository=self._truck_repository,
        )
        self._list_trucks_use_case = ListTrucksUseCase(
            truck_repository=self._truck_repository,
        )
        self._update_truck_use_case = UpdateTruckUseCase(
            truck_repository=self._truck_repository,
        )

        self._mark_initialized()
        logger.info("Delivery Board DI Container initialized successfully")

    def cleanup(self) -> None:
        """Release all resources."""
        logger.info("Cleaning up Delivery Board DI Container")

        if isinstance(self._delivery_repository, InMemoryDeliveryRepository):
            self._delivery_repository.clear()
        if isinstance(self._truck_repository, InMemoryTruckRepository):
            self._truck_repository.clear()

        self._mark_cleanup()
        logger.info("Delivery Board DI Container cleanup complete")

    # =========================================================================
    # Repository Properties
    # =========================================================================

    @property
    def delivery_repository(self) -> DeliveryRepositoryPort:
        """Get the delivery repository adapter."""
        self._ensure_initialized()
        assert self._delivery_repository is not None
        return self._delivery_repository

    @property
    def truck_repository(self) -> TruckRepositoryPort:
        """Get the truck repository adapter."""
        self._ensure_initialized()
        assert self._truck_repository is not None
        return self._truck_repository

    # =========================================================================
    # Use Case Properties
    # =========================================================================

    @property
    def event_bus(self) -> EnhancedEventBus:
        """Get the event bus instance."""
        self._ensure_initialized()
        assert self._event_bus is not None
        return self._event_bus

    @property
    def create_delivery_use_case(self) -> CreateDeliveryUseCase:
        """Get the create delivery use case."""
        self._ensure_initialized()
        assert self._create_delivery_use_case is not None
        return self._create_delivery_use_case

    @property
    def get_delivery_use_case(self) -> GetDeliveryUseCase:
        """Get the get delivery use case."""
        self._ensure_initialized()
        assert self._get_delivery_use_case is not None
        return self._get_delivery_use_case

    @property
    def list_deliveries_use_case(self) -> ListDeliveriesUseCase:
        """Get the list deliveries use case."""
        self._ensure_initialized()
        assert self._list_deliveries_use_case is not None
        return self._list_deliveries_use_case

    @property
    def complete_delivery_use_case(self) -> CompleteDeliveryUseCase:
        """Get the complete delivery use case."""
        self._ensure_initialized()
        assert self._complete_delivery_use_case is not None
        return self._complete_delivery_use_case

    @property
    def list_trucks_use_case(self) -> ListTrucksUseCase:
        """Get the list trucks use case."""
        self._ensure_initialized()
        assert self._list_trucks_use_case is not None
        return self._list_trucks_use_case

    @property
    def cancel_delivery_use_case(self) -> CancelDeliveryUseCase:
        """Get the cancel delivery use case."""
        self._ensure_initialized()
        assert self._cancel_delivery_use_case is not None
        return self._cancel_delivery_use_case

    @property
    def update_truck_use_case(self) -> UpdateTruckUseCase:
        """Get the update truck use case."""
        self._ensure_initialized()
        assert self._update_truck_use_case is not None
        return self._update_truck_use_case

    @property
    def metrics(self) -> DeliveryMetrics | None:
        """Get the delivery metrics instance."""
        self._ensure_initialized()
        return self._metrics
