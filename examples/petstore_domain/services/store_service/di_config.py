"""Dependency Injection configuration for Store Service.

This module wires all dependencies following the Hexagonal Architecture pattern,
using the framework's BaseDIContainer for consistent lifecycle management.
"""

import logging
import os

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.delivery_service import (
    DeliveryServicePort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.use_cases.create_order import (
    CreateOrderUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_catalog import (
    GetCatalogUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_order import (
    GetOrderUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.list_orders import (
    ListOrdersUseCase,
)
from examples.petstore_domain.services.store_service.domain.entities import CatalogItem
from examples.petstore_domain.services.store_service.domain.value_objects import Money
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.http_delivery_service import (
    HttpDeliveryServiceAdapter,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_catalog_repository import (
    InMemoryCatalogRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.postgres_catalog_repository import (
    PostgresCatalogRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.postgres_order_repository import (
    PostgresOrderRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.metrics import (
    StoreMetrics,
    get_store_metrics,
)
from mmf.core.di import BaseDIContainer
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus, KafkaConfig

logger = logging.getLogger(__name__)


# Initial catalog data
INITIAL_CATALOG = [
    CatalogItem(
        pet_id="corgi",
        name="Pembroke Welsh Corgi",
        species="dog",
        price=Money.from_float(1200.0),
        quantity=4,
        delivery_lead_days=1,
    ),
    CatalogItem(
        pet_id="siamese-cat",
        name="Siamese Cat",
        species="cat",
        price=Money.from_float(800.0),
        quantity=6,
        delivery_lead_days=1,
    ),
    CatalogItem(
        pet_id="macaw",
        name="Blue and Gold Macaw",
        species="bird",
        price=Money.from_float(2500.0),
        quantity=2,
        delivery_lead_days=2,
    ),
]


class StoreServiceDIContainer(BaseDIContainer):
    """Dependency injection container for Store Service.

    This container wires all store service dependencies following the
    Hexagonal Architecture pattern.
    """

    def __init__(self) -> None:
        """Initialize DI container."""
        super().__init__()

        # Infrastructure (driven adapters - out)
        self._catalog_repository: CatalogRepositoryPort | None = None
        self._order_repository: OrderRepositoryPort | None = None
        self._delivery_service: DeliveryServicePort | None = None
        self._event_bus: EnhancedEventBus | None = None
        self._metrics: StoreMetrics | None = None

        # Application (use cases)
        self._create_order_use_case: CreateOrderUseCase | None = None
        self._get_order_use_case: GetOrderUseCase | None = None
        self._list_orders_use_case: ListOrdersUseCase | None = None
        self._get_catalog_use_case: GetCatalogUseCase | None = None

    def initialize(self) -> None:
        """Wire all dependencies."""
        logger.info("Initializing Store Service DI Container")

        # Initialize infrastructure adapters
        db_connection_string = os.getenv("DB_CONNECTION_STRING")
        if db_connection_string:
            logger.info("Using PostgreSQL repositories")
            self._catalog_repository = PostgresCatalogRepository(db_connection_string)
            self._order_repository = PostgresOrderRepository(db_connection_string)
        else:
            logger.info("Using In-Memory repositories")
            self._catalog_repository = InMemoryCatalogRepository()
            self._order_repository = InMemoryOrderRepository()

        self._delivery_service = HttpDeliveryServiceAdapter()

        # Initialize event bus
        kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
        kafka_config = KafkaConfig(bootstrap_servers=kafka_bootstrap_servers)
        self._event_bus = EnhancedEventBus(kafka_config=kafka_config)

        # Initialize metrics
        self._metrics = get_store_metrics()

        # Seed initial catalog data
        for item in INITIAL_CATALOG:
            self._catalog_repository.save(item)

        # Initialize use cases with their dependencies
        self._create_order_use_case = CreateOrderUseCase(
            catalog_repository=self._catalog_repository,
            order_repository=self._order_repository,
            event_bus=self._event_bus,
        )
        self._get_order_use_case = GetOrderUseCase(
            order_repository=self._order_repository,
        )
        self._list_orders_use_case = ListOrdersUseCase(
            order_repository=self._order_repository,
        )
        self._get_catalog_use_case = GetCatalogUseCase(
            catalog_repository=self._catalog_repository,
        )

        self._mark_initialized()
        logger.info("Store Service DI Container initialized successfully")

    def cleanup(self) -> None:
        """Release all resources."""
        logger.info("Cleaning up Store Service DI Container")

        if isinstance(self._catalog_repository, InMemoryCatalogRepository):
            self._catalog_repository.clear()
        if isinstance(self._order_repository, InMemoryOrderRepository):
            self._order_repository.clear()

        self._mark_cleanup()
        logger.info("Store Service DI Container cleanup complete")

    # =========================================================================
    # Repository Properties
    # =========================================================================

    @property
    def catalog_repository(self) -> CatalogRepositoryPort:
        """Get the catalog repository adapter."""
        self._ensure_initialized()
        assert self._catalog_repository is not None
        return self._catalog_repository

    @property
    def order_repository(self) -> OrderRepositoryPort:
        """Get the order repository adapter."""
        self._ensure_initialized()
        assert self._order_repository is not None
        return self._order_repository

    @property
    def delivery_service(self) -> DeliveryServicePort:
        """Get the delivery service adapter."""
        self._ensure_initialized()
        assert self._delivery_service is not None
        return self._delivery_service

    @property
    def event_bus(self) -> EnhancedEventBus:
        """Get the event bus instance."""
        self._ensure_initialized()
        assert self._event_bus is not None
        return self._event_bus

    # =========================================================================
    # Use Case Properties
    # =========================================================================

    @property
    def create_order_use_case(self) -> CreateOrderUseCase:
        """Get the create order use case."""
        self._ensure_initialized()
        assert self._create_order_use_case is not None
        return self._create_order_use_case

    @property
    def get_order_use_case(self) -> GetOrderUseCase:
        """Get the get order use case."""
        self._ensure_initialized()
        assert self._get_order_use_case is not None
        return self._get_order_use_case

    @property
    def list_orders_use_case(self) -> ListOrdersUseCase:
        """Get the list orders use case."""
        self._ensure_initialized()
        assert self._list_orders_use_case is not None
        return self._list_orders_use_case

    @property
    def get_catalog_use_case(self) -> GetCatalogUseCase:
        """Get the get catalog use case."""
        self._ensure_initialized()
        assert self._get_catalog_use_case is not None
        return self._get_catalog_use_case

    @property
    def metrics(self) -> StoreMetrics | None:
        """Get the store metrics instance.

        Returns:
            The store metrics instance
        """
        self._ensure_initialized()
        return self._metrics
