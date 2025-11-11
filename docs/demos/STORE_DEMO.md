# Marty Microservices Framework - Store Demo

## Overview

The Store Demo is a comprehensive microservices demonstration showcasing the Marty Microservices Framework (MMF) capabilities in a realistic e-commerce scenario. This demo simulates an online store with order processing, payment handling, and inventory management services.

## Architecture

### Services

1. **Order Service** (Port 8001)
   - Handles order creation and processing
   - Manages order state transitions
   - Includes audit logging and distributed tracing
   - Deliberately includes performance bottlenecks for testing

2. **Payment Service** (Port 8002)
   - Processes payment transactions
   - Includes fraud detection simulation
   - Contains artificial delays to simulate real-world processing
   - Returns appropriate error responses for testing

3. **Inventory Service** (Port 8003)
   - Manages product inventory
   - Handles stock validation and updates
   - Includes realistic business logic for stock management

4. **Demo Runner**
   - Orchestrates load testing across all services
   - Provides analytics and performance reporting
   - Supports both local and Docker environments

### Observability Stack

- **Prometheus** (Port 9090): Metrics collection
- **Grafana** (Port 3000): Dashboard and visualization

## Performance Characteristics

Based on extensive testing, the demo achieves:

- **Success Rate**: 63-70% (intentionally includes failures for realistic testing)
- **Response Time**: ~1.8 seconds average
- **Bottleneck**: Payment service (as designed)
- **Concurrent Processing**: Fully async with proper error handling

## Quick Start

### Docker Compose (Recommended)

1. **Navigate to the store demo:**

   ```bash
   cd examples/store-demo
   ```

2. **Start the complete stack:**

   ```bash
   docker compose up -d
   ```

3. **Run the demo:**

   ```bash
   docker compose exec demo-runner python /app/mmf_demo_runner.py
   ```

4. **View results:**
   - Reports: `./reports/` (JSON and text files)
   - Prometheus: <http://localhost:9090>
   - Grafana: <http://localhost:3000>

### Local Development

1. **Install dependencies:**

   ```bash
   uv sync
   ```

2. **Start services (separate terminals):**

   ```bash
   # Terminal 1 - Order Service
   python examples/store-demo/services/mmf_order_service.py

   # Terminal 2 - Payment Service
   python examples/store-demo/services/mmf_payment_service.py

   # Terminal 3 - Inventory Service
   python examples/store-demo/services/mmf_inventory_service.py
   ```

3. **Run demo:**

   ```bash
   python examples/store-demo/mmf_demo_runner.py
   ```

## Service Endpoints

### Order Service (<http://localhost:8001>)

- `GET /health` - Health check
- `POST /orders` - Create new order
- `GET /orders/{order_id}` - Get order status
- `GET /metrics` - Prometheus metrics

### Payment Service (<http://localhost:8002>)

- `GET /health` - Health check
- `POST /payments` - Process payment
- `GET /payments/{payment_id}` - Get payment status
- `GET /metrics` - Prometheus metrics

### Inventory Service (<http://localhost:8003>)

- `GET /health` - Health check
- `POST /inventory/reserve` - Reserve inventory
- `POST /inventory/confirm` - Confirm reservation
- `POST /inventory/release` - Release reservation
- `GET /inventory/{product_id}` - Get product inventory
- `GET /metrics` - Prometheus metrics

## Demo Configuration

The demo runner supports various configuration options:

```python
# Default configuration
DEMO_CONFIG = {
    "num_orders": 100,
    "concurrent_requests": 10,
    "delay_between_batches": 0.1,
    "request_timeout": 30.0
}
```

### Environment Variables

- `DOCKER_ENV`: Set to `true` when running in Docker
- `DEMO_REPORTS_DIR`: Directory for storing reports (default: `./demo_reports`)

## Understanding the Results

### Success Metrics

- **Order Created**: Order successfully submitted
- **Payment Processed**: Payment completed (success or handled failure)
- **Inventory Updated**: Stock levels properly managed
- **Full Success**: Complete transaction flow successful

### Expected Failure Modes

The demo intentionally includes realistic failure scenarios:

1. **Payment Failures** (~30%): Simulated card declines, fraud detection
2. **Inventory Issues** (~10%): Out of stock, reservation conflicts
3. **Network Timeouts** (~5%): Realistic network delays
4. **Service Errors** (~2%): Temporary service unavailability

### Performance Bottlenecks

- **Payment Service**: Artificial 1-2 second delays (fraud checks)
- **Order Processing**: Complex validation logic
- **Database Operations**: Simulated DB transaction delays

## Monitoring and Observability

### Prometheus Metrics

All services expose `/metrics` endpoints with:

- Request counters and histograms
- Error rates by type
- Service-specific business metrics
- System resource usage

### Grafana Dashboards

Pre-configured dashboards available for:

- Service overview and health
- Request rates and latencies
- Error analysis
- Business metrics (orders, payments, inventory)

### Distributed Tracing

- Full request tracing across all services
- Correlation IDs for transaction tracking
- Performance profiling and bottleneck identification

## Troubleshooting

### Common Issues

1. **Port Conflicts**

   ```bash
   # Check if ports are in use
   lsof -i :8001 -i :8002 -i :8003 -i :9090 -i :3000
   ```

2. **Docker Issues**

   ```bash
   # Rebuild containers
   docker compose down
   docker compose build --no-cache
   docker compose up
   ```

3. **Low Success Rates**
   - Expected: 63-70% success rate
   - If lower: Check service logs for errors
   - If higher: Reduce concurrent requests

### Service Health Checks

```bash
# Check all services
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

### Logs

```bash
# Docker logs (from examples/store-demo directory)
docker compose logs order-service
docker compose logs payment-service
docker compose logs inventory-service

# Or all services
docker compose logs -f
```

## Development Notes

### Framework Features Demonstrated

1. **Plugin Architecture**: Analytics plugin for performance monitoring
2. **Async Processing**: Non-blocking concurrent request handling
3. **Error Handling**: Comprehensive error categorization and response
4. **Metrics Collection**: Prometheus integration with custom metrics
5. **Health Monitoring**: Structured health check endpoints
6. **Configuration Management**: Environment-based configuration
7. **Containerization**: Full Docker support with health checks

### Code Organization

```
examples/store-demo/
├── README.md                    # Store demo documentation
├── docker-compose.yml           # Complete orchestration setup
├── mmf_demo_runner.py          # Demo orchestration and testing
├── mmf_analytics_plugin.py     # Analytics and reporting plugin
├── services/                   # Microservices
│   ├── mmf_order_service.py    # Order service implementation
│   ├── mmf_payment_service.py  # Payment service implementation
│   └── mmf_inventory_service.py # Inventory service implementation
├── docker/                     # Docker configuration
│   ├── Dockerfile.order        # Order service container
│   ├── Dockerfile.payment      # Payment service container
│   ├── Dockerfile.inventory    # Inventory service container
│   └── Dockerfile.demo         # Demo runner container
└── monitoring/                 # Observability configuration
    └── prometheus.yml          # Prometheus metrics config
```

### Testing Strategy

The demo serves as both a demonstration and a test suite:

- **Load Testing**: Concurrent request processing
- **Error Handling**: Various failure scenarios
- **Performance Testing**: Bottleneck identification
- **Integration Testing**: Service-to-service communication

## Next Steps

1. **Custom Configuration**: Modify demo parameters for specific testing needs
2. **Extended Monitoring**: Add custom Grafana dashboards
3. **Load Scenarios**: Create different load testing profiles
4. **Service Extensions**: Add new services to the demo ecosystem

## Related Documentation

- [Framework Architecture](architecture.md)
- [Development Guide](development/README.md)
- [Deployment Guide](guides/deployment.md)
- [Monitoring Setup](../observability/README.md)
