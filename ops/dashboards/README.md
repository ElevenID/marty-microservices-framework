# Marty Dashboard

A comprehensive management dashboard for the Marty Microservices Framework.

## Features

- **Service Discovery & Monitoring**: Automatically discover and monitor microservices
- **Real-time Metrics**: Collect and visualize service metrics with Prometheus integration
- **Health Monitoring**: Track service health with customizable health checks
- **Configuration Management**: Centralized configuration management for all services
- **Alert Management**: Create and manage alerts for system events
- **RESTful API**: Full REST API for programmatic access
- **Modern Web UI**: React-based dashboard with real-time updates

## Architecture

The dashboard consists of two main components:

### Backend (FastAPI)

- **FastAPI** web framework with async support
- **PostgreSQL** database for data persistence
- **Redis** for caching and real-time features
- **Prometheus** metrics collection
- **WebSocket** support for real-time updates
- **JWT** authentication and authorization

### Frontend (React)

- **React** with TypeScript for type safety
- **TailwindCSS** for modern styling
- **React Query** for efficient data fetching
- **React Router** for navigation
- **Recharts** for data visualization
- **WebSocket** client for real-time updates

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL 12+
- Redis 6+

### Backend Setup

1. **Install dependencies:**

   ```bash
   cd backend
   pip install -e .
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Initialize database:**

   ```bash
   marty-dashboard init
   ```

4. **Start the server:**

   ```bash
   marty-dashboard serve --reload
   ```

### Frontend Setup

1. **Install dependencies:**

   ```bash
   cd frontend
   npm install
   ```

2. **Start development server:**

   ```bash
   npm run dev
   ```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## Usage

### Web Interface

Access the dashboard at `http://localhost:3000` for the complete web interface.

### CLI Commands

```bash
# Register a service
marty-dashboard register my-service localhost 8080 --health-url http://localhost:8080/health

# List services
marty-dashboard list-services

# Deregister a service
marty-dashboard deregister my-service
```

### API Endpoints

The REST API is available at `http://localhost:8000/api`

- **Services**: `/api/services` - Manage service registration
- **Metrics**: `/api/metrics` - Retrieve service metrics
- **Config**: `/api/config` - Manage configurations
- **Alerts**: `/api/alerts` - Handle alerts
- **Auth**: `/api/auth` - Authentication endpoints

### Service Integration

To integrate your services with the dashboard:

1. **Health Check Endpoint**: Implement a `/health` endpoint
2. **Metrics Endpoint**: Expose Prometheus metrics at `/metrics`
3. **Registration**: Register your service via API or CLI

Example service registration:

```python
import httpx

async def register_with_dashboard():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://dashboard:8000/api/services/register",
            json={
                "name": "my-service",
                "address": "localhost",
                "port": 8080,
                "health_check_url": "http://localhost:8080/health",
                "tags": ["api", "production"],
                "metadata": {"version": "1.0.0"}
            }
        )
        return response.status_code == 200
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:password@localhost:5432/marty_dashboard` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | Application secret key | `your-secret-key-change-in-production` |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |
| `JWT_SECRET` | JWT signing secret | `jwt-secret-change-in-production` |
| `DEBUG` | Enable debug mode | `false` |

### Service Configuration

Services can be configured through the dashboard UI or API:

```json
{
  "service_name": "my-service",
  "config_key": "database.connection_pool_size",
  "config_value": "10",
  "environment": "production",
  "is_secret": false
}
```

## Monitoring & Alerts

### Metrics Collection

The dashboard automatically collects metrics from services that expose Prometheus metrics:

- HTTP request metrics
- System resource usage
- Custom application metrics
- Service health status

### Alert Rules

Configure alerts based on:

- Service health status
- Metric thresholds
- Service registration/deregistration
- Custom conditions

## Development

### Backend Development

```bash
cd backend

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black .
isort .

# Type checking
mypy .
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Run linting
npm run lint

# Type checking
npm run type-check

# Build for production
npm run build
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## Deployment

### Production Deployment

1. **Docker Compose** (Recommended):

   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Kubernetes**:

   ```bash
   kubectl apply -f k8s/
   ```

3. **Manual Deployment**:
   - Build frontend: `npm run build`
   - Install backend: `pip install .`
   - Configure environment variables
   - Run with production ASGI server: `gunicorn -k uvicorn.workers.UvicornWorker marty_dashboard.main:app`

### Environment-Specific Configuration

- **Development**: `.env.development`
- **Testing**: `.env.testing`
- **Production**: `.env.production`

## Security

The dashboard implements several security best practices:

- **Authentication**: JWT-based authentication
- **Authorization**: Role-based access control
- **HTTPS**: TLS encryption for production
- **CORS**: Configurable cross-origin resource sharing
- **Rate Limiting**: API rate limiting to prevent abuse
- **Input Validation**: Comprehensive input validation
- **Security Headers**: Standard security headers

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- **Documentation**: [Link to docs]
- **Issues**: [GitHub Issues]
- **Community**: [Discord/Slack]

---

Built with ❤️ by the Marty Team
