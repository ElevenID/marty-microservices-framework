"""
Petstore Domain Extended Messaging Examples

This module demonstrates how the petstore domain uses the extended messaging
capabilities for real-world e-commerce scenarios including order processing,
inventory management, and customer communications.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from app.services.enhanced_petstore_service import EnhancedPetstoreDomainService
from app.services.petstore_extended_messaging_service import (
    PetstoreEventType,
    PetstoreMessagingPattern,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_petstore_extended_messaging():
    """Demonstrate petstore extended messaging integration"""
    print("=" * 60)
    print("🐕 Petstore Extended Messaging Demonstration")
    print("=" * 60)

    try:
        # Import petstore service with extended messaging

        # Configuration for extended messaging
        config = {
            "extended_messaging": {
                "enabled": True,
                "nats": {
                    "enabled": True,
                    "servers": ["nats://localhost:4222"],
                    "jetstream_enabled": True
                },
                "aws_sns": {
                    "enabled": False  # Disabled for demo
                }
            }
        }

        # Initialize petstore service
        petstore_service = EnhancedPetstoreDomainService(config)
        await petstore_service.initialize()

        print("✅ Petstore service initialized with extended messaging")

        # Demonstrate browsing pets with extended messaging
        print("\n📋 Browsing pets with extended messaging...")
        pets_result = await petstore_service.browse_pets_with_extended_messaging(
            category="dog",
            max_price=1500.0,
            correlation_id="demo-browse-001"
        )

        print(f"   Found {pets_result['total_count']} dogs under $1500")
        if pets_result["pets"]:
            for pet in pets_result["pets"][:2]:  # Show first 2
                print(f"   - {pet['name']} ({pet['breed']}): ${pet['price']}")

        # Demonstrate order creation with extended messaging saga
        print("\n🛒 Creating order with extended messaging saga...")

        if pets_result["pets"]:
            selected_pet = pets_result["pets"][0]

            order_result = await petstore_service.create_order_saga(
                customer_id="customer-demo-001",
                pet_id=selected_pet["id"],
                amount=selected_pet["price"],
                special_instructions="Please ensure the pet is ready for pickup",
                correlation_id="demo-order-001"
            )

            print(f"   ✅ Order created: {order_result['order_id']}")
            print(f"   📊 Saga status: {order_result.get('saga_status', 'N/A')}")

            # Check order status
            print("\n📈 Checking order status...")
            order_status = await petstore_service.get_order_status(
                order_result['order_id'],
                correlation_id="demo-status-001"
            )

            print(f"   Order {order_status['order_id']}: {order_status['status']}")

        else:
            print("   ⚠️  No pets available for ordering")

        # Demonstrate messaging patterns summary
        print("\n🔄 Extended Messaging Patterns Used:")
        print("   📢 Pub/Sub: Inventory updates and customer notifications")
        print("   🎯 Point-to-Point: Payment processing commands")
        print("   🔄 Request/Response: Inventory status queries")
        print("   📊 Streaming: Order analytics and events")

        print("\n🏗️  Backend Configuration:")
        if petstore_service.extended_messaging_service:
            print("   ✅ Extended messaging service active")
            print("   🚀 NATS backend configured")
            print("   ☁️  AWS SNS backend (disabled for demo)")
            print("   📈 Saga orchestration enabled")
        else:
            print("   ⚠️  Extended messaging service not available")

        print("\n" + "=" * 60)
        print("✅ Petstore extended messaging demonstration completed!")
        print("=" * 60)

    except ImportError as e:
        print(f"❌ Could not import petstore services: {e}")
        print("   Make sure you're running from the petstore_domain directory")
        await demonstrate_messaging_concepts()
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        logger.exception("Demonstration error")


async def demonstrate_messaging_concepts():
    """Demonstrate extended messaging concepts without petstore services"""
    print("\n🔧 Extended Messaging Concepts Demonstration")
    print("-" * 50)

    # Simulate messaging patterns
    messaging_patterns = {
        "inventory_broadcast": {
            "pattern": "pub_sub",
            "backend": "nats",
            "use_case": "Broadcast inventory changes to multiple services",
            "example": "Pet sold → notify warehouse, accounting, CRM"
        },
        "order_processing": {
            "pattern": "streaming",
            "backend": "kafka",
            "use_case": "High-volume order events for analytics",
            "example": "Order lifecycle events → analytics, reporting"
        },
        "customer_notifications": {
            "pattern": "pub_sub",
            "backend": "nats",
            "use_case": "Send notifications to multiple channels",
            "example": "Order confirmed → email, SMS, push notification"
        },
        "payment_commands": {
            "pattern": "point_to_point",
            "backend": "nats",
            "use_case": "Direct payment processing requests",
            "example": "Process payment → payment service directly"
        },
        "inventory_queries": {
            "pattern": "request_response",
            "backend": "nats",
            "use_case": "Real-time inventory status checks",
            "example": "Check pet availability → get immediate response"
        }
    }

    print("📋 Petstore Messaging Patterns:")
    for name, details in messaging_patterns.items():
        print(f"\n   🔸 {name.replace('_', ' ').title()}")
        print(f"      Pattern: {details['pattern']}")
        print(f"      Backend: {details['backend']}")
        print(f"      Use Case: {details['use_case']}")
        print(f"      Example: {details['example']}")

    # Simulate saga orchestration
    print("\n🔄 Order Processing Saga Flow:")
    saga_steps = [
        "1. 🔍 Validate Inventory → Reserve pet",
        "2. 💳 Process Payment → Charge customer",
        "3. 📦 Arrange Shipping → Schedule delivery",
        "4. 📊 Update Inventory → Mark pet as sold",
        "5. 📧 Send Confirmation → Notify customer"
    ]

    for step in saga_steps:
        print(f"   {step}")
        await asyncio.sleep(0.5)  # Simulate processing time

    print("\n   ✅ Saga completed successfully!")
    print("\n   🔄 If any step fails → automatic compensation:")
    print("      - Refund payment")
    print("      - Release inventory reservation")
    print("      - Cancel shipping")
    print("      - Send cancellation notice")


async def demonstrate_configuration_examples():
    """Show configuration examples for extended messaging"""
    print("\n⚙️  Extended Messaging Configuration Examples")
    print("-" * 50)

    # NATS Configuration
    nats_config = {
        "nats": {
            "enabled": True,
            "servers": ["nats://localhost:4222", "nats://nats-cluster:4222"],
            "jetstream_enabled": True,
            "stream_config": {
                "max_msgs": 10000,
                "max_bytes": 1048576,  # 1MB
                "retention": "workqueue"
            },
            "connection_timeout": 30,
            "request_timeout": 10
        }
    }

    # AWS SNS Configuration
    aws_sns_config = {
        "aws_sns": {
            "enabled": True,
            "region_name": "us-east-1",
            "fifo_topics": True,
            "topic_prefix": "petstore-prod",
            "credentials": {
                "aws_access_key_id": "${AWS_ACCESS_KEY_ID}",
                "aws_secret_access_key": "${AWS_SECRET_ACCESS_KEY}"
            }
        }
    }

    # Pattern Preferences
    pattern_config = {
        "backend_selection": {
            "default_backend": "nats",
            "pattern_preferences": {
                "pub_sub": "nats",
                "point_to_point": "nats",
                "request_response": "nats",
                "streaming": "kafka"
            },
            "fallback_backend": "kafka"
        }
    }

    print("📋 NATS Configuration:")
    print(json.dumps(nats_config, indent=2))

    print("\n☁️  AWS SNS Configuration:")
    print(json.dumps(aws_sns_config, indent=2))

    print("\n🎯 Backend Selection Strategy:")
    print(json.dumps(pattern_config, indent=2))


async def demonstrate_deployment_scenarios():
    """Show different deployment scenarios"""
    print("\n🚀 Deployment Scenarios")
    print("-" * 30)

    scenarios = {
        "Local Development": {
            "description": "Single developer machine",
            "backends": ["In-Memory", "Local NATS"],
            "config": "Simple, minimal setup"
        },
        "Staging Environment": {
            "description": "Pre-production testing",
            "backends": ["NATS Cluster", "Kafka"],
            "config": "Production-like, observability enabled"
        },
        "Production Cloud": {
            "description": "High availability deployment",
            "backends": ["AWS SNS", "NATS Cluster", "Kafka"],
            "config": "Multi-region, monitoring, security"
        },
        "Hybrid Setup": {
            "description": "On-premises + cloud",
            "backends": ["On-prem NATS", "AWS SNS", "Local Kafka"],
            "config": "Cross-network connectivity"
        }
    }

    for scenario_name, details in scenarios.items():
        print(f"\n🏗️  {scenario_name}")
        print(f"   Description: {details['description']}")
        print(f"   Backends: {', '.join(details['backends'])}")
        print(f"   Config: {details['config']}")


async def main():
    """Run all demonstrations"""
    print("🎯 Starting Petstore Extended Messaging Examples")
    print("=" * 70)

    try:
        # Main petstore demonstration
        await demonstrate_petstore_extended_messaging()

        # Configuration examples
        await demonstrate_configuration_examples()

        # Deployment scenarios
        await demonstrate_deployment_scenarios()

        print("\n🎉 All demonstrations completed successfully!")

    except Exception as e:
        print(f"\n❌ Error in demonstrations: {e}")
        logger.exception("Main demonstration error")


if __name__ == "__main__":
    asyncio.run(main())
