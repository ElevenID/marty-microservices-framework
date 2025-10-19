#!/usr/bin/env python3
"""
Enhanced Petstore Service for Kubernetes Demo
Includes event streaming capabilities and distributed system patterns
"""

import asyncio
import json
import logging
import random
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Event System Classes
class Event(BaseModel):
    event_id: str
    event_type: str
    aggregate_id: str
    data: Dict[str, Any]
    timestamp: datetime
    correlation_id: Optional[str] = None

class EventStore:
    """In-memory event store for demo purposes"""

    def __init__(self):
        self.events: List[Event] = []
        self.subscribers: Dict[str, List[callable]] = defaultdict(list)
        self.event_stream: deque = deque(maxlen=1000)  # Keep last 1000 events

    def publish_event(self, event: Event):
        """Publish an event to the event store"""
        self.events.append(event)
        self.event_stream.append(event)
        logger.info(f"Published event: {event.event_type} for {event.aggregate_id}")

        # Notify subscribers
        for subscriber in self.subscribers.get(event.event_type, []):
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

    def subscribe(self, event_type: str, callback: callable):
        """Subscribe to events of a specific type"""
        self.subscribers[event_type].append(callback)
        logger.info(f"New subscriber for event type: {event_type}")

    def get_events_by_aggregate(self, aggregate_id: str) -> List[Event]:
        """Get all events for a specific aggregate"""
        return [event for event in self.events if event.aggregate_id == aggregate_id]

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Get recent events from the stream"""
        return list(self.event_stream)[-limit:]

# Global event store
event_store = EventStore()

# Pydantic models
class Pet(BaseModel):
    pet_id: str
    name: str
    category: str
    breed: Optional[str] = None
    age_months: Optional[int] = None
    price: float
    description: Optional[str] = None
    available: bool = True

class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None

class Order(BaseModel):
    order_id: str
    customer_id: str
    pet_id: str
    amount: float
    status: str
    correlation_id: str

# In-memory data store for demo
pets_db = [
    Pet(
        pet_id="golden-retriever-001",
        name="Buddy",
        category="dog",
        breed="Golden Retriever",
        age_months=8,
        price=1200.00,
        description="Friendly and energetic Golden Retriever puppy",
        available=True
    ),
    Pet(
        pet_id="persian-cat-002",
        name="Princess",
        category="cat",
        breed="Persian Cat",
        age_months=12,
        price=800.00,
        description="Beautiful Persian cat with long fluffy coat",
        available=True
    ),
    Pet(
        pet_id="cockatiel-003",
        name="Sunny",
        category="bird",
        breed="Cockatiel",
        age_months=6,
        price=300.00,
        description="Social and intelligent cockatiel with beautiful crest",
        available=True
    )
]

customers_db = [
    Customer(
        customer_id="customer-001",
        name="Alice Johnson",
        email="alice@example.com",
        phone="+1-555-0101",
        address="123 Pet Lover Lane, Dogtown, ST 12345"
    ),
    Customer(
        customer_id="customer-002",
        name="Bob Smith",
        email="bob@example.com",
        phone="+1-555-0102",
        address="456 Cat Avenue, Kittyville, ST 12346"
    )
]

orders_db = []

# Create FastAPI app
app = FastAPI(
    title="Petstore Domain Service",
    description="Simple petstore demo service for Kubernetes",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "petstore-domain",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return {
        "status": "ready",
        "service": "petstore-domain",
        "timestamp": datetime.utcnow().isoformat()
    }

# Petstore endpoints
@app.get("/petstore-domain/pets")
async def get_pets(category: Optional[str] = None):
    """Get all available pets, optionally filtered by category"""
    pets = [pet for pet in pets_db if pet.available]
    if category:
        pets = [pet for pet in pets if pet.category.lower() == category.lower()]

    return {
        "pets": pets,
        "total": len(pets),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/pets/{pet_id}")
async def get_pet(pet_id: str):
    """Get a specific pet by ID"""
    pet = next((pet for pet in pets_db if pet.pet_id == pet_id), None)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    return {
        "pet": pet,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/customers")
async def get_customers():
    """Get all customers"""
    return {
        "customers": customers_db,
        "total": len(customers_db),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/petstore-domain/orders")
async def create_order(order_data: dict[str, Any], background_tasks: BackgroundTasks):
    """Create a new order with event publishing"""
    # Validate pet exists and is available
    pet = next((pet for pet in pets_db if pet.pet_id == order_data.get("pet_id")), None)
    if not pet or not pet.available:
        raise HTTPException(status_code=400, detail="Pet not available")

    # Validate customer exists
    customer = next((customer for customer in customers_db if customer.customer_id == order_data.get("customer_id")), None)
    if not customer:
        raise HTTPException(status_code=400, detail="Customer not found")

    # Create correlation ID for this transaction
    correlation_id = f"corr-{uuid.uuid4()}"

    # Create order
    order = Order(
        order_id=f"order-{int(time.time())}-{random.randint(1000, 9999)}",
        customer_id=order_data["customer_id"],
        pet_id=order_data["pet_id"],
        amount=pet.price,
        status="pending",
        correlation_id=correlation_id
    )

    orders_db.append(order)

    # Mark pet as not available
    pet.available = False

    # Publish events for the order creation
    def publish_order_events():
        # Order created event
        order_created_event = Event(
            event_id=str(uuid.uuid4()),
            event_type="order.created",
            aggregate_id=order.order_id,
            data={
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "pet_id": order.pet_id,
                "amount": order.amount,
                "status": order.status
            },
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id
        )
        event_store.publish_event(order_created_event)

        # Inventory updated event
        inventory_updated_event = Event(
            event_id=str(uuid.uuid4()),
            event_type="inventory.updated",
            aggregate_id=pet.pet_id,
            data={
                "pet_id": pet.pet_id,
                "available": pet.available,
                "reserved_for_order": order.order_id
            },
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id
        )
        event_store.publish_event(inventory_updated_event)

    # Schedule event publishing as background task
    background_tasks.add_task(publish_order_events)

    logger.info(f"Created order {order.order_id} for pet {order.pet_id}")

    return {
        "order": order,
        "status": "created",
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": correlation_id
    }

@app.get("/petstore-domain/orders")
async def get_orders():
    """Get all orders"""
    return {
        "orders": orders_db,
        "total": len(orders_db),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/orders/{order_id}")
async def get_order(order_id: str):
    """Get a specific order by ID"""
    order = next((order for order in orders_db if order.order_id == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order": order,
        "timestamp": datetime.utcnow().isoformat()
    }

# Demo endpoints for testing
@app.get("/petstore-domain/demo/status")
async def demo_status():
    """Demo status endpoint"""
    return {
        "demo_status": "active",
        "features": {
            "pets_catalog": True,
            "order_processing": True,
            "customer_management": True,
            "health_checks": True
        },
        "stats": {
            "total_pets": len(pets_db),
            "available_pets": len([pet for pet in pets_db if pet.available]),
            "total_customers": len(customers_db),
            "total_orders": len(orders_db)
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/demo/reset")
async def reset_demo():
    """Reset demo data"""
    global orders_db
    orders_db = []

    # Reset pet availability
    for pet in pets_db:
        pet.available = True

    logger.info("Demo data reset")

    return {
        "status": "reset_complete",
        "message": "Demo data has been reset",
        "timestamp": datetime.utcnow().isoformat()
    }

# Event streaming endpoints
@app.get("/petstore-domain/events/stream")
async def get_event_stream(limit: int = 50):
    """Get recent events from the event stream"""
    events = event_store.get_recent_events(limit)
    return {
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id
            }
            for event in events
        ],
        "total": len(events),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/events/by-aggregate/{aggregate_id}")
async def get_events_by_aggregate(aggregate_id: str):
    """Get all events for a specific aggregate"""
    events = event_store.get_events_by_aggregate(aggregate_id)
    return {
        "aggregate_id": aggregate_id,
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id
            }
            for event in events
        ],
        "total": len(events),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/events/types/{event_type}")
async def get_events_by_type(event_type: str):
    """Get all events of a specific type"""
    events = [event for event in event_store.events if event.event_type == event_type]
    return {
        "event_type": event_type,
        "events": [
            {
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id
            }
            for event in events
        ],
        "total": len(events),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/petstore-domain/events/stats")
async def get_event_stats():
    """Get event stream statistics"""
    event_types = {}
    for event in event_store.events:
        event_types[event.event_type] = event_types.get(event.event_type, 0) + 1

    return {
        "total_events": len(event_store.events),
        "event_types": event_types,
        "recent_events_count": len(event_store.event_stream),
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    print("🚀 Starting Enhanced Petstore Service with Event Streaming...")
    print("📊 Health: http://localhost:8080/health")
    print("📋 API Docs: http://localhost:8080/docs")
    print("🐾 Pets: http://localhost:8080/petstore-domain/pets")
    print("📦 Orders: http://localhost:8080/petstore-domain/orders")
    print("🔄 Events: http://localhost:8080/petstore-domain/events/stream")

    uvicorn.run(
        "simple_main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
