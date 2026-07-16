# Core Framework Migration Guide

## Overview

The new core framework provides foundational components for building microservices using hexagonal (ports and adapters) architecture. This guide shows how to migrate existing services and create new ones using the framework.

## Core Components

### 1. Domain Layer

#### Entity Base Class

```python
from mmf.core.domain.entity import Entity, AggregateRoot
from uuid import UUID
from datetime import datetime

class User(Entity):
    def __init__(self, username: str, email: str, entity_id: UUID = None):
        super().__init__(entity_id)
        self.username = username
        self.email = email

    def change_email(self, new_email: str) -> None:
        self.email = new_email
        self.mark_updated()
```

#### Repository Interface

```python
from mmf.core.domain.repository import Repository
from uuid import UUID

class UserRepository(Repository[User]):
    """User repository interface."""

    async def find_by_username(self, username: str) -> User | None:
        """Find user by username."""
        ...

    async def find_by_email(self, email: str) -> User | None:
        """Find user by email."""
        ...
```

### 2. Application Layer

#### Use Cases

```python
from mmf.core.application.base import UseCase, ValidationError
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    username: str
    email: str

@dataclass
class CreateUserResponse:
    user_id: str
    username: str
    email: str

class CreateUserUseCase(UseCase[CreateUserRequest, CreateUserResponse]):
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(self, request: CreateUserRequest) -> CreateUserResponse:
        # Validate request
        if not request.username or not request.email:
            raise ValidationError("Username and email are required")

        # Check if user already exists
        existing_user = await self.user_repository.find_by_username(request.username)
        if existing_user:
            raise ValidationError("Username already exists")

        # Create new user
        user = User(username=request.username, email=request.email)
        saved_user = await self.user_repository.save(user)

        return CreateUserResponse(
            user_id=str(saved_user.id),
            username=saved_user.username,
            email=saved_user.email
        )
```

### 3. Infrastructure Layer

#### Database Configuration

```python
from mmf.framework.infrastructure.database import DatabaseConfig
from mmf.framework.infrastructure.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Configure database
config = DatabaseConfig(
    service_name="user-service",
    database_url="postgresql+asyncpg://user:pass@localhost/userdb",  # pragma: allowlist secret
    pool_size=5,
    max_overflow=10,
    echo=False
)

# Create database manager
db_manager = SQLAlchemyDatabaseManager(config)
await db_manager.initialize()
```

#### Repository Implementation

```python
from mmf.framework.infrastructure.sqlalchemy_manager import SQLAlchemyDatabaseManager
from sqlalchemy import select

class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, db_manager: SQLAlchemyDatabaseManager):
        self.db_manager = db_manager

    async def save(self, entity: User) -> User:
        async with self.db_manager.get_transaction() as session:
            # Convert domain entity to SQLAlchemy model
            user_model = UserModel(
                id=entity.id,
                username=entity.username,
                email=entity.email,
                created_at=entity.created_at,
                updated_at=entity.updated_at
            )
            session.add(user_model)
            await session.flush()

            # Convert back to domain entity
            return User(
                username=user_model.username,
                email=user_model.email,
                entity_id=user_model.id
            )

    async def find_by_id(self, entity_id: UUID) -> User | None:
        async with self.db_manager.get_session() as session:
            stmt = select(UserModel).where(UserModel.id == entity_id)
            result = await session.execute(stmt)
            user_model = result.scalar_one_or_none()

            if not user_model:
                return None

            return User(
                username=user_model.username,
                email=user_model.email,
                entity_id=user_model.id
            )
```

## Migration Steps

### 1. Update Service Structure

Create the following directory structure for each service:

```
mmf/services/your_service/
├── domain/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── your_entity.py
│   └── contracts/
│       ├── __init__.py
│       └── your_repository.py
├── application/
│   ├── __init__.py
│   ├── use_cases/
│   │   ├── __init__.py
│   │   └── your_use_case.py
│   └── ports_out/
│       ├── __init__.py
│       └── your_port.py
├── infrastructure/
│   ├── __init__.py
│   └── adapters/
│       ├── __init__.py
│       ├── your_repository_impl.py
│       └── your_adapter.py
└── integration/
    ├── __init__.py
    ├── configuration.py
    └── endpoints.py
```

### 2. Migrate Domain Models

Transform existing models to extend the Entity base class:

```python
# Before (old framework)
class User:
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

# After (new framework)
from mmf.core.domain.entity import Entity

class User(Entity):
    def __init__(self, username: str, email: str, entity_id: UUID = None):
        super().__init__(entity_id)
        self.username = username
        self.email = email
```

### 3. Create Repository Interfaces

Define repository contracts in the domain layer:

```python
from mmf.core.domain.repository import Repository

class UserRepository(Repository[User]):
    async def find_by_username(self, username: str) -> User | None:
        """Find user by username."""
        ...
```

### 4. Implement Use Cases

Create use cases in the application layer:

```python
from mmf.core.application.base import UseCase

class CreateUserUseCase(UseCase[CreateUserRequest, CreateUserResponse]):
    # Implementation as shown above
```

### 5. Implement Infrastructure

Create concrete implementations in the infrastructure layer:

```python
class SQLAlchemyUserRepository(UserRepository):
    # Implementation as shown above
```

### 6. Wire Everything Together

In your service's integration layer:

```python
# configuration.py
from mmf.framework.infrastructure.database import DatabaseConfig
from mmf.framework.infrastructure.sqlalchemy_manager import SQLAlchemyDatabaseManager

def create_database_manager() -> SQLAlchemyDatabaseManager:
    config = DatabaseConfig(
        service_name="user-service",
        database_url=os.getenv("DATABASE_URL"),
        pool_size=5
    )
    return SQLAlchemyDatabaseManager(config)

def create_user_repository(db_manager: SQLAlchemyDatabaseManager) -> UserRepository:
    return SQLAlchemyUserRepository(db_manager)

def create_create_user_use_case(user_repository: UserRepository) -> CreateUserUseCase:
    return CreateUserUseCase(user_repository)
```

## Benefits of the New Framework

1. **Clean Architecture**: Clear separation of concerns with hexagonal architecture
2. **Testability**: Easy to mock dependencies and test business logic
3. **Flexibility**: Swap implementations without affecting business logic
4. **Consistency**: Standard patterns across all services
5. **Type Safety**: Full type annotations for better development experience
6. **Async Support**: Built-in async/await support throughout

## Next Steps

1. Start with a simple service to validate the approach
2. Gradually migrate existing services
3. Create shared utilities and patterns
4. Establish testing conventions
5. Document service-specific patterns
