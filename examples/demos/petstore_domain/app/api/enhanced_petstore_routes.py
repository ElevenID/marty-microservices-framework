"""
Enhanced Petstore Domain API Routes

Showcases MMF capabilities:
- Event-driven workflows with saga orchestration
- Comprehensive observability with correlation tracking
- Resilience patterns (circuit breakers, retries)
- Security guardrails (JWT/OIDC, rate limiting)
- Centralized configuration and feature flags
- Real data integration (Redis, databases)
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# MMF Framework imports
from marty_msf.framework.cache import cache_result
from marty_msf.framework.config import get_config_value, get_feature_flag
from marty_msf.framework.plugins.decorators import event_handler
from marty_msf.framework.resilience.retry import with_retry
from marty_msf.observability.metrics import track_metrics
from marty_msf.observability.tracing import trace_operation
from marty_msf.security.authentication import requires_auth, verify_jwt_token
from marty_msf.security.rate_limiting import rate_limit

from ..services.enhanced_petstore_service import EnhancedPetstoreDomainService

MMF_AVAILABLE = True

# Import our enhanced service

logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(prefix="/petstore-domain", tags=["petstore-domain-enhanced"])
security = HTTPBearer()

# Enhanced Request/Response Models
class CorrelatedRequest(BaseModel):
    """Base request with correlation tracking"""
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    def get_correlation_id(self) -> str:
        """Get or generate correlation ID"""
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())
        return self.correlation_id

class EnhancedOrderRequest(CorrelatedRequest):
    """Enhanced order request with feature flag support"""
    customer_id: str = Field(..., description="Customer identifier")
    pet_id: str = Field(..., description="Pet identifier")
    special_instructions: str = Field("", description="Special care instructions")
    priority: Optional[str] = Field("normal", description="Order priority level")
    gift_wrapping: Optional[bool] = Field(False, description="Gift wrapping option")

class PaymentRequest(CorrelatedRequest):
    """Payment processing request"""
    order_id: str = Field(..., description="Order identifier")
    payment_method: str = Field(..., description="Payment method")
    amount: Optional[float] = Field(None, description="Payment amount")

class EnhancedResponse(BaseModel):
    """Enhanced response with observability metadata"""
    success: bool
    data: Any
    correlation_id: str
    timestamp: str
    service: str = "petstore-domain-enhanced"
    mmf_enabled: bool = MMF_AVAILABLE

# Global service instance
_service_instance = None

async def get_service() -> EnhancedPetstoreDomainService:
    """Get or create enhanced service instance with dependency injection"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EnhancedPetstoreDomainService()
        await _service_instance.initialize()
    return _service_instance

# Helper functions for MMF integration
async def get_correlation_id(
    correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
) -> str:
    """Extract or generate correlation ID from headers"""
    return correlation_id or str(uuid.uuid4())

async def get_user_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    correlation_id: str = Depends(get_correlation_id)
) -> dict[str, Any]:
    """Extract user context from JWT token with correlation tracking"""
    if not credentials and MMF_AVAILABLE:
        # In demo mode, allow unauthenticated access with warnings
        logger.warning(f"Unauthenticated access - correlation_id: {correlation_id}")
        return {"user_id": "anonymous", "roles": ["guest"], "correlation_id": correlation_id}

    if credentials and MMF_AVAILABLE:
        try:
            user_data = await verify_jwt_token(credentials.credentials)
            user_data["correlation_id"] = correlation_id
            return user_data
        except Exception as e:
            logger.error(f"Authentication failed - correlation_id: {correlation_id}, error: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Fallback for non-MMF environments
    return {"user_id": "demo-user", "roles": ["customer"], "correlation_id": correlation_id}

# Health and Status Endpoints
@router.get("/health")
@trace_operation("health_check")
@track_metrics("health_check_requests")
async def get_health(correlation_id: str = Depends(get_correlation_id)):
    """Enhanced health check with observability integration"""
    logger.info(f"Health check requested - correlation_id: {correlation_id}")

    service = await get_service()
    health_data = await service.get_health()

    return EnhancedResponse(
        success=True,
        data=health_data,
        correlation_id=correlation_id,
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/status")
@trace_operation("service_status")
@requires_auth
async def get_service_status(
    user_context: dict = Depends(get_user_context)
):
    """Get comprehensive service status (authenticated endpoint)"""
    correlation_id = user_context["correlation_id"]
    logger.info(f"Service status requested - correlation_id: {correlation_id}, user: {user_context['user_id']}")

    service = await get_service()
    status_data = await service.get_service_status()

    # Add user context to response
    status_data["requested_by"] = user_context["user_id"]
    status_data["user_roles"] = user_context["roles"]

    return EnhancedResponse(
        success=True,
        data=status_data,
        correlation_id=correlation_id,
        timestamp=datetime.utcnow().isoformat()
    )

# Pet Catalog Endpoints with Caching and Feature Flags
@router.get("/pets/browse")
@trace_operation("browse_pets")
@track_metrics("pet_browsing_requests")
@rate_limit(requests_per_minute=100)
@cache_result(ttl_seconds=300)  # Cache for 5 minutes
async def browse_pets(
    category: Optional[str] = Query(None, description="Pet category filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    include_special_care: Optional[bool] = Query(None, description="Include special care pets"),
    user_context: dict = Depends(get_user_context)
):
    """Browse pets with enhanced filtering and feature flags"""
    correlation_id = user_context["correlation_id"]

    # Check feature flags
    personalization_enabled = await get_feature_flag("pet_personalization", False)
    premium_filters_enabled = await get_feature_flag("premium_filters", True)

    logger.info(
        f"Browsing pets - correlation_id: {correlation_id}, "
        f"category: {category}, max_price: {max_price}, "
        f"personalization: {personalization_enabled}"
    )

    service = await get_service()

    # Apply feature-flag driven logic
    if not premium_filters_enabled and max_price:
        max_price = None  # Disable premium filtering if flag is off

    pets_data = await service.browse_pets(
        category=category,
        max_price=max_price,
        correlation_id=correlation_id
    )

    # Add personalization if enabled
    if personalization_enabled:
        pets_data["personalized"] = True
        pets_data["recommendations"] = ["golden-retriever-001"]  # Mock recommendation

    # Add pricing configuration
    pricing_config = await get_config_value("pricing.display_currency", "USD")
    pets_data["currency"] = pricing_config

    return EnhancedResponse(
        success=True,
        data=pets_data,
        correlation_id=correlation_id,
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/pets/{pet_id}")
@trace_operation("get_pet_details")
@track_metrics("pet_detail_requests")
@cache_result(ttl_seconds=600)  # Cache for 10 minutes
@with_retry(max_attempts=3)
async def get_pet_details(
    pet_id: str,
    user_context: dict = Depends(get_user_context)
):
    """Get detailed pet information with resilience patterns"""
    correlation_id = user_context["correlation_id"]

    logger.info(f"Getting pet details - pet_id: {pet_id}, correlation_id: {correlation_id}")

    service = await get_service()

    try:
        # This will use the circuit breaker and retry logic from the service
        pet_data = await service.get_pet_details(pet_id, correlation_id)

        # Add dynamic pricing based on configuration
        markup_percentage = await get_config_value("pricing.markup_percentage", 0.0)
        if markup_percentage > 0:
            original_price = pet_data.get("price", 0)
            pet_data["promotional_price"] = original_price * (1 + markup_percentage / 100)

        return EnhancedResponse(
            success=True,
            data=pet_data,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pet details - pet_id: {pet_id}, correlation_id: {correlation_id}, error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to retrieve pet details",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__
            }
        )

# Order Management with Saga Orchestration
@router.post("/orders")
@trace_operation("create_order")
@track_metrics("order_creation_requests")
@requires_auth
@rate_limit(requests_per_minute=30)  # Lower rate limit for order creation
async def create_order(
    request: EnhancedOrderRequest,
    user_context: dict = Depends(get_user_context)
):
    """Create order using saga orchestration with comprehensive error handling"""
    correlation_id = request.get_correlation_id()
    user_context["correlation_id"] = correlation_id

    logger.info(
        f"Creating order - customer_id: {request.customer_id}, "
        f"pet_id: {request.pet_id}, correlation_id: {correlation_id}, "
        f"user: {user_context['user_id']}"
    )

    # Check if user can create orders
    if "customer" not in user_context.get("roles", []):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Insufficient permissions to create orders",
                "correlation_id": correlation_id,
                "required_role": "customer"
            }
        )

    service = await get_service()

    try:
        # Check if express processing is enabled
        express_processing = await get_feature_flag("express_order_processing", False)

        if express_processing:
            # Use saga orchestration for complex workflow
            order_data = await service.create_order_saga(
                customer_id=request.customer_id,
                pet_id=request.pet_id,
                special_instructions=request.special_instructions,
                correlation_id=correlation_id
            )
        else:
            # Use direct processing
            order_data = await service._create_order_direct({
                "order_id": f"order-{uuid.uuid4().hex[:8]}",
                "customer_id": request.customer_id,
                "pet_id": request.pet_id,
                "special_instructions": request.special_instructions,
                "correlation_id": correlation_id
            })

        # Add user context to order
        order_data["created_by"] = user_context["user_id"]
        order_data["processing_type"] = "saga" if express_processing else "direct"

        return EnhancedResponse(
            success=True,
            data=order_data,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error creating order - customer_id: {request.customer_id}, "
            f"correlation_id: {correlation_id}, error: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to create order",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__,
                "support_contact": "support@petstore.com"
            }
        )

@router.post("/payments")
@trace_operation("process_payment")
@track_metrics("payment_processing_requests")
@requires_auth
@rate_limit(requests_per_minute=20)
@with_retry(max_attempts=2)  # Payments are sensitive, fewer retries
async def process_payment(
    request: PaymentRequest,
    user_context: dict = Depends(get_user_context)
):
    """Process payment with enhanced security and observability"""
    correlation_id = request.get_correlation_id()
    user_context["correlation_id"] = correlation_id

    logger.info(
        f"Processing payment - order_id: {request.order_id}, "
        f"method: {request.payment_method}, correlation_id: {correlation_id}"
    )

    # Enhanced security checks
    if "customer" not in user_context.get("roles", []):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Insufficient permissions to process payments",
                "correlation_id": correlation_id
            }
        )

    # Check payment processing feature flag
    payment_processing_enabled = await get_feature_flag("payment_processing", True)
    if not payment_processing_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Payment processing is temporarily unavailable",
                "correlation_id": correlation_id,
                "retry_after": "Please try again in a few minutes"
            }
        )

    service = await get_service()

    try:
        # This would integrate with the saga orchestrator for payment processing
        payment_data = await service.process_payment(
            order_id=request.order_id,
            payment_method=request.payment_method,
            correlation_id=correlation_id
        )

        # Add security metadata
        payment_data["processed_by"] = user_context["user_id"]
        payment_data["security_level"] = "high"
        payment_data["audit_trail"] = f"payment-{correlation_id}"

        return EnhancedResponse(
            success=True,
            data=payment_data,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing payment - order_id: {request.order_id}, "
            f"correlation_id: {correlation_id}, error: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Payment processing failed",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__,
                "support_contact": "payments@petstore.com"
            }
        )

@router.get("/orders/{order_id}/status")
@trace_operation("get_order_status")
@track_metrics("order_status_requests")
@requires_auth
async def get_order_status(
    order_id: str,
    user_context: dict = Depends(get_user_context)
):
    """Get order status with workflow tracking"""
    correlation_id = user_context["correlation_id"]

    logger.info(f"Getting order status - order_id: {order_id}, correlation_id: {correlation_id}")

    service = await get_service()

    try:
        status_data = await service.get_order_status(order_id, correlation_id)

        # Add user context and audit information
        status_data["requested_by"] = user_context["user_id"]
        status_data["access_level"] = user_context["roles"]

        # Add real-time updates feature if enabled
        real_time_updates = await get_feature_flag("real_time_order_updates", False)
        if real_time_updates:
            status_data["websocket_url"] = f"ws://api/orders/{order_id}/updates"
            status_data["real_time_enabled"] = True

        return EnhancedResponse(
            success=True,
            data=status_data,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting order status - order_id: {order_id}, "
            f"correlation_id: {correlation_id}, error: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to retrieve order status",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__
            }
        )

# Event-Driven Endpoint Examples
@router.post("/events/order-created")
@event_handler("order_created")
async def handle_order_created_event(
    event_data: dict[str, Any],
    correlation_id: str = Depends(get_correlation_id)
):
    """Handle order created events from other services"""
    logger.info(f"Handling order created event - correlation_id: {correlation_id}")

    try:
        # Process the event (e.g., send notifications, update inventory)
        result = {
            "event_processed": True,
            "event_type": "order_created",
            "correlation_id": correlation_id,
            "processing_timestamp": datetime.utcnow().isoformat()
        }

        return EnhancedResponse(
            success=True,
            data=result,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error processing order created event - correlation_id: {correlation_id}, error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to process order created event",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__
            }
        )

# Configuration and Feature Flag Endpoints (Admin only)
@router.get("/admin/config")
@trace_operation("get_configuration")
@requires_auth
async def get_configuration(
    user_context: dict = Depends(get_user_context)
):
    """Get current configuration values (admin endpoint)"""
    correlation_id = user_context["correlation_id"]

    # Check admin permissions
    if "admin" not in user_context.get("roles", []):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Admin privileges required",
                "correlation_id": correlation_id
            }
        )

    logger.info(f"Getting configuration - correlation_id: {correlation_id}, admin: {user_context['user_id']}")

    try:
        config_data = {
            "feature_flags": {
                "pet_personalization": await get_feature_flag("pet_personalization", False),
                "premium_filters": await get_feature_flag("premium_filters", True),
                "express_order_processing": await get_feature_flag("express_order_processing", False),
                "payment_processing": await get_feature_flag("payment_processing", True),
                "real_time_order_updates": await get_feature_flag("real_time_order_updates", False)
            },
            "config_values": {
                "pricing.display_currency": await get_config_value("pricing.display_currency", "USD"),
                "pricing.markup_percentage": await get_config_value("pricing.markup_percentage", 0.0),
                "service.max_orders_per_customer": await get_config_value("service.max_orders_per_customer", 10)
            },
            "mmf_status": {
                "framework_available": MMF_AVAILABLE,
                "observability_enabled": MMF_AVAILABLE,
                "security_enabled": MMF_AVAILABLE,
                "event_streaming_enabled": MMF_AVAILABLE
            }
        }

        return EnhancedResponse(
            success=True,
            data=config_data,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting configuration - correlation_id: {correlation_id}, error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to retrieve configuration",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__
            }
        )

# Legacy compatibility endpoint
@router.post("/process")
@trace_operation("legacy_process_request")
@track_metrics("legacy_requests")
async def process_legacy_request(
    request: dict[str, Any],
    correlation_id: str = Depends(get_correlation_id)
):
    """Legacy endpoint for backward compatibility"""
    logger.info(f"Processing legacy request - correlation_id: {correlation_id}")

    service = await get_service()

    try:
        # Add correlation ID to request
        request["correlation_id"] = correlation_id

        result = await service.process_request(request)

        return EnhancedResponse(
            success=True,
            data=result,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error processing legacy request - correlation_id: {correlation_id}, error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to process legacy request",
                "correlation_id": correlation_id,
                "error_type": type(e).__name__
            }
        )
