# Morty Service - Hexagonal Architecture Reference Implementation

The Morty service is a reference implementation of hexagonal (ports & adapters) architecture using the Marty Chassis framework. It demonstrates how to build maintainable, testable microservices with proper separation of concerns.

## Architecture Overview

The service follows hexagonal architecture principles with three distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  HTTP Adapter   │  │ Database Adapter│  │  Event Adapter  │ │
│  │   (FastAPI)     │  │  (SQLAlchemy)   │  │    (Kafka)      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                           │                         │
                           ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Input Ports   │  │   Use Cases     │  │  Output Ports   │ │
│  │  (Interfaces)   │  │ (Orchestrators) │  │  (Interfaces)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DOMAIN LAYER                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    Entities     │  │ Value Objects   │  │ Domain Services │ │
│  │   (Task, User)  │  │ (Email, Name)   │  │   (Business)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Pure Domain Layer**: Business logic independent of external concerns
- **Dependency Inversion**: Application depends on abstractions, not implementations
- **Port & Adapter Pattern**: Clear boundaries between layers
- **Event-Driven Architecture**: Domain events for loose coupling
- **Comprehensive Testing**: Each layer can be tested in isolation
- **Configuration Management**: Environment-based configuration
- **Observability**: Built-in logging, metrics, and health checks

## Directory Structure

```
service/morty_service/
├── domain/                     # Core business logic
│   ├── entities.py            # Domain entities (Task, User)
│   ├── value_objects.py       # Value objects (Email, PersonName)
│   ├── events.py              # Domain events
│   └── services.py            # Domain services
├── application/               # Use cases and ports
│   ├── ports/
│   │   ├── input_ports.py     # Interfaces for external interaction
│   │   └── output_ports.py    # Interfaces for infrastructure
│   └── use_cases.py          # Application use cases
├── infrastructure/           # External adapters
│   └── adapters/
│       ├── http_adapter.py    # REST API implementation
│       ├── database_adapters.py # Database persistence
│       ├── event_adapters.py  # Event publishing/notifications
│       └── models.py          # Database models
└── main.py                   # Service entry point
```

## Domain Layer

### Entities

- **Task**: Represents a work item with business rules
- **User**: Represents a person who can be assigned tasks

### Value Objects

- **Email**: Email address with validation
- **PersonName**: First and last name combination
- **PhoneNumber**: Phone number with normalization

### Domain Services

- **TaskManagementService**: Business logic for task operations
- **UserManagementService**: Business logic for user operations

### Domain Events

- **TaskCreated**: When a new task is created
- **TaskAssigned**: When a task is assigned to a user
- **TaskCompleted**: When a task is marked as completed

## Application Layer

### Input Ports (Interfaces)

- **TaskManagementPort**: Task operations interface
- **UserManagementPort**: User operations interface
- **HealthCheckPort**: Health check interface

### Output Ports (Interfaces)

- **TaskRepositoryPort**: Task persistence interface
- **UserRepositoryPort**: User persistence interface
- **EventPublisherPort**: Event publishing interface
- **NotificationPort**: Notification sending interface
- **CachePort**: Caching operations interface
- **UnitOfWorkPort**: Transaction management interface

### Use Cases

- **TaskManagementUseCase**: Orchestrates task-related workflows
- **UserManagementUseCase**: Orchestrates user-related workflows

## Infrastructure Layer

### Input Adapters

- **HTTPAdapter**: FastAPI-based REST API
- Future: gRPC adapter, CLI adapter, etc.

### Output Adapters

- **SQLAlchemyTaskRepository**: PostgreSQL task persistence
- **SQLAlchemyUserRepository**: PostgreSQL user persistence
- **KafkaEventPublisher**: Event publishing via Kafka
- **EmailNotificationService**: Email notifications
- **RedisCache**: Redis-based caching

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis (optional)
- Kafka (optional)

### Installation

1. Install the Marty Chassis framework:

```bash
pip install marty-chassis
```

2. Set up the database:

```bash
# Create database
createdb morty_dev

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/morty_dev"
export REDIS_URL="redis://localhost:6379"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
```

3. Run the service:

```bash
python -m service.morty_service.main
```

### API Endpoints

#### Tasks

- `POST /api/v1/tasks` - Create a new task
- `GET /api/v1/tasks/{id}` - Get a task by ID
- `PUT /api/v1/tasks/{id}` - Update a task
- `POST /api/v1/tasks/{id}/assign` - Assign task to user
- `POST /api/v1/tasks/{id}/complete` - Mark task as completed
- `GET /api/v1/tasks` - List tasks with filters
- `DELETE /api/v1/tasks/{id}` - Delete a task

#### Users

- `POST /api/v1/users` - Create a new user
- `GET /api/v1/users/{id}` - Get a user by ID
- `GET /api/v1/users` - List all users
- `POST /api/v1/users/{id}/activate` - Activate a user
- `POST /api/v1/users/{id}/deactivate` - Deactivate a user
- `GET /api/v1/users/{id}/workload` - Get user workload info
- `DELETE /api/v1/users/{id}` - Delete a user

#### Health

- `GET /health` - Health check
- `GET /ready` - Readiness check

## Configuration

The service uses the Marty Chassis configuration system. Environment variables:

```bash
# Service configuration
SERVICE_NAME=morty-service
SERVICE_VERSION=1.0.0
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8080

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/morty_dev

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Kafka (optional)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Email (optional)
EMAIL_FROM=morty@company.com
SMTP_HOST=smtp.company.com
SMTP_PORT=587

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Testing

The hexagonal architecture makes testing straightforward:

### Domain Testing

```python
# Test domain entities and services in isolation
def test_task_creation():
    task = Task("Test Task", "Description", priority="high")
    assert task.title == "Test Task"
    assert task.priority == "high"
```

### Application Testing

```python
# Test use cases with mock adapters
async def test_create_task_use_case():
    mock_repository = MockTaskRepository()
    use_case = TaskManagementUseCase(mock_repository, ...)

    command = CreateTaskCommand("Test", "Description")
    result = await use_case.create_task(command)

    assert result.title == "Test"
```

### Integration Testing

```python
# Test with real adapters but test database
async def test_task_api():
    async with TestClient(app) as client:
        response = await client.post("/api/v1/tasks", json={
            "title": "Test Task",
            "description": "Test Description"
        })
        assert response.status_code == 201
```

## Benefits of Hexagonal Architecture

1. **Testability**: Each layer can be tested independently
2. **Flexibility**: Easy to swap implementations (e.g., database, message queue)
3. **Maintainability**: Clear separation of concerns
4. **Domain Focus**: Business logic is protected from technical concerns
5. **Technology Independence**: Domain doesn't depend on frameworks
6. **Scalability**: Components can be deployed and scaled independently

## Framework Integration

The Morty service demonstrates how the Marty Chassis provides:

- **Dependency Injection**: Automatic wiring of adapters and use cases
- **Configuration Management**: Environment-based configuration
- **Cross-cutting Concerns**: Logging, metrics, health checks
- **Service Factory**: Simplified service creation with `create_hexagonal_service()`
- **Adapter Implementations**: Pre-built adapters for common patterns

## Extension Points

To extend the service:

1. **Add New Domain Logic**: Create new entities, value objects, or domain services
2. **Add New Use Cases**: Implement new input ports and use case classes
3. **Add New Adapters**: Implement output ports for new infrastructure
4. **Add New APIs**: Create additional input adapters (gRPC, GraphQL, etc.)

## Best Practices

1. **Keep Domain Pure**: No external dependencies in domain layer
2. **Use Value Objects**: For data that has validation or behavior
3. **Emit Domain Events**: For significant business events
4. **Test Each Layer**: Unit tests for domain, integration tests for adapters
5. **Use Dependency Injection**: Let the chassis wire dependencies
6. **Follow Port Contracts**: Ensure adapters implement port interfaces correctly

This implementation serves as a reference for building robust, maintainable microservices using hexagonal architecture principles with the Marty Chassis framework.
