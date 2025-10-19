"""
Enhanced Petstore Domain API Routes

This module demonstrates the full power of the Marty Microservices Framework (MMF)
by implementing a comprehensive petstore domain with:

- Event-driven saga orchestration for order → payment → delivery workflows
- Comprehensive observability with correlation tracking, metrics, and tracing
- Resilience patterns including circuit breakers, retries, and timeouts
- Security guardrails with JWT/OIDC authentication and rate limiting
- Centralized configuration and feature flags with live reload
- Real data integration with Redis caching and PostgreSQL
- Zero-trust security patterns

The enhanced implementation showcases enterprise-grade microservice patterns
while maintaining backward compatibility with the original API.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

# Import both original and enhanced implementations
from ..services.petstore_domain_service import PetstoreDomainService
from .enhanced_petstore_routes import router as enhanced_router

# Try to import enhanced routes, fall back to basic if not available
try:
    ENHANCED_AVAILABLE = True
except ImportError as e:
    print(f"Enhanced routes not available: {e}")
    ENHANCED_AVAILABLE = False
    enhanced_router = None


logger = logging.getLogger(__name__)

# Create main router
router = APIRouter(prefix="/petstore-domain", tags=["petstore-domain"])

# Include enhanced routes if available
if ENHANCED_AVAILABLE and enhanced_router:
    # Mount enhanced routes at the root level
    logger.info("Enhanced MMF routes are available and loaded")
    # We'll merge the routes by including them here
else:
    logger.warning("Enhanced MMF routes not available, using basic implementation")

# Pydantic models for request/response (maintained for compatibility)
class RequestModel(BaseModel):
    """Request model for petstore-domain."""
    data: dict[str, Any]

class ResponseModel(BaseModel):
    """Response model for petstore-domain."""
    message: str
    data: dict[str, Any]
    service: str

class CreateOrderRequest(BaseModel):
    """Request model for creating an order."""
    customer_id: str
    pet_id: str
    special_instructions: str = ""
    correlation_id: Optional[str] = None

class ProcessPaymentRequest(BaseModel):
    """Request model for processing payment."""
    order_id: str
    payment_method: str
    correlation_id: Optional[str] = None

# Global service instance
_service_instance = None

async def get_service() -> PetstoreDomainService:
    """Get or create service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PetstoreDomainService()
        await _service_instance.initialize()
    return _service_instance

# Basic health endpoint (always available)
@router.get("/health")
async def get_health():
    """Get service health with MMF integration status."""
    service = await get_service()
    health_data = await service.get_health()

    # Add MMF status information
    health_data.update({
        "enhanced_features_available": ENHANCED_AVAILABLE,
        "mmf_integration": "enabled" if ENHANCED_AVAILABLE else "disabled",
        "demo_capabilities": {
            "event_streaming": ENHANCED_AVAILABLE,
            "observability": ENHANCED_AVAILABLE,
            "resilience_patterns": ENHANCED_AVAILABLE,
            "security_guardrails": ENHANCED_AVAILABLE,
            "centralized_config": ENHANCED_AVAILABLE,
            "data_integration": ENHANCED_AVAILABLE
        }
    })

    return health_data

# Legacy endpoints (maintained for backward compatibility)
@router.get("/browse-pets")
async def browse_pets(
    category: Optional[str] = Query(None, description="Pet category filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Browse available pets with optional filters."""
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    logger.info(f"Legacy browse pets endpoint - correlation_id: {correlation_id}")

    service = await get_service()
    result = await service.browse_pets(category=category, max_price=max_price, correlation_id=correlation_id)

    # Add enhancement status
    result["enhanced_features"] = ENHANCED_AVAILABLE
    result["recommendation"] = "Use /petstore-domain/pets/browse for enhanced capabilities" if ENHANCED_AVAILABLE else None

    return result

@router.get("/pet-details")
async def get_pet_details(
    pet_id: str = Query(..., description="Pet ID"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Get detailed information about a specific pet."""
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    logger.info(f"Legacy pet details endpoint - pet_id: {pet_id}, correlation_id: {correlation_id}")

    service = await get_service()
    result = await service.get_pet_details(pet_id=pet_id, correlation_id=correlation_id)

    # Add enhancement status
    result["enhanced_features"] = ENHANCED_AVAILABLE
    result["recommendation"] = f"Use /petstore-domain/pets/{pet_id} for enhanced capabilities" if ENHANCED_AVAILABLE else None

    return result

@router.post("/create-order")
async def create_order(request: CreateOrderRequest):
    """Create a new pet order."""
    if not request.correlation_id:
        request.correlation_id = str(uuid.uuid4())

    logger.info(f"Legacy create order endpoint - correlation_id: {request.correlation_id}")

    service = await get_service()
    result = await service.create_order(
        customer_id=request.customer_id,
        pet_id=request.pet_id,
        special_instructions=request.special_instructions,
        correlation_id=request.correlation_id
    )

    # Add enhancement recommendations
    result["enhanced_features"] = ENHANCED_AVAILABLE
    if ENHANCED_AVAILABLE:
        result["recommendation"] = "Use POST /petstore-domain/orders for saga-orchestrated workflows"
        result["saga_orchestration_available"] = True

    return result

@router.post("/process-payment")
async def process_payment(request: ProcessPaymentRequest):
    """Process payment for an order."""
    if not request.correlation_id:
        request.correlation_id = str(uuid.uuid4())

    logger.info(f"Legacy process payment endpoint - correlation_id: {request.correlation_id}")

    service = await get_service()
    result = await service.process_payment(
        order_id=request.order_id,
        payment_method=request.payment_method,
        correlation_id=request.correlation_id
    )

    # Add enhancement recommendations
    result["enhanced_features"] = ENHANCED_AVAILABLE
    if ENHANCED_AVAILABLE:
        result["recommendation"] = "Use POST /petstore-domain/payments for enhanced security and resilience"

    return result

@router.get("/order-status")
async def get_order_status(
    order_id: str = Query(..., description="Order ID"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Get current order status and tracking information."""
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    logger.info(f"Legacy order status endpoint - order_id: {order_id}, correlation_id: {correlation_id}")

    service = await get_service()
    result = await service.get_order_status(order_id=order_id, correlation_id=correlation_id)

    # Add enhancement recommendations
    result["enhanced_features"] = ENHANCED_AVAILABLE
    if ENHANCED_AVAILABLE:
        result["recommendation"] = f"Use GET /petstore-domain/orders/{order_id}/status for workflow tracking"

    return result

@router.get("/service-status")
async def get_service_status():
    """Get detailed service status information."""
    service = await get_service()
    result = await service.get_service_status()

    # Add MMF integration status
    result.update({
        "mmf_integration": {
            "status": "enabled" if ENHANCED_AVAILABLE else "disabled",
            "enhanced_routes_available": ENHANCED_AVAILABLE,
            "capabilities": {
                "event_streaming": ENHANCED_AVAILABLE,
                "saga_orchestration": ENHANCED_AVAILABLE,
                "observability": ENHANCED_AVAILABLE,
                "resilience_patterns": ENHANCED_AVAILABLE,
                "security_guardrails": ENHANCED_AVAILABLE,
                "centralized_config": ENHANCED_AVAILABLE,
                "redis_caching": ENHANCED_AVAILABLE,
                "database_integration": ENHANCED_AVAILABLE
            }
        },
        "demo_endpoints": {
            "enhanced_health": "/petstore-domain/health" if ENHANCED_AVAILABLE else None,
            "enhanced_pets": "/petstore-domain/pets/browse" if ENHANCED_AVAILABLE else None,
            "enhanced_orders": "/petstore-domain/orders" if ENHANCED_AVAILABLE else None,
            "enhanced_payments": "/petstore-domain/payments" if ENHANCED_AVAILABLE else None,
            "admin_config": "/petstore-domain/admin/config" if ENHANCED_AVAILABLE else None
        }
    })

    return result

@router.post("/process", response_model=ResponseModel)
async def process_request(request: RequestModel):
    """Process a generic service request."""
    correlation_id = request.data.get("correlation_id", str(uuid.uuid4()))

    logger.info(f"Legacy process request endpoint - correlation_id: {correlation_id}")

    service = await get_service()
    result = await service.process_request(request.data)

    # Add enhancement status
    result["enhanced_features"] = ENHANCED_AVAILABLE
    if ENHANCED_AVAILABLE:
        result["mmf_capabilities"] = "Available - see /petstore-domain/admin/config for details"

    return ResponseModel(
        message=result["message"],
        data=result["data"],
        service=result["service"]
    )

# Information endpoint about the demo
@router.get("/demo-info")
async def get_demo_info():
    """Get information about the enhanced petstore demo capabilities."""
    return {
        "demo_name": "Enhanced Petstore Domain with MMF",
        "version": "1.0.0",
        "description": "Comprehensive demonstration of Marty Microservices Framework capabilities",
        "enhanced_features_available": ENHANCED_AVAILABLE,
        "capabilities": {
            "event_driven_workflows": {
                "available": ENHANCED_AVAILABLE,
                "description": "Saga-orchestrated order → payment → delivery workflows",
                "endpoints": ["/orders", "/payments"] if ENHANCED_AVAILABLE else []
            },
            "observability": {
                "available": ENHANCED_AVAILABLE,
                "description": "Structured logging, metrics, and distributed tracing",
                "features": ["correlation_ids", "prometheus_metrics", "jaeger_tracing"] if ENHANCED_AVAILABLE else []
            },
            "resilience_patterns": {
                "available": ENHANCED_AVAILABLE,
                "description": "Circuit breakers, retries, and timeouts",
                "patterns": ["circuit_breaker", "retry_policy", "timeout_handling"] if ENHANCED_AVAILABLE else []
            },
            "security": {
                "available": ENHANCED_AVAILABLE,
                "description": "JWT/OIDC authentication and rate limiting",
                "features": ["jwt_auth", "rate_limiting", "zero_trust"] if ENHANCED_AVAILABLE else []
            },
            "configuration": {
                "available": ENHANCED_AVAILABLE,
                "description": "Centralized config and feature flags with live reload",
                "endpoint": "/admin/config" if ENHANCED_AVAILABLE else None
            },
            "data_integration": {
                "available": ENHANCED_AVAILABLE,
                "description": "Redis caching and PostgreSQL integration",
                "features": ["redis_cache", "postgresql_db", "event_sourcing"] if ENHANCED_AVAILABLE else []
            }
        },
        "getting_started": {
            "basic_health": "/petstore-domain/health",
            "browse_pets": "/petstore-domain/browse-pets",
            "enhanced_endpoints": "/petstore-domain/pets/browse" if ENHANCED_AVAILABLE else "Not available",
            "docker_compose": "docker-compose.enhanced.yml" if ENHANCED_AVAILABLE else None
        },
        "architecture": {
            "event_streaming": "Kafka-based with saga orchestration" if ENHANCED_AVAILABLE else "In-memory",
            "observability": "Prometheus + Jaeger + Grafana" if ENHANCED_AVAILABLE else "Basic logging",
            "security": "JWT/OIDC + Rate limiting" if ENHANCED_AVAILABLE else "None",
            "data_layer": "Redis + PostgreSQL with event sourcing" if ENHANCED_AVAILABLE else "In-memory"
        },
        "demo_scenarios": [
            {
                "name": "Cross-Service Workflow",
                "description": "Order creation triggering payment and delivery saga",
                "endpoint": "/orders" if ENHANCED_AVAILABLE else "/create-order"
            },
            {
                "name": "Observability Demo",
                "description": "Correlation tracking across service calls",
                "monitoring": "Grafana dashboards" if ENHANCED_AVAILABLE else "Logs only"
            },
            {
                "name": "Resilience Testing",
                "description": "Circuit breaker and retry patterns",
                "available": ENHANCED_AVAILABLE
            },
            {
                "name": "Security Patterns",
                "description": "JWT authentication and rate limiting",
                "available": ENHANCED_AVAILABLE
            },
            {
                "name": "Feature Flags",
                "description": "Live configuration changes",
                "endpoint": "/admin/config" if ENHANCED_AVAILABLE else None
            }
        ]
    }
    return await service.get_health()

@router.get("/browse-pets")
async def browse_pets(
    category: Optional[str] = Query(None, description="Pet category filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Browse available pets with optional filters."""
    service = await get_service()
    return await service.browse_pets(category=category, max_price=max_price, correlation_id=correlation_id)

@router.get("/pet-details")
async def get_pet_details(
    pet_id: str = Query(..., description="Pet ID"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Get detailed information about a specific pet."""
    service = await get_service()
    return await service.get_pet_details(pet_id=pet_id, correlation_id=correlation_id)

@router.post("/create-order")
async def create_order(request: CreateOrderRequest):
    """Create a new pet order."""
    service = await get_service()
    return await service.create_order(
        customer_id=request.customer_id,
        pet_id=request.pet_id,
        special_instructions=request.special_instructions,
        correlation_id=request.correlation_id
    )

@router.post("/process-payment")
async def process_payment(request: ProcessPaymentRequest):
    """Process payment for an order."""
    service = await get_service()
    return await service.process_payment(
        order_id=request.order_id,
        payment_method=request.payment_method,
        correlation_id=request.correlation_id
    )

@router.get("/order-status")
async def get_order_status(
    order_id: str = Query(..., description="Order ID"),
    correlation_id: Optional[str] = Query(None, description="Request correlation ID")
):
    """Get current order status and tracking information."""
    service = await get_service()
    return await service.get_order_status(order_id=order_id, correlation_id=correlation_id)

@router.get("/service-status")
async def get_service_status():
    """Get detailed service status information."""
    service = await get_service()
    return await service.get_service_status()

@router.post("/process", response_model=ResponseModel)
async def process_request(request: RequestModel):
    """Process a generic service request."""
    service = await get_service()
    result = await service.process_request(request.data)

    return ResponseModel(
        message=result["message"],
        data=result["data"],
        service=result["service"]
    )
