# gRPC Service Template Example

This is a full-featured gRPC service template that demonstrates:

## Architecture
- **Hexagonal Architecture** (Ports & Adapters)
- **Domain-Driven Design** principles
- **Async gRPC** implementation
- **Integration with external services** via MMF connectors

## Features
- gRPC API with Protocol Buffers
- External service integration (inventory service)
- In-memory repository (easily replaceable)
- Health checks
- Proper error handling
- Mock protobuf classes (for demonstration)

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate gRPC Code (Production)
```bash
# Generate Python gRPC code from proto files
python -m grpc_tools.protoc \
    --proto_path=proto \
    --python_out=proto \
    --grpc_python_out=proto \
    proto/order_service.proto
```

### 3. Run the Service
```bash
python server.py
```

## Proto Definition

The service is defined in `proto/order_service.proto` with:
- **CreateOrder** - Create new orders
- **GetOrder** - Retrieve orders by ID
- **HealthCheck** - Service health status

## Testing with grpcurl

### Install grpcurl
```bash
# macOS
brew install grpcurl

# Or download from: https://github.com/fullstorydev/grpcurl
```

### Test the Service
```bash
# Health check
grpcurl -plaintext localhost:50051 order_service.OrderService/HealthCheck

# Create order
grpcurl -plaintext -d '{
  "customer_id": "customer-123",
  "items": [
    {
      "product_id": "product-456", 
      "quantity": 2,
      "price": 29.99
    }
  ]
}' localhost:50051 order_service.OrderService/CreateOrder

# Get order (use order_id from create response)
grpcurl -plaintext -d '{
  "order_id": "your-order-id-here"
}' localhost:50051 order_service.OrderService/GetOrder
```

## Integration Points

The service integrates with:
1. **Inventory Service** - Checks product availability via REST
2. **Order Repository** - Stores order data

## Production Considerations

This template uses mock protobuf classes for demonstration. In production:

1. **Generate Real Protobuf Code:**
   ```bash
   python -m grpc_tools.protoc --proto_path=proto --python_out=proto --grpc_python_out=proto proto/order_service.proto
   ```

2. **Replace Mock Classes:**
   - Import generated `order_service_pb2` and `order_service_pb2_grpc`
   - Remove mock classes
   - Use real protobuf message types

3. **Add Server Reflection:**
   ```python
   from grpc_reflection.v1alpha import reflection
   reflection.enable_server_reflection(SERVICE_NAMES, server)
   ```

## Customization

To adapt this template:
1. Replace `InMemoryOrderRepository` with your database adapter
2. Configure inventory service connection
3. Add authentication/authorization interceptors
4. Extend domain models and proto definitions
5. Add more business logic to the application service
6. Configure TLS for production

## Architecture Benefits

- **Type Safety** - Protocol Buffers provide strong typing
- **Performance** - Binary serialization is efficient
- **Language Agnostic** - Clients can be written in many languages
- **Streaming Support** - Built-in support for streaming RPCs
- **Load Balancing** - Built-in client-side load balancing