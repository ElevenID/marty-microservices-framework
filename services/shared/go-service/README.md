# {{ service_name }}

{{ service_description }}

## Features

- **Enterprise-grade Go microservice** with Gin web framework
- **Comprehensive logging** with structured JSON logging via Logrus
- **Security** with JWT authentication, CORS, rate limiting, and security headers
- **Monitoring** with Prometheus metrics and health checks
- **Configuration** via environment variables with sensible defaults
{{- if include_database }}
- **Database support** with PostgreSQL and GORM ORM
{{- endif }}
{{- if include_redis }}
- **Redis integration** for caching and session storage
{{- endif }}
- **Graceful shutdown** with proper cleanup
- **Docker support** with multi-stage builds
- **Request tracing** with unique request IDs
- **Input validation** with Gin's built-in validators

## Quick Start

### Prerequisites

- Go 1.21 or later
{{- if include_database }}
- PostgreSQL (if using database features)
{{- endif }}
{{- if include_redis }}
- Redis (if using caching features)
{{- endif }}

### Installation

1. **Clone or generate the service:**

   ```bash
   # If using Marty CLI
   marty create {{ service_name }} --template=go-service

   # Or clone manually
   git clone <repository-url>
   cd {{ service_name }}
   ```

2. **Install dependencies:**

   ```bash
   go mod tidy
   ```

3. **Configuration:**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the service:**

   ```bash
   # Development
   go run ./cmd/server

   # Or build and run
   go build -o bin/{{ service_name }} ./cmd/server
   ./bin/{{ service_name }}
   ```

### Docker

```bash
# Build image
docker build -t {{ service_name }} .

# Run container
docker run -p {{ port }}:{{ port }} --env-file .env {{ service_name }}
```

## API Documentation

### Base URL

```
http://localhost:{{ port }}
```

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "service": "{{ service_name }}",
  "version": "1.0.0",
  "checks": {
    {{- if include_database }}
    "database": {"status": "healthy"},
    {{- endif }}
    {{- if include_redis }}
    "redis": {"status": "healthy"}
    {{- endif }}
  }
}
```

### Metrics

```http
GET /metrics
```

Prometheus metrics endpoint for monitoring.

### API Endpoints

#### Root

```http
GET /api/v1/
```

#### Ping

```http
GET /api/v1/ping
```

{{- if include_auth }}

#### Authentication

##### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

##### Register

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password",
  "name": "User Name"
}
```

##### Get Profile (Protected)

```http
GET /api/v1/profile
Authorization: Bearer <jwt-token>
```

{{- endif }}

## Configuration

The service can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `PORT` | Server port | `{{ port }}` |
| `LOG_LEVEL` | Log level (debug/info/warn/error) | `info` |
{{- if include_database }}
| `DATABASE_HOST` | Database host | `localhost` |
| `DATABASE_PORT` | Database port | `5432` |
| `DATABASE_USER` | Database user | `postgres` |
| `DATABASE_PASSWORD` | Database password | `password` |
| `DATABASE_NAME` | Database name | `{{ service_name }}` |
{{- endif }}
{{- if include_redis }}
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
{{- endif }}
{{- if include_auth }}
| `JWT_SECRET` | JWT signing secret | `your-secret-key` |
| `JWT_EXPIRES_IN` | JWT expiration time | `24h` |
{{- endif }}
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `RATE_LIMIT` | Requests per minute | `100` |

## Project Structure

```
{{ service_name }}/
├── cmd/
│   └── server/          # Application entrypoint
├── internal/
│   ├── app/            # Application setup and configuration
│   ├── config/         # Configuration management
│   ├── handlers/       # HTTP handlers
│   ├── middleware/     # HTTP middleware
│   ├── logger/         # Logging utilities
{{- if include_database }}
│   ├── database/       # Marty database framework integration
{{- endif }}
{{- if include_redis }}
│   └── redis/          # Redis client
{{- endif }}
├── pkg/                # Public packages (if any)
├── .env.example        # Environment variables template
├── Dockerfile          # Docker configuration
├── go.mod              # Go modules
└── README.md          # This file
```

{{- if include_database }}

## Database Architecture

This service follows Marty's enterprise database patterns for service isolation and clean architecture:

### Service-Specific Database Isolation

Each service uses its own dedicated database following the naming convention:

- Database name: `{service_name}_db`
- Automatic configuration based on `SERVICE_NAME` environment variable
- No direct GORM connections - all access through DatabaseManager

### Database Abstraction Layer

The service uses Marty's database framework patterns:

#### DatabaseManager (Singleton)

- Thread-safe singleton implementation
- Manages GORM connection and health checks
- Provides service-specific database isolation
- Handles connection lifecycle and recovery

#### Configuration Management

- Environment-based configuration with validation
- Service-specific database naming
- Connection pool settings
- Health check intervals

### Usage Example

```go
package main

import (
    "{{ module_name }}/internal/database"
    "{{ module_name }}/internal/config"
    "{{ module_name }}/internal/logger"
)

// Get singleton instance
dbManager, err := database.GetInstance("my-service", cfg, log)
if err != nil {
    log.Fatal("Failed to initialize database", err)
}

// Get GORM DB instance
db := dbManager.GetDB()

// Use GORM for operations
var users []User
db.Find(&users)

// Health check
if err := dbManager.HealthCheck(); err != nil {
    log.Error("Database health check failed", err)
}
```

### Environment Variables

```env
SERVICE_NAME={{ service_name }}
DATABASE_URL=postgresql://user:password@localhost:5432/{{ service_name }}_db
DATABASE_POOL_MAX_OPEN_CONNS=25
DATABASE_POOL_MAX_IDLE_CONNS=5
DATABASE_CONN_MAX_LIFETIME=300s
```

{{- endif }}

## Development

### Running Tests

```bash
go test ./...
```

### Building

```bash
# Build for current platform
go build -o bin/{{ service_name }} ./cmd/server

# Build for Linux
GOOS=linux GOARCH=amd64 go build -o bin/{{ service_name }}-linux ./cmd/server
```

### Adding New Routes

1. Create handler functions in `internal/handlers/`
2. Add routes in `internal/app/app.go` in the `setupRoutes()` method
3. Add middleware if needed in `internal/middleware/`

### Database Migrations

{{- if include_database }}
Database migrations should be handled in `internal/database/migrations.go` or using a dedicated migration tool.
{{- else }}
Not applicable - database support not included.
{{- endif }}

## Monitoring

The service exposes several monitoring endpoints:

- **Health Check**: `/health` - Service health status
- **Metrics**: `/metrics` - Prometheus metrics
- **Request IDs**: Every request gets a unique ID for tracing

### Key Metrics

- `http_requests_total` - Total number of HTTP requests
- `http_request_duration_seconds` - Request duration histogram

## Security

The service implements several security best practices:

- **JWT Authentication** (if enabled)
- **CORS** with configurable origins
- **Rate Limiting** to prevent abuse
- **Security Headers** (XSS protection, frame options, etc.)
- **Input Validation** using Gin validators
- **Secure defaults** in production mode

## Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  {{ service_name }}:
    build: .
    ports:
      - "{{ port }}:{{ port }}"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=info
    {{- if include_database }}
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: {{ service_name }}
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    {{- endif }}
    {{- if include_redis }}

  redis:
    image: redis:7-alpine
    {{- endif }}
```

### Kubernetes

Use the provided Kubernetes manifests or Helm charts for deployment.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

{{ author }}

---

Generated with [Marty Microservices Framework](https://github.com/your-org/marty-microservices-framework)
