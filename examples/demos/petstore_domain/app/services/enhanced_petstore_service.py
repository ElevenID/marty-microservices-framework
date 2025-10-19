"""
Enhanced Petstore-Domain Service Implementation

Service Type: business
Features: comprehensive business logic with MMF event streaming, observability, resilience, and security
"""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from marty_msf.framework.event_streaming.core import (
    DomainEvent,
    EventBus,
    EventMetadata,
    EventType,
)
from marty_msf.framework.event_streaming.saga import (
    Saga,
    SagaContext,
    SagaOrchestrator,
    SagaStep,
    StepStatus,
)
from marty_msf.framework.resilience.circuit_breaker import CircuitBreaker
from marty_msf.framework.resilience.retry import RetryPolicy, with_retry
from marty_msf.observability.unified_observability import ObservabilityManager
from marty_msf.security.middleware import AuthenticationMiddleware, RateLimitMiddleware

from .petstore_extended_messaging_service import (
    PetstoreEventType,
    PetstoreExtendedMessagingService,
    PetstoreMessagingPattern,
    create_petstore_extended_messaging_service,
)
from .petstore_resilience_service import (
    PetstoreResilienceManager,
    PetstoreResilientOperations,
)

# MMF imports for enhanced capabilities
try:
    MMF_AVAILABLE = True
except ImportError:
    # Fallback when MMF modules are not available
    MMF_AVAILABLE = False
    print("MMF modules not available, using basic implementation")

# Import the new resilience service
try:
    RESILIENCE_SERVICE_AVAILABLE = True
except ImportError:
    RESILIENCE_SERVICE_AVAILABLE = False
    print("Petstore resilience service not available")

# Import the new extended messaging service
try:
    EXTENDED_MESSAGING_AVAILABLE = True
except ImportError:
    EXTENDED_MESSAGING_AVAILABLE = False
    print("Extended messaging service not available")

logger = logging.getLogger(__name__)


class PetCategory(Enum):
    """Enumeration of pet categories"""
    DOG = "dog"
    CAT = "cat"
    BIRD = "bird"
    FISH = "fish"
    REPTILE = "reptile"
    SMALL_ANIMAL = "small_animal"


class OrderStatus(Enum):
    """Enumeration of order statuses"""
    PENDING = "pending"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PREPARING_FOR_DELIVERY = "preparing_for_delivery"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DeliveryStatus(Enum):
    """Enumeration of delivery statuses"""
    AVAILABLE = "available"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Event Definitions for Cross-Service Workflows
class OrderCreatedEvent(DomainEvent if MMF_AVAILABLE else BaseModel):
    """Event published when an order is created"""
    order_id: str
    customer_id: str
    pet_id: str
    amount: float
    special_instructions: str
    correlation_id: str


class PaymentProcessedEvent(DomainEvent if MMF_AVAILABLE else BaseModel):
    """Event published when payment is processed"""
    order_id: str
    payment_id: str
    amount: float
    status: str
    correlation_id: str


class DeliveryScheduledEvent(DomainEvent if MMF_AVAILABLE else BaseModel):
    """Event published when delivery is scheduled"""
    order_id: str
    delivery_id: str
    estimated_delivery: str
    correlation_id: str


# Saga Implementation for Order Processing Workflow
class PetOrderProcessingSaga(Saga if MMF_AVAILABLE else BaseModel):
    """Saga orchestrating the complete pet order processing workflow"""

    def __init__(self, saga_id: str, correlation_id: str):
        if MMF_AVAILABLE:
            super().__init__(saga_id, correlation_id)
        self.saga_id = saga_id
        self.correlation_id = correlation_id

    async def define_workflow(self, context: dict[str, Any]) -> list:
        """Define the saga workflow steps"""
        if not MMF_AVAILABLE:
            return []

        return [
            SagaStep(
                step_id="create_order",
                name="Create Order",
                action=self._create_order_step,
                compensation=self._cancel_order_step
            ),
            SagaStep(
                step_id="process_payment",
                name="Process Payment",
                action=self._process_payment_step,
                compensation=self._refund_payment_step
            ),
            SagaStep(
                step_id="schedule_delivery",
                name="Schedule Delivery",
                action=self._schedule_delivery_step,
                compensation=self._cancel_delivery_step
            )
        ]

    async def _create_order_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Create order step"""
        logger.info(f"Creating order for correlation_id: {self.correlation_id}")
        # Order creation logic here
        return {"order_id": context.get("order_id"), "status": "created"}

    async def _cancel_order_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Cancel order compensation"""
        logger.info(f"Canceling order for correlation_id: {self.correlation_id}")
        return {"status": "cancelled"}

    async def _process_payment_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Process payment step"""
        logger.info(f"Processing payment for correlation_id: {self.correlation_id}")
        # Payment processing logic here
        return {"payment_id": str(uuid.uuid4()), "status": "processed"}

    async def _refund_payment_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Refund payment compensation"""
        logger.info(f"Refunding payment for correlation_id: {self.correlation_id}")
        return {"status": "refunded"}

    async def _schedule_delivery_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Schedule delivery step"""
        logger.info(f"Scheduling delivery for correlation_id: {self.correlation_id}")
        # Delivery scheduling logic here
        return {"delivery_id": str(uuid.uuid4()), "status": "scheduled"}

    async def _cancel_delivery_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Cancel delivery compensation"""
        logger.info(f"Canceling delivery for correlation_id: {self.correlation_id}")
        return {"status": "cancelled"}


class EnhancedPetstoreDomainService:
    """Enhanced service implementation with MMF capabilities."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the enhanced service."""
        self._initialized = False
        self.config = config or {}
        self.pet_catalog: dict[str, dict[str, Any]] = {}
        self.customers: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.order_counter = 1

        # MMF Components
        self.event_bus = None
        self.saga_orchestrator = None
        self.circuit_breaker = None
        self.observability_manager = None

        # Resilience Components
        self.resilience_manager = None
        self.resilient_operations = None

        # Extended Messaging Components
        self.extended_messaging_service = None

        if MMF_AVAILABLE:
            self._initialize_mmf_components()

        if RESILIENCE_SERVICE_AVAILABLE:
            self._initialize_resilience_components()

        if EXTENDED_MESSAGING_AVAILABLE:
            self._initialize_extended_messaging()

    def _initialize_resilience_components(self):
        """Initialize resilience components"""
        try:
            self.resilience_manager = PetstoreResilienceManager(self.config)
            self.resilient_operations = PetstoreResilientOperations(self.resilience_manager)
            logger.info("Resilience components initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize resilience components: {e}")
            self.resilience_manager = None
            self.resilient_operations = None

    def _initialize_extended_messaging(self):
        """Initialize extended messaging service if available"""
        try:
            # Create extended messaging service with configuration
            messaging_config = self.config.get("extended_messaging", {})
            self.extended_messaging_service = create_petstore_extended_messaging_service(messaging_config)

            logger.info("Extended messaging service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize extended messaging service: {e}")
            self.extended_messaging_service = None

    def _initialize_mmf_components(self):
        """Initialize MMF components if available"""
        try:
            # Event Bus for cross-service communication
            self.event_bus = EventBus()

            # Saga Orchestrator for workflow management
            self.saga_orchestrator = SagaOrchestrator(self.event_bus)

            # Circuit Breaker for resilience
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=60
            )

            # Observability Manager
            self.observability_manager = ObservabilityManager(
                service_name="petstore-domain",
                service_version="1.0.0"
            )

            logger.info("MMF components initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize MMF components: {e}")
            self.event_bus = None
            self.saga_orchestrator = None

    async def initialize(self) -> None:
        """Initialize the service with sample data."""
        if self._initialized:
            return

        await self._init_pet_catalog()
        await self._init_test_customers()

        if self.observability_manager:
            await self.observability_manager.initialize()

        # Start extended messaging service if available
        if self.extended_messaging_service:
            await self.extended_messaging_service.start()

        self._initialized = True
        logger.info("EnhancedPetstoreDomainService initialized successfully")

    async def _init_pet_catalog(self) -> None:
        """Initialize the pet catalog with sample pets"""
        self.pet_catalog = {
            "golden-retriever-001": {
                "id": "golden-retriever-001",
                "name": "Buddy",
                "category": PetCategory.DOG.value,
                "breed": "Golden Retriever",
                "age_months": 8,
                "price": 1200.00,
                "description": "Friendly and energetic Golden Retriever puppy",
                "vaccinated": True,
                "available": True,
                "special_care": False,
                "image_url": "/images/golden-retriever.jpg"
            },
            "persian-cat-002": {
                "id": "persian-cat-002",
                "name": "Princess",
                "category": PetCategory.CAT.value,
                "breed": "Persian Cat",
                "age_months": 12,
                "price": 800.00,
                "description": "Beautiful Persian cat with long fluffy coat",
                "vaccinated": True,
                "available": True,
                "special_care": True,
                "image_url": "/images/persian-cat.jpg"
            },
            "cockatiel-003": {
                "id": "cockatiel-003",
                "name": "Sunny",
                "category": PetCategory.BIRD.value,
                "breed": "Cockatiel",
                "age_months": 6,
                "price": 300.00,
                "description": "Social and intelligent cockatiel with beautiful crest",
                "vaccinated": True,
                "available": True,
                "special_care": False,
                "image_url": "/images/cockatiel.jpg"
            }
        }

    async def _init_test_customers(self) -> None:
        """Initialize test customers"""
        self.customers = {
            "customer-001": {
                "id": "customer-001",
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "phone": "+1-555-0101",
                "address": "123 Pet Lover Lane, Dogtown, ST 12345"
            },
            "customer-002": {
                "id": "customer-002",
                "name": "Bob Smith",
                "email": "bob@example.com",
                "phone": "+1-555-0102",
                "address": "456 Cat Avenue, Kittyville, ST 12346"
            }
        }

    async def get_health(self) -> dict[str, Any]:
        """Get service health with MMF observability integration."""
        try:
            health_status = {
                "status": "healthy",
                "service": "petstore-domain",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "mmf_enabled": MMF_AVAILABLE
            }

            if self.observability_manager:
                # Include detailed health metrics
                health_status.update(await self.observability_manager.get_health_status())

            return health_status
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "petstore-domain",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def browse_pets(
        self,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        correlation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Browse available pets with enhanced observability and caching."""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        logger.info(f"Browsing pets - correlation_id: {correlation_id}")

        try:
            # Apply circuit breaker if available
            if self.circuit_breaker:
                @self.circuit_breaker
                async def _browse_pets_protected():
                    return await self._do_browse_pets(category, max_price, correlation_id)

                result = await _browse_pets_protected()
            else:
                result = await self._do_browse_pets(category, max_price, correlation_id)

            # Emit metrics if observability manager is available
            if self.observability_manager:
                await self.observability_manager.increment_counter(
                    "pets_browsed_total",
                    labels={"category": category or "all"}
                )

            return result

        except Exception as e:
            logger.error(f"Error browsing pets - correlation_id: {correlation_id}, error: {e}")
            if self.observability_manager:
                await self.observability_manager.increment_counter("pets_browse_errors_total")
            raise HTTPException(status_code=500, detail=f"Failed to browse pets: {str(e)}")

    async def browse_pets_with_extended_messaging(
        self,
        category: str | None = None,
        max_price: float | None = None,
        correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Browse pets using extended messaging patterns for cross-service queries."""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        logger.info(f"Browsing pets with extended messaging - correlation_id: {correlation_id}")

        try:
            # If extended messaging is available, use request/response pattern
            if self.extended_messaging_service:
                # Query inventory status from external service
                inventory_data = await self.extended_messaging_service.query_inventory_status("all")

                if inventory_data:
                    logger.info(f"Retrieved inventory data via extended messaging: {len(inventory_data.get('pets', []))} pets")
                else:
                    logger.warning("No inventory data received from extended messaging, using local catalog")

            # Fall back to local browsing
            result = await self._do_browse_pets(category, max_price, correlation_id)

            # Publish analytics event using streaming pattern
            if self.extended_messaging_service:
                await self.extended_messaging_service.publish_order_event(
                    PetstoreEventType.PET_ADDED,  # Using existing enum, would be better to have PET_BROWSED
                    {
                        "action": "browse_pets",
                        "category": category,
                        "max_price": max_price,
                        "result_count": len(result.get("pets", [])),
                        "correlation_id": correlation_id
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error browsing pets with extended messaging - correlation_id: {correlation_id}, error: {e}")
            raise HTTPException(status_code=500, detail=f"Error browsing pets: {str(e)}")

    async def _do_browse_pets(
        self,
        category: Optional[str],
        max_price: Optional[float],
        correlation_id: str
    ) -> dict[str, Any]:
        """Internal implementation of pet browsing."""
        available_pets = []

        for pet in self.pet_catalog.values():
            if not pet["available"]:
                continue

            if category and pet["category"] != category:
                continue

            if max_price and pet["price"] > max_price:
                continue

            available_pets.append(pet)

        return {
            "pets": available_pets,
            "total_count": len(available_pets),
            "category_filter": category,
            "max_price_filter": max_price,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def create_order_saga(
        self,
        customer_id: str,
        pet_id: str,
        special_instructions: str = "",
        correlation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Create order using saga pattern for workflow orchestration."""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        logger.info(f"Starting order saga - correlation_id: {correlation_id}")

        try:
            # Validate inputs
            if customer_id not in self.customers:
                raise HTTPException(status_code=404, detail="Customer not found")

            if pet_id not in self.pet_catalog:
                raise HTTPException(status_code=404, detail="Pet not found")

            pet = self.pet_catalog[pet_id]
            if not pet["available"]:
                raise HTTPException(status_code=400, detail="Pet is not available")

            # Create saga context
            order_id = f"order-{self.order_counter:06d}"
            self.order_counter += 1

            saga_context = {
                "order_id": order_id,
                "customer_id": customer_id,
                "pet_id": pet_id,
                "amount": pet["price"],
                "special_instructions": special_instructions,
                "correlation_id": correlation_id
            }

            if self.saga_orchestrator and MMF_AVAILABLE:
                # Use MMF saga orchestrator
                saga = PetOrderProcessingSaga(
                    saga_id=str(uuid.uuid4()),
                    correlation_id=correlation_id
                )

                result = await self.saga_orchestrator.execute_saga(saga, saga_context)

                # Publish order created event
                if self.event_bus:
                    event = OrderCreatedEvent(
                        metadata=EventMetadata(
                            correlation_id=correlation_id,
                            source_service="petstore-domain"
                        ),
                        order_id=order_id,
                        customer_id=customer_id,
                        pet_id=pet_id,
                        amount=pet["price"],
                        special_instructions=special_instructions,
                        correlation_id=correlation_id
                    )
                    await self.event_bus.publish(event)

                return result
            else:
                # Fallback to direct implementation
                return await self._create_order_direct(saga_context)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating order saga - correlation_id: {correlation_id}, error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

    async def _create_order_direct(self, context: dict[str, Any]) -> dict[str, Any]:
        """Direct order creation fallback."""
        order_id = context["order_id"]

        # Create order record
        order = {
            "order_id": order_id,
            "customer_id": context["customer_id"],
            "pet_id": context["pet_id"],
            "amount": context["amount"],
            "special_instructions": context["special_instructions"],
            "status": OrderStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
            "correlation_id": context["correlation_id"]
        }

        self.orders[order_id] = order

        # Mark pet as unavailable
        self.pet_catalog[context["pet_id"]]["available"] = False

        # Use extended messaging for order events if available
        if self.extended_messaging_service:
            try:
                # Start order processing saga using extended messaging
                saga_id = await self.extended_messaging_service.start_order_processing_saga({
                    "order_id": order_id,
                    "customer_id": context["customer_id"],
                    "pet_id": context["pet_id"],
                    "total_amount": context["amount"],
                    "shipping_address": context.get("shipping_address", "TBD")
                })

                # Publish order created event
                await self.extended_messaging_service.publish_order_event(
                    PetstoreEventType.ORDER_CREATED,
                    order
                )

                # Update inventory through extended messaging
                await self.extended_messaging_service.handle_inventory_update({
                    "pet_id": context["pet_id"],
                    "available": False,
                    "reserved_for_order": order_id
                })

                # Send customer notification
                await self.extended_messaging_service.notify_customer(
                    context["customer_id"],
                    {
                        "type": "order_confirmation",
                        "message": f"Your order {order_id} has been created and is being processed",
                        "channels": ["email"]
                    }
                )

                logger.info(f"Extended messaging used for order {order_id}, saga: {saga_id}")

            except Exception as e:
                logger.error(f"Extended messaging failed for order {order_id}: {e}")
                # Continue with fallback processing

        return {
            "message": "Order created successfully",
            "order": order,
            "correlation_id": context["correlation_id"]
        }

    async def get_order_status(
        self,
        order_id: str,
        correlation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Get order status with correlation tracking."""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        logger.info(f"Getting order status - order_id: {order_id}, correlation_id: {correlation_id}")

        if order_id not in self.orders:
            raise HTTPException(status_code=404, detail="Order not found")

        order = self.orders[order_id]

        # Add workflow tracking information
        workflow_status = {
            "order_details": order,
            "workflow_steps": [
                {
                    "step": "order_created",
                    "status": "completed",
                    "timestamp": order["created_at"]
                },
                {
                    "step": "payment_processing",
                    "status": "completed" if order["status"] in [
                        OrderStatus.PAYMENT_CONFIRMED.value,
                        OrderStatus.PREPARING_FOR_DELIVERY.value,
                        OrderStatus.OUT_FOR_DELIVERY.value,
                        OrderStatus.DELIVERED.value
                    ] else "pending",
                    "timestamp": order.get("payment_processed_at")
                },
                {
                    "step": "delivery_scheduled",
                    "status": "completed" if order["status"] in [
                        OrderStatus.OUT_FOR_DELIVERY.value,
                        OrderStatus.DELIVERED.value
                    ] else "pending",
                    "timestamp": order.get("delivery_scheduled_at")
                }
            ],
            "correlation_id": correlation_id
        }

        return workflow_status

    async def get_service_status(self) -> dict[str, Any]:
        """Get comprehensive service status including MMF components."""
        status = {
            "service": "petstore-domain",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "mmf_enabled": MMF_AVAILABLE,
            "initialized": self._initialized,
            "catalog_size": len(self.pet_catalog),
            "customer_count": len(self.customers),
            "order_count": len(self.orders)
        }

        if MMF_AVAILABLE and self.observability_manager:
            try:
                mmf_status = await self.observability_manager.get_service_metrics()
                status.update({"mmf_metrics": mmf_status})
            except Exception as e:
                status["mmf_error"] = str(e)

        return status

    async def process_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process a generic service request with correlation tracking."""
        correlation_id = data.get("correlation_id", str(uuid.uuid4()))

        logger.info(f"Processing request - correlation_id: {correlation_id}")

        try:
            # Process the request
            result = {
                "message": "Request processed successfully",
                "data": data,
                "service": "petstore-domain-enhanced",
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "mmf_enabled": MMF_AVAILABLE
            }

            # Emit processing metrics
            if self.observability_manager:
                await self.observability_manager.increment_counter("requests_processed_total")

            return result

        except Exception as e:
            logger.error(f"Error processing request - correlation_id: {correlation_id}, error: {e}")
            if self.observability_manager:
                await self.observability_manager.increment_counter("request_errors_total")
            raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

    # === RESILIENT OPERATIONS ===

    async def get_resilience_health(self) -> dict[str, Any]:
        """Get comprehensive resilience health status."""
        if not self.resilience_manager:
            return {
                "status": "resilience_framework_unavailable",
                "message": "Resilience framework not initialized"
            }

        return await self.resilience_manager.get_resilience_health()

    async def create_order_with_resilience(
        self,
        customer_id: str,
        pet_id: str,
        payment_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Create a pet order using the full resilience framework.

        This demonstrates the comprehensive business transaction with
        bulkheads, timeouts, circuit breakers, and external dependency management.
        """
        if not self.resilient_operations:
            raise HTTPException(
                status_code=503,
                detail="Resilience framework not available"
            )

        logger.info(f"Creating resilient order for customer {customer_id}, pet {pet_id}")

        try:
            result = await self.resilient_operations.complete_pet_order_with_recommendations(
                customer_id=customer_id,
                pet_id=pet_id,
                payment_data=payment_data
            )

            # Update our local state if order was successful
            if result.get("status") == "completed":
                order_id = result.get("order_id")
                if order_id:
                    self.orders[order_id] = {
                        "order_id": order_id,
                        "customer_id": customer_id,
                        "pet_id": pet_id,
                        "amount": result.get("pet_data", {}).get("price", 0),
                        "status": "completed",
                        "created_at": datetime.utcnow().isoformat(),
                        "resilience_demo": True,
                        "steps_completed": result.get("steps_completed", []),
                    }

            return result

        except Exception as e:
            logger.error(f"Resilient order creation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Order creation failed: {str(e)}"
            )

    async def get_pet_with_cache_and_recommendations(
        self,
        pet_id: str,
        customer_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get pet details with caching and ML recommendations using resilience patterns.
        """
        if not self.resilient_operations:
            raise HTTPException(
                status_code=503,
                detail="Resilience framework not available"
            )

        result = {
            "pet_id": pet_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Get pet from database with resilience
            pet_data = await self.resilient_operations.get_pet_from_database(pet_id)
            if not pet_data:
                raise HTTPException(status_code=404, detail=f"Pet {pet_id} not found")

            result["pet_data"] = pet_data

            # Check cache for catalog
            catalog_data = await self.resilient_operations.get_pet_catalog_from_cache(
                pet_data.get("category", "unknown")
            )
            result["catalog_cached"] = catalog_data is not None
            if catalog_data:
                result["related_pets"] = catalog_data.get("pets", [])

            # Get ML recommendations if customer provided
            if customer_id:
                try:
                    recommendations = await self.resilient_operations.get_pet_recommendation_external({
                        "customer_id": customer_id,
                        "current_pet": pet_data,
                    })
                    result["ml_recommendations"] = recommendations
                except Exception as e:
                    logger.warning(f"ML recommendations failed: {e}")
                    result["ml_recommendations_error"] = str(e)

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting pet with resilience: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get pet details: {str(e)}"
            )

    async def simulate_resilience_scenarios(self) -> dict[str, Any]:
        """
        Simulate various resilience scenarios for demonstration.
        """
        if not self.resilient_operations:
            raise HTTPException(
                status_code=503,
                detail="Resilience framework not available"
            )

        scenarios = {}

        # Scenario 1: Normal operation
        try:
            normal_result = await self.resilient_operations.get_pet_from_database("demo_pet_1")
            scenarios["normal_operation"] = {
                "status": "success",
                "result": normal_result
            }
        except Exception as e:
            scenarios["normal_operation"] = {
                "status": "failed",
                "error": str(e)
            }

        # Scenario 2: Error handling (this pet ID triggers an error)
        try:
            error_result = await self.resilient_operations.get_pet_from_database("error_pet")
            scenarios["error_handling"] = {
                "status": "unexpected_success",
                "result": error_result
            }
        except Exception as e:
            scenarios["error_handling"] = {
                "status": "error_handled",
                "error": str(e)
            }

        # Scenario 3: High load simulation
        try:
            # Simulate multiple concurrent requests to test bulkheads
            tasks = []
            for i in range(10):
                task = self.resilient_operations.get_pet_from_database(f"load_test_pet_{i}")
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_requests = sum(1 for r in results if not isinstance(r, Exception))
            scenarios["high_load_test"] = {
                "status": "completed",
                "total_requests": len(tasks),
                "successful_requests": successful_requests,
                "failed_requests": len(tasks) - successful_requests
            }
        except Exception as e:
            scenarios["high_load_test"] = {
                "status": "failed",
                "error": str(e)
            }

        # Scenario 4: Payment processing with high amount (should fail)
        try:
            payment_result = await self.resilient_operations.process_payment_external({
                "customer_id": "demo_customer",
                "amount": 15000  # This should trigger an error
            })
            scenarios["payment_error_test"] = {
                "status": "unexpected_success",
                "result": payment_result
            }
        except Exception as e:
            scenarios["payment_error_test"] = {
                "status": "error_handled",
                "error": str(e)
            }

        # Get current health status
        health_status = await self.get_resilience_health()

        return {
            "test_scenarios": scenarios,
            "resilience_health": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "demo_mode": True
        }
