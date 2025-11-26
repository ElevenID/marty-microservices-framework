# FastAPI Service Template Example

This is a full-featured FastAPI service template that demonstrates:

## Architecture
- **Hexagonal Architecture** (Ports & Adapters)
- **Domain-Driven Design** principles
- **Async/Await** throughout
- **Integration with external services** via MMF connectors

## Features
- RESTful API with FastAPI
- External service integration (inventory service)
- In-memory repository (easily replaceable)
- Health checks
- Proper error handling
- Pydantic models for request/response validation

## Running the Service

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn main:app --reload --port 8000

# Or with custom configuration
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Create Order
```bash
POST /orders
Content-Type: application/json

{
  "customer_id": "customer-123",
  "items": [
    {
      "product_id": "product-456",
      "quantity": 2,
      "price": 29.99
    }
  ]
}
```

### Get Order
```bash
GET /orders/{order_id}
```

### Health Check
```bash
GET /health
```

## Integration Points

The service integrates with:
1. **Inventory Service** - Checks product availability
2. **Order Repository** - Stores order data

## Customization

To adapt this template:
1. Replace `InMemoryOrderRepository` with your database adapter
2. Configure `INVENTORY_CONFIG` for your inventory service
3. Add authentication/authorization middleware
4. Extend domain models as needed
5. Add more business logic to the application service

## Testing

```bash
# Test the service
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "test-customer",
    "items": [{"product_id": "test-product", "quantity": 1, "price": 10.0}]
  }'
```