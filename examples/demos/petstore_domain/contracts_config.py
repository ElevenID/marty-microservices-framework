"""
Contract Testing Examples for Petstore Domain Plugin

This module demonstrates how to create and manage consumer-driven contracts
for the petstore service using the Marty Framework's contract testing capabilities.

Contract Types Demonstrated:
- Consumer contracts for frontend applications
- Service-to-service contracts for internal APIs
- Integration contracts for external services
- API version compatibility contracts

Author: Marty Framework Team
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from marty_msf.framework.testing.contract_testing import pact_contract

logger = logging.getLogger(__name__)


class PetstoreContractManager:
    """Manages contract testing for the petstore domain service."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.contracts_dir = base_path / "contracts"
        self.contracts_dir.mkdir(exist_ok=True)

        # Create subdirectories for different contract types
        (self.contracts_dir / "rest").mkdir(exist_ok=True)
        (self.contracts_dir / "integration").mkdir(exist_ok=True)
        (self.contracts_dir / "internal").mkdir(exist_ok=True)

    async def create_frontend_contracts(self):
        """Create contracts for frontend applications consuming the petstore API."""

        logger.info("Creating frontend consumer contracts...")

        # Web frontend contract for pet management
        web_frontend_contract = (
            pact_contract("web-frontend", "petstore-domain", "2.0.0")
            .interaction("Get all pets")
            .upon_receiving("GET", "/petstore-domain/pets")
            .with_query({"page": "1", "size": "10"})
            .with_headers({"Authorization": "Bearer jwt-token"})
            .will_respond_with(200)
            .with_response_headers({"Content-Type": "application/json"})
            .with_response_body({
                "success": True,
                "correlation_id": "req-123",
                "timestamp": "2025-10-15T10:00:00Z",
                "data": {
                    "pets": [
                        {
                            "id": "pet-001",
                            "name": "Buddy",
                            "species": "dog",
                            "breed": "Golden Retriever",
                            "age": 3,
                            "status": "available",
                            "price": 599.99
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "size": 10,
                        "total": 1,
                        "total_pages": 1
                    }
                }
            })
            .interaction("Create new pet")
            .upon_receiving("POST", "/petstore-domain/pets")
            .with_headers({"Authorization": "Bearer jwt-token", "Content-Type": "application/json"})
            .with_request_body({
                "name": "Max",
                "species": "cat",
                "breed": "Persian",
                "age": 2,
                "price": 450.00
            })
            .will_respond_with(201)
            .with_response_body({
                "success": True,
                "correlation_id": "req-124",
                "timestamp": "2025-10-15T10:01:00Z",
                "data": {
                    "id": "pet-002",
                    "name": "Max",
                    "species": "cat",
                    "breed": "Persian",
                    "age": 2,
                    "status": "available",
                    "price": 450.00
                }
            })
            .interaction("Update pet details")
            .upon_receiving("PUT", "/petstore-domain/pets/pet-001")
            .with_headers({"Authorization": "Bearer jwt-token", "Content-Type": "application/json"})
            .with_request_body({
                "name": "Buddy Updated",
                "price": 649.99
            })
            .will_respond_with(200)
            .interaction("Handle pet not found")
            .upon_receiving("GET", "/petstore-domain/pets/nonexistent")
            .with_headers({"Authorization": "Bearer jwt-token"})
            .will_respond_with(404)
            .with_response_body({
                "error": "Pet not found",
                "error_code": "PET_NOT_FOUND",
                "correlation_id": "req-125",
                "timestamp": "2025-10-15T10:02:00Z"
            })
            .build()
        )

        # Mobile app contract with different requirements
        mobile_app_contract = (
            pact_contract("mobile-app", "petstore-domain", "2.0.0")
            .interaction("Get pets with mobile-optimized response")
            .upon_receiving("GET", "/petstore-domain/pets")
            .with_query({"mobile": "true", "size": "5"})
            .with_headers({"Authorization": "Bearer mobile-jwt-token", "User-Agent": "PetstoreApp/2.1.0"})
            .will_respond_with(200)
            .with_response_body({
                "success": True,
                "correlation_id": "mob-req-001",
                "timestamp": "2025-10-15T10:03:00Z",
                "data": {
                    "pets": [
                        {
                            "id": "pet-001",
                            "name": "Buddy",
                            "species": "dog",
                            "thumbnail": "https://cdn.petstore.com/thumbs/pet-001.jpg",
                            "price": 599.99,
                            "status": "available"
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "size": 5,
                        "has_more": False
                    }
                }
            })
            .interaction("Create order for mobile")
            .upon_receiving("POST", "/petstore-domain/orders")
            .with_headers({"Authorization": "Bearer mobile-jwt-token", "Content-Type": "application/json"})
            .with_request_body({
                "pet_id": "pet-001",
                "customer_id": "cust-001",
                "payment_method": "mobile_wallet"
            })
            .will_respond_with(201)
            .build()
        )

        # Save contracts
        self._save_contract(web_frontend_contract, "rest/web-frontend-petstore-domain.json")
        self._save_contract(mobile_app_contract, "rest/mobile-app-petstore-domain.json")

        logger.info("Frontend contracts created successfully")

    async def create_internal_service_contracts(self):
        """Create contracts for internal service-to-service communication."""

        logger.info("Creating internal service contracts...")

        # Order service -> Petstore domain contract
        order_service_contract = (
            pact_contract("order-service", "petstore-domain", "2.0.0")
            .interaction("Check pet availability")
            .upon_receiving("GET", "/petstore-domain/pets/pet-001/availability")
            .with_headers({"Authorization": "Bearer service-token", "X-Service-Name": "order-service"})
            .will_respond_with(200)
            .with_response_body({
                "success": True,
                "correlation_id": "svc-req-001",
                "timestamp": "2025-10-15T10:04:00Z",
                "data": {
                    "pet_id": "pet-001",
                    "available": True,
                    "stock_count": 1,
                    "reserved_until": None
                }
            })
            .interaction("Reserve pet for order")
            .upon_receiving("POST", "/petstore-domain/pets/pet-001/reserve")
            .with_headers({"Authorization": "Bearer service-token", "Content-Type": "application/json"})
            .with_request_body({
                "order_id": "order-001",
                "customer_id": "cust-001",
                "reservation_duration": 900  # 15 minutes
            })
            .will_respond_with(200)
            .interaction("Handle insufficient stock")
            .upon_receiving("POST", "/petstore-domain/pets/out-of-stock-pet/reserve")
            .with_headers({"Authorization": "Bearer service-token", "Content-Type": "application/json"})
            .with_request_body({
                "order_id": "order-002",
                "customer_id": "cust-002",
                "reservation_duration": 900
            })
            .will_respond_with(409)
            .with_response_body({
                "error": "Insufficient stock",
                "error_code": "INSUFFICIENT_STOCK",
                "correlation_id": "svc-req-002",
                "timestamp": "2025-10-15T10:05:00Z"
            })
            .build()
        )

        # Notification service -> Petstore domain contract
        notification_contract = (
            pact_contract("notification-service", "petstore-domain", "2.0.0")
            .interaction("Get customer preferences")
            .upon_receiving("GET", "/petstore-domain/customers/cust-001/preferences")
            .with_headers({"Authorization": "Bearer service-token", "X-Service-Name": "notification-service"})
            .will_respond_with(200)
            .with_response_body({
                "success": True,
                "correlation_id": "notif-req-001",
                "timestamp": "2025-10-15T10:06:00Z",
                "data": {
                    "customer_id": "cust-001",
                    "email_notifications": True,
                    "sms_notifications": False,
                    "push_notifications": True,
                    "preferred_language": "en-US"
                }
            })
            .build()
        )

        # Save internal contracts
        self._save_contract(order_service_contract, "internal/order-service-petstore-domain.json")
        self._save_contract(notification_contract, "internal/notification-service-petstore-domain.json")

        logger.info("Internal service contracts created successfully")

    async def create_external_integration_contracts(self):
        """Create contracts for external service integrations."""

        logger.info("Creating external integration contracts...")

        # Petstore domain -> Payment service contract
        payment_service_contract = (
            pact_contract("petstore-domain", "payment-service", "3.0.0")
            .interaction("Process payment")
            .upon_receiving("POST", "/payments/process")
            .with_headers({"Authorization": "Bearer payment-api-key", "Content-Type": "application/json"})
            .with_request_body({
                "amount": 599.99,
                "currency": "USD",
                "payment_method": "credit_card",
                "customer_id": "cust-001",
                "order_id": "order-001",
                "idempotency_key": "pay-idmp-001"
            })
            .will_respond_with(200)
            .with_response_body({
                "payment_id": "pay-001",
                "status": "completed",
                "amount": 599.99,
                "currency": "USD",
                "transaction_id": "txn-001"
            })
            .interaction("Handle payment failure")
            .upon_receiving("POST", "/payments/process")
            .with_headers({"Authorization": "Bearer payment-api-key", "Content-Type": "application/json"})
            .with_request_body({
                "amount": 1000000.00,  # Exceeds limit
                "currency": "USD",
                "payment_method": "credit_card",
                "customer_id": "cust-002",
                "order_id": "order-002",
                "idempotency_key": "pay-idmp-002"
            })
            .will_respond_with(400)
            .with_response_body({
                "error": "Payment amount exceeds limit",
                "error_code": "AMOUNT_LIMIT_EXCEEDED",
                "payment_id": None
            })
            .build()
        )

        # Petstore domain -> Shipping service contract
        shipping_service_contract = (
            pact_contract("petstore-domain", "shipping-service", "2.1.0")
            .interaction("Create shipment")
            .upon_receiving("POST", "/shipments")
            .with_headers({"Authorization": "Bearer shipping-api-key", "Content-Type": "application/json"})
            .with_request_body({
                "order_id": "order-001",
                "recipient": {
                    "name": "John Doe",
                    "address": "123 Main St, Anytown, ST 12345",
                    "phone": "+1234567890"
                },
                "items": [
                    {
                        "id": "pet-001",
                        "name": "Buddy",
                        "weight": 25.5,
                        "special_handling": ["live_animal", "temperature_controlled"]
                    }
                ],
                "shipping_method": "express"
            })
            .will_respond_with(201)
            .with_response_body({
                "shipment_id": "ship-001",
                "tracking_number": "TRK123456789",
                "estimated_delivery": "2025-10-17T15:00:00Z",
                "shipping_cost": 49.99
            })
            .build()
        )

        # Save external contracts
        self._save_contract(payment_service_contract, "integration/petstore-domain-payment-service.json")
        self._save_contract(shipping_service_contract, "integration/petstore-domain-shipping-service.json")

        logger.info("External integration contracts created successfully")

    async def create_version_compatibility_contracts(self):
        """Create contracts for API version compatibility testing."""

        logger.info("Creating version compatibility contracts...")

        # Legacy v1.0 client contract
        legacy_client_contract = (
            pact_contract("legacy-client", "petstore-domain", "1.0.0")
            .interaction("Get pets with legacy format")
            .upon_receiving("GET", "/api/v1/pets")
            .with_headers({"Authorization": "Bearer legacy-token"})
            .will_respond_with(200)
            .with_response_body({
                "pets": [
                    {
                        "id": 1,
                        "name": "Buddy",
                        "type": "dog",
                        "price": 599.99
                    }
                ],
                "total": 1
            })
            .build()
        )

        # Beta v2.1 client contract
        beta_client_contract = (
            pact_contract("beta-client", "petstore-domain", "2.1.0-beta")
            .interaction("Get pets with new features")
            .upon_receiving("GET", "/petstore-domain/pets")
            .with_query({"include_ai_recommendations": "true"})
            .with_headers({"Authorization": "Bearer beta-token", "X-Beta-Features": "ai-recommendations"})
            .will_respond_with(200)
            .with_response_body({
                "success": True,
                "correlation_id": "beta-req-001",
                "timestamp": "2025-10-15T10:07:00Z",
                "data": {
                    "pets": [
                        {
                            "id": "pet-001",
                            "name": "Buddy",
                            "species": "dog",
                            "breed": "Golden Retriever",
                            "age": 3,
                            "status": "available",
                            "price": 599.99,
                            "ai_recommendations": {
                                "compatibility_score": 0.95,
                                "care_level": "moderate",
                                "suggested_accessories": ["leash", "bed", "toys"]
                            }
                        }
                    ]
                }
            })
            .build()
        )

        # Save version compatibility contracts
        self._save_contract(legacy_client_contract, "rest/legacy-client-petstore-domain-v1.json")
        self._save_contract(beta_client_contract, "rest/beta-client-petstore-domain-v2-1-beta.json")

        logger.info("Version compatibility contracts created successfully")

    def _save_contract(self, contract, filename: str):
        """Save a contract to the contracts directory."""
        filepath = self.contracts_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Convert contract to JSON if needed
        if hasattr(contract, 'to_dict'):
            contract_data = contract.to_dict()
        else:
            contract_data = contract

        with open(filepath, 'w') as f:
            json.dump(contract_data, f, indent=2)

        logger.info(f"Contract saved to {filepath}")

    async def create_all_contracts(self):
        """Create all contract types for the petstore domain."""
        logger.info("Creating all petstore contracts...")

        await self.create_frontend_contracts()
        await self.create_internal_service_contracts()
        await self.create_external_integration_contracts()
        await self.create_version_compatibility_contracts()

        logger.info("All petstore contracts created successfully")

        # Create contract documentation
        await self._create_contract_documentation()

    async def _create_contract_documentation(self):
        """Create documentation for all contracts."""
        docs_dir = self.contracts_dir / "docs"
        docs_dir.mkdir(exist_ok=True)

        readme_content = """# Petstore Domain Contracts

This directory contains all consumer-driven contracts for the Petstore Domain service.

## Contract Types

### Frontend Contracts (`rest/`)
- `web-frontend-petstore-domain.json`: Web application contract
- `mobile-app-petstore-domain.json`: Mobile application contract
- `legacy-client-petstore-domain-v1.json`: Legacy v1.0 API client
- `beta-client-petstore-domain-v2-1-beta.json`: Beta v2.1 API client

### Internal Service Contracts (`internal/`)
- `order-service-petstore-domain.json`: Order service integration
- `notification-service-petstore-domain.json`: Notification service integration

### External Integration Contracts (`integration/`)
- `petstore-domain-payment-service.json`: Payment service integration
- `petstore-domain-shipping-service.json`: Shipping service integration

## Running Contract Tests

### Test All Contracts
```bash
marty api test-contracts -p petstore-domain -u http://localhost:8000
```

### Test Specific Consumer
```bash
marty api test-contracts -p petstore-domain -u http://localhost:8000 -c web-frontend
```

### Generate Contract Documentation
```bash
marty api generate-contract-docs --contracts-dir ./contracts --docs-dir ./docs/contracts
```

## Contract Management

### Create New Contract
```bash
marty api create-contract -c new-consumer -p petstore-domain --interactive
```

### Monitor Contract Compliance
```bash
marty api monitor-contracts -p petstore-domain --interval 300
```

## Version Compatibility

The contracts ensure compatibility across API versions:
- **v1.0**: Legacy format (deprecated 2024-12-31)
- **v2.0**: Current stable version
- **v2.1-beta**: Beta features for testing

Each consumer can specify which version they expect, enabling safe API evolution.
"""

        with open(docs_dir / "README.md", 'w') as f:
            f.write(readme_content)

        logger.info("Contract documentation created")


async def setup_petstore_contracts():
    """Setup all petstore contracts."""
    base_path = Path(__file__).parent
    contract_manager = PetstoreContractManager(base_path)

    await contract_manager.create_all_contracts()

    return contract_manager


if __name__ == "__main__":
    # CLI entry point for contract creation
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_petstore_contracts())
