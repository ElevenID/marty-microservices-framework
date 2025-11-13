# {{ service_name }}

{{ service_description }}

Enterprise-grade Node.js microservice built with the Marty Microservices Framework.

## Features

- **Express.js with TypeScript** - Type-safe modern web framework
- **Enterprise Security** - Helmet, CORS, rate limiting, input validation
- **Monitoring & Observability** - Prometheus metrics, structured logging
- **API Documentation** - Swagger/OpenAPI integration{% if include_auth %}
- **JWT Authentication** - Secure token-based authentication{% endif %}{% if include_database %}
- **Database Integration** - PostgreSQL with Knex.js ORM{% endif %}{% if include_redis %}
- **Redis Caching** - High-performance caching layer{% endif %}
- **Health Checks** - Comprehensive health monitoring
- **Docker Support** - Multi-stage containerization
- **Testing** - Jest with supertest for API testing
- **Code Quality** - ESLint, TypeScript strict mode

## Quick Start

### Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0{% if include_database %}
- PostgreSQL{% endif %}{% if include_redis %}
- Redis{% endif %}

### Installation

```bash
# Install dependencies
npm install

# Build the application
npm run build

# Start development server
npm run dev

# Start production server
npm start
```

### Environment Variables

Create a `.env` file in the root directory:

```env
NODE_ENV=development
PORT={{ port }}
LOG_LEVEL=info

# Database{% if include_database %}
DATABASE_URL=postgresql://user:password@localhost:5432/{{ service_name }}{% endif %}

# Redis{% if include_redis %}
REDIS_URL=redis://localhost:6379{% endif %}

# Authentication{% if include_auth %}
JWT_SECRET=your-super-secret-jwt-key
JWT_EXPIRES_IN=24h{% endif %}

# Security
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

## API Endpoints

### Core Endpoints

- `GET /` - Service information
- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus metrics
- `GET /docs` - API documentation{% if include_auth %}

### Authentication

- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/profile` - Get user profile{% endif %}

### API Routes

- `GET /api/status` - API status
- `GET /api/version` - API version

## Development

### Scripts

```bash
# Development
npm run dev          # Start with hot reload
npm run build        # Build for production
npm run start        # Start production server

# Testing
npm test             # Run tests
npm run test:coverage # Run tests with coverage

# Code Quality
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues

# Docker
npm run docker:build # Build Docker image
npm run docker:run   # Run Docker container
```

### Project Structure

```
src/
├── app.ts              # Express application setup
├── server.ts           # Server startup and shutdown
├── config/             # Configuration management
│   ├── config.ts       # Environment configuration
│   ├── logger.ts       # Winston logger setup{% if include_database %}
│   └── swagger.ts      # Swagger documentation
├── database/           # Marty database framework integration
│   ├── config.ts       # Database configuration with service isolation
│   ├── manager.ts      # DatabaseManager singleton following Marty patterns
│   ├── repository.ts   # BaseRepository with transaction support
│   └── index.ts        # Database exports{% endif %}{% if include_redis %}
├── redis.ts            # Redis connection{% endif %}
├── middleware/         # Custom middleware
│   ├── auth.ts         # Authentication middleware
│   ├── errorHandler.ts # Error handling
│   ├── logger.ts       # Request logging
│   └── metrics.ts      # Prometheus metrics
├── routes/             # Route handlers
│   ├── api.ts          # API routes{% if include_auth %}
│   ├── auth.ts         # Authentication routes{% endif %}
│   └── health.ts       # Health check routes
├── types/              # TypeScript type definitions
└── utils/              # Utility functions
```

{% if include_database %}

## Database Architecture

This service follows Marty's enterprise database patterns for service isolation and clean architecture:

### Service-Specific Database Isolation

Each service uses its own dedicated database following the naming convention:

- Database name: `{service_name}_db`
- Automatic configuration based on `SERVICE_NAME` environment variable
- No direct database connections - all access through DatabaseManager

### Database Abstraction Layer

The service uses Marty's database framework patterns:

#### DatabaseManager (Singleton)

- Manages connection pooling and health checks
- Provides service-specific database isolation
- Handles connection lifecycle and error recovery

#### BaseRepository Pattern

- Provides standard CRUD operations
- Transaction management and rollback support
- Type-safe database operations
- Consistent error handling

#### Configuration Management

- Environment-based configuration
- Service-specific database naming
- Connection pool settings
- Health check intervals

### Usage Example

```typescript
import { DatabaseManager } from './database';

// Get singleton instance
const dbManager = DatabaseManager.getInstance();

// Use repository pattern
const userRepo = dbManager.getRepository('users');
const users = await userRepo.findAll();

// Transaction support
await dbManager.transaction(async (trx) => {
  await userRepo.create(userData, trx);
  await auditRepo.log(auditData, trx);
});
```

### Environment Variables

```env
SERVICE_NAME={{ service_name }}
DATABASE_URL=postgresql://user:password@localhost:5432/{{ service_name }}_db
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=10
DATABASE_TIMEOUT=30000
```

{% endif %}

## Monitoring

### Health Checks

The service provides comprehensive health checks at `/health`:

```json
{
  "status": "healthy",
  "timestamp": "2023-10-09T12:00:00.000Z",
  "uptime": 3600,
  "memory": {
    "used": "45.2 MB",
    "free": "982.8 MB"
  },{% if include_database %}
  "database": "connected",{% endif %}{% if include_redis %}
  "redis": "connected",{% endif %}
  "version": "1.0.0"
}
```

### Metrics

Prometheus metrics are exposed at `/metrics`:

- `http_request_duration_seconds` - Request duration histogram
- `http_requests_total` - Total request counter
- `http_request_errors_total` - Error counter
- `nodejs_*` - Node.js runtime metrics

## Security

### Built-in Security Features

- **Helmet.js** - Security headers
- **CORS** - Cross-origin resource sharing
- **Rate Limiting** - Request rate limiting
- **Input Validation** - Request validation{% if include_auth %}
- **JWT Authentication** - Secure token authentication{% endif %}
- **Error Handling** - Secure error responses

### Security Headers

The service automatically sets security headers:

- Content Security Policy
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy

## Docker

### Build Image

```bash
docker build -t {{ service_name }} .
```

### Run Container

```bash
docker run -p {{ port }}:{{ port }} {{ service_name }}
```

### Docker Compose

```yaml
version: '3.8'
services:
  {{ service_name }}:
    build: .
    ports:
      - "{{ port }}:{{ port }}"
    environment:
      - NODE_ENV=production{% if include_database %}
      - DATABASE_URL=postgresql://user:password@db:5432/{{ service_name }}{% endif %}{% if include_redis %}
      - REDIS_URL=redis://redis:6379{% endif %}{% if include_database %}

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: {{ service_name }}
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password{% endif %}{% if include_redis %}

  redis:
    image: redis:7-alpine{% endif %}
```

## Testing

Run the test suite:

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- health.test.ts
```

## License

MIT License - see LICENSE file for details

## Support

For questions and support, please refer to the [Marty Framework Documentation](https://marty-msf.readthedocs.io).
