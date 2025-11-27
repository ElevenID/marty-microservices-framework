# Hybrid Service Template Example

This is a **hybrid service template** that provides both **REST API** and **gRPC** interfaces for the same business logic, demonstrating:

## Architecture

- **Hexagonal Architecture** (Ports & Adapters)
- **Domain-Driven Design** principles
- **Dual Protocol Support** (REST + gRPC)
- **Shared Business Logic** across protocols
- **Integration with external services** via MMF connectors

## Features

- **REST API** with FastAPI (JSON over HTTP)
- **gRPC API** with Protocol Buffers (binary over HTTP/2)
- **Shared domain models** and business logic
- **External service integration** (inventory service)
- **In-memory repository** (easily replaceable)
- **Health checks** for both protocols
- **Concurrent server execution**

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate gRPC Code (Production)

```bash
python -m grpc_tools.protoc \
    --proto_path=proto \
    --python_out=proto \
    --grpc_python_out=proto \
    proto/hybrid_order_service.proto
```

### 3. Run the Service

#### Option A: FastAPI Only (Development)

```bash
python main.py
# Runs on http://localhost:8000
```

#### Option B: gRPC Only

```bash
# Edit main.py to uncomment: asyncio.run(run_grpc_server())
python main.py
# Runs on localhost:50051
```

#### Option C: Both Servers (Production)

```bash
# Edit main.py to uncomment: asyncio.run(run_hybrid_servers())
python main.py
# REST on :8000, gRPC on :50051
```

## API Usage

### REST API Endpoints

```bash
# Create order
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "customer-123",
    "items": [{"product_id": "product-456", "quantity": 2, "price": 29.99}]
  }'

# Get order
curl "http://localhost:8000/orders/{order_id}"

# Batch get orders
curl -X POST "http://localhost:8000/orders/batch" \
  -H "Content-Type: application/json" \
  -d '{"order_ids": ["order-1", "order-2"]}'

# Health check
curl "http://localhost:8000/health"
```

### gRPC API Usage

```bash
# Install grpcurl: brew install grpcurl

# Create order
grpcurl -plaintext -d '{
  "customer_id": "customer-123",
  "items": [{"product_id": "product-456", "quantity": 2, "price": 29.99}]
}' localhost:50051 hybrid_order_service.HybridOrderService/CreateOrder

# Get order
grpcurl -plaintext -d '{
  "order_id": "your-order-id"
}' localhost:50051 hybrid_order_service.HybridOrderService/GetOrder

# Batch get orders
grpcurl -plaintext -d '{
  "order_ids": ["order-1", "order-2"]
}' localhost:50051 hybrid_order_service.HybridOrderService/BatchGetOrders

# Health check
grpcurl -plaintext localhost:50051 hybrid_order_service.HybridOrderService/HealthCheck
```

## Architecture Benefits

### REST API Benefits

- **Human-readable** JSON format
- **Web browser compatible**
- **Easy debugging** with curl/Postman
- **Wide client library support**
- **Cacheable** with HTTP caching

### gRPC Benefits

- **High performance** binary serialization
- **Type safety** with Protocol Buffers
- **Streaming support** for real-time data
- **Language agnostic** client generation
- **Built-in load balancing**

### Hybrid Benefits

- **Protocol flexibility** - choose the right tool
- **Migration path** - transition between protocols
- **Client preferences** - serve different client types
- **Performance optimization** - gRPC for internal, REST for external

## When to Use Each Protocol

### Use REST when

- Building web frontends
- Integrating with third-party services
- Need human-readable debugging
- Caching is important
- Simple request/response patterns

### Use gRPC when

- High-performance internal communication
- Real-time streaming requirements
- Strong typing is critical
- Multiple programming languages
- Microservices mesh communication

## Production Considerations

1. **Generate Real Protobuf Code:**

   ```bash
   python -m grpc_tools.protoc --proto_path=proto --python_out=proto --grpc_python_out=proto proto/hybrid_order_service.proto
   ```

2. **Load Balancing:**
   - Use nginx/envoy for REST traffic
   - Use gRPC load balancers for gRPC traffic

3. **Service Discovery:**
   - Register both protocols in service registry
   - Different ports for different protocols

4. **Monitoring:**
   - Separate metrics for each protocol
   - Protocol-specific health checks

5. **Security:**
   - TLS for both protocols
   - Authentication middleware/interceptors

## Customization

To adapt this template:

1. Replace `InMemoryOrderRepository` with your database adapter
2. Configure external service connections
3. Add authentication for both protocols
4. Extend domain models and API definitions
5. Add protocol-specific middleware/interceptors
6. Configure production-grade servers (gunicorn, etc.)

## File Structure

```
hybrid_example/
├── domain/           # Business logic (shared)
├── application/      # Application services (shared)
├── infrastructure/   # Adapters (shared)
├── proto/           # Protocol buffer definitions
├── main.py          # Server implementations
└── requirements.txt # Dependencies
```

This hybrid approach gives you the flexibility to serve different clients with the most appropriate protocol while maintaining a single source of business logic.
