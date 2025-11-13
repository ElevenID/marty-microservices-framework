"""Tests for command and query handling - using real implementations."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4


# Test entity classes
class TestUser:
    """Test user entity."""

    def __init__(self, user_id: str = None, name: str = "", email: str = ""):
        self.id = user_id or str(uuid4())
        self.name = name
        self.email = email
        self.created_at = datetime.now(timezone.utc)


class TestProduct:
    """Test product entity."""

    def __init__(self, product_id: str = None, name: str = "", price: float = 0.0):
        self.id = product_id or str(uuid4())
        self.name = name
        self.price = price
        self.created_at = datetime.now(timezone.utc)


# Test repository implementation


class InMemoryTestRepository:
    """In-memory repository for testing."""

    def __init__(self):
        self._entities = {}

    async def save(self, entity):
        """Save an entity."""
        if not hasattr(entity, "id"):
            entity.id = str(uuid4())
        self._entities[entity.id] = entity
        return entity

    async def find_by_id(self, entity_id: str):
        """Find an entity by ID."""
        return self._entities.get(entity_id)

    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    async def find_all(self) -> list:
        """Find all entities."""
        return list(self._entities.values())


# Test command infrastructure


class CreateUserCommand:
    """Command to create a user."""

    def __init__(self, name: str, email: str):
        self.request_id = str(uuid4())
        self.name = name
        self.email = email
        self.timestamp = datetime.now(timezone.utc)


class UpdateUserCommand:
    """Command to update a user."""

    def __init__(self, user_id: str, name: str = None, email: str = None):
        self.request_id = str(uuid4())
        self.user_id = user_id
        self.name = name
        self.email = email
        self.timestamp = datetime.now(timezone.utc)


class CommandResult:
    """Result of command execution."""

    def __init__(self, success: bool, data=None, error=None):
        self.success = success
        self.data = data
        self.error = error
        self.execution_time_ms = 0


class CreateUserHandler:
    """Handler for creating users."""

    def __init__(self, repository):
        self.repository = repository

    async def handle(self, command: CreateUserCommand) -> CommandResult:
        try:
            user = TestUser(name=command.name, email=command.email)
            saved_user = await self.repository.save(user)
            return CommandResult(success=True, data=saved_user)
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class UpdateUserHandler:
    """Handler for updating users."""

    def __init__(self, repository):
        self.repository = repository

    async def handle(self, command: UpdateUserCommand) -> CommandResult:
        try:
            user = await self.repository.find_by_id(command.user_id)
            if not user:
                return CommandResult(success=False, error="User not found")

            if command.name:
                user.name = command.name
            if command.email:
                user.email = command.email

            saved_user = await self.repository.save(user)
            return CommandResult(success=True, data=saved_user)
        except Exception as e:
            return CommandResult(success=False, error=str(e))


# Test query infrastructure


class GetUserQuery:
    """Query to get a user by ID."""

    def __init__(self, user_id: str):
        self.request_id = str(uuid4())
        self.user_id = user_id
        self.timestamp = datetime.now(timezone.utc)


class GetAllUsersQuery:
    """Query to get all users."""

    def __init__(self):
        self.request_id = str(uuid4())
        self.timestamp = datetime.now(timezone.utc)


class QueryResult:
    """Result of query execution."""

    def __init__(self, success: bool, data=None, error=None, total_count=None):
        self.success = success
        self.data = data
        self.error = error
        self.total_count = total_count


class GetUserHandler:
    """Handler for getting a user."""

    def __init__(self, repository):
        self.repository = repository

    async def handle(self, query: GetUserQuery) -> QueryResult:
        try:
            user = await self.repository.find_by_id(query.user_id)
            if user:
                return QueryResult(success=True, data=user)
            else:
                return QueryResult(success=False, error="User not found")
        except Exception as e:
            return QueryResult(success=False, error=str(e))


class GetAllUsersHandler:
    """Handler for getting all users."""

    def __init__(self, repository):
        self.repository = repository

    async def handle(self, query: GetAllUsersQuery) -> QueryResult:
        try:
            users = await self.repository.find_all()
            return QueryResult(success=True, data=users, total_count=len(users))
        except Exception as e:
            return QueryResult(success=False, error=str(e))


# Command and Query Buses


class TestCommandBus:
    """Simple command bus for testing."""

    def __init__(self):
        self._handlers = {}

    def register_handler(self, command_type: type, handler):
        """Register a command handler."""
        self._handlers[command_type] = handler

    async def execute(self, command) -> CommandResult:
        """Execute a command."""
        command_type = type(command)
        if command_type not in self._handlers:
            return CommandResult(
                success=False,
                error=f"No handler for {command_type.__name__}",
            )

        handler = self._handlers[command_type]
        return await handler.handle(command)


class TestQueryBus:
    """Simple query bus for testing."""

    def __init__(self):
        self._handlers = {}

    def register_handler(self, query_type: type, handler):
        """Register a query handler."""
        self._handlers[query_type] = handler

    async def execute(self, query) -> QueryResult:
        """Execute a query."""
        query_type = type(query)
        if query_type not in self._handlers:
            return QueryResult(
                success=False,
                error=f"No handler for {query_type.__name__}",
            )

        handler = self._handlers[query_type]
        return await handler.handle(query)


# Test Classes


class TestRepositoryOperations:
    """Test repository basic operations."""

    def test_save_user(self):
        """Test saving a user to repository."""

        async def run_test():
            repo = InMemoryTestRepository()
            user = TestUser(name="John Doe", email="john@example.com")

            saved_user = await repo.save(user)

            assert saved_user.id is not None
            assert saved_user.name == "John Doe"
            assert saved_user.email == "john@example.com"
            assert saved_user.created_at is not None

        asyncio.run(run_test())

    def test_find_user_by_id(self):
        """Test finding a user by ID."""

        async def run_test():
            repo = InMemoryTestRepository()
            user = TestUser(name="Jane Doe", email="jane@example.com")

            saved_user = await repo.save(user)
            found_user = await repo.find_by_id(saved_user.id)

            assert found_user is not None
            assert found_user.id == saved_user.id
            assert found_user.name == "Jane Doe"
            assert found_user.email == "jane@example.com"

        asyncio.run(run_test())

    def test_find_user_not_found(self):
        """Test finding a non-existent user returns None."""

        async def run_test():
            repo = InMemoryTestRepository()

            found_user = await repo.find_by_id("non-existent-id")

            assert found_user is None

        asyncio.run(run_test())

    def test_delete_user(self):
        """Test deleting a user."""

        async def run_test():
            repo = InMemoryTestRepository()
            user = TestUser(name="Delete Me", email="delete@example.com")

            saved_user = await repo.save(user)
            deleted = await repo.delete(saved_user.id)
            found_user = await repo.find_by_id(saved_user.id)

            assert deleted is True
            assert found_user is None

        asyncio.run(run_test())

    def test_find_all_users(self):
        """Test finding all users."""

        async def run_test():
            repo = InMemoryTestRepository()

            user1 = TestUser(name="User 1", email="user1@example.com")
            user2 = TestUser(name="User 2", email="user2@example.com")

            await repo.save(user1)
            await repo.save(user2)

            all_users = await repo.find_all()

            assert len(all_users) == 2
            user_names = [u.name for u in all_users]
            assert "User 1" in user_names
            assert "User 2" in user_names

        asyncio.run(run_test())


class TestCommandHandling:
    """Test command handling operations."""

    def test_create_user_command(self):
        """Test creating a user through command."""

        async def run_test():
            repo = InMemoryTestRepository()
            handler = CreateUserHandler(repo)
            command = CreateUserCommand("New User", "newuser@example.com")

            result = await handler.handle(command)

            assert result.success is True
            assert result.data is not None
            assert result.data.name == "New User"
            assert result.data.email == "newuser@example.com"
            assert result.error is None

        asyncio.run(run_test())

    def test_update_user_command(self):
        """Test updating a user through command."""

        async def run_test():
            repo = InMemoryTestRepository()

            # Create initial user
            user = TestUser(name="Original Name", email="original@example.com")
            saved_user = await repo.save(user)

            # Update user
            handler = UpdateUserHandler(repo)
            command = UpdateUserCommand(
                saved_user.id, name="Updated Name", email="updated@example.com"
            )

            result = await handler.handle(command)

            assert result.success is True
            assert result.data.name == "Updated Name"
            assert result.data.email == "updated@example.com"

        asyncio.run(run_test())

    def test_update_nonexistent_user_command(self):
        """Test updating a non-existent user fails."""

        async def run_test():
            repo = InMemoryTestRepository()
            handler = UpdateUserHandler(repo)
            command = UpdateUserCommand("non-existent-id", name="Updated Name")

            result = await handler.handle(command)

            assert result.success is False
            assert result.error == "User not found"

        asyncio.run(run_test())


class TestQueryHandling:
    """Test query handling operations."""

    def test_get_user_query(self):
        """Test getting a user through query."""

        async def run_test():
            repo = InMemoryTestRepository()

            # Create test user
            user = TestUser(name="Query User", email="query@example.com")
            saved_user = await repo.save(user)

            # Query for user
            handler = GetUserHandler(repo)
            query = GetUserQuery(saved_user.id)

            result = await handler.handle(query)

            assert result.success is True
            assert result.data is not None
            assert result.data.name == "Query User"
            assert result.data.email == "query@example.com"

        asyncio.run(run_test())

    def test_get_nonexistent_user_query(self):
        """Test getting a non-existent user fails."""

        async def run_test():
            repo = InMemoryTestRepository()
            handler = GetUserHandler(repo)
            query = GetUserQuery("non-existent-id")

            result = await handler.handle(query)

            assert result.success is False
            assert result.error == "User not found"

        asyncio.run(run_test())

    def test_get_all_users_query(self):
        """Test getting all users through query."""

        async def run_test():
            repo = InMemoryTestRepository()

            # Create test users
            user1 = TestUser(name="User A", email="usera@example.com")
            user2 = TestUser(name="User B", email="userb@example.com")
            await repo.save(user1)
            await repo.save(user2)

            # Query for all users
            handler = GetAllUsersHandler(repo)
            query = GetAllUsersQuery()

            result = await handler.handle(query)

            assert result.success is True
            assert result.data is not None
            assert len(result.data) == 2
            assert result.total_count == 2

        asyncio.run(run_test())


class TestBusOperations:
    """Test command and query bus operations."""

    def test_command_bus_execution(self):
        """Test command bus with registered handler."""

        async def run_test():
            repo = InMemoryTestRepository()
            bus = TestCommandBus()
            handler = CreateUserHandler(repo)

            # Register handler
            bus.register_handler(CreateUserCommand, handler)

            # Execute command
            command = CreateUserCommand("Bus User", "bus@example.com")
            result = await bus.execute(command)

            assert result.success is True
            assert result.data.name == "Bus User"
            assert result.data.email == "bus@example.com"

        asyncio.run(run_test())

    def test_command_bus_no_handler(self):
        """Test command bus with no registered handler."""

        async def run_test():
            bus = TestCommandBus()
            command = CreateUserCommand("No Handler", "nohandler@example.com")

            result = await bus.execute(command)

            assert result.success is False
            assert "No handler for CreateUserCommand" in result.error

        asyncio.run(run_test())

    def test_query_bus_execution(self):
        """Test query bus with registered handler."""

        async def run_test():
            repo = InMemoryTestRepository()
            bus = TestQueryBus()
            handler = GetAllUsersHandler(repo)

            # Create test data
            user = TestUser(name="Query Bus User", email="querybus@example.com")
            await repo.save(user)

            # Register handler
            bus.register_handler(GetAllUsersQuery, handler)

            # Execute query
            query = GetAllUsersQuery()
            result = await bus.execute(query)

            assert result.success is True
            assert len(result.data) == 1
            assert result.data[0].name == "Query Bus User"

        asyncio.run(run_test())


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""

    def test_complete_user_workflow(self):
        """Test complete user creation and retrieval workflow."""

        async def run_test():
            # Setup
            repo = InMemoryTestRepository()
            command_bus = TestCommandBus()
            query_bus = TestQueryBus()

            # Register handlers
            create_handler = CreateUserHandler(repo)
            update_handler = UpdateUserHandler(repo)
            get_handler = GetUserHandler(repo)
            get_all_handler = GetAllUsersHandler(repo)

            command_bus.register_handler(CreateUserCommand, create_handler)
            command_bus.register_handler(UpdateUserCommand, update_handler)
            query_bus.register_handler(GetUserQuery, get_handler)
            query_bus.register_handler(GetAllUsersQuery, get_all_handler)

            # Create user
            create_command = CreateUserCommand("Workflow User", "workflow@example.com")
            create_result = await command_bus.execute(create_command)

            assert create_result.success is True
            user_id = create_result.data.id

            # Get user by ID
            get_query = GetUserQuery(user_id)
            get_result = await query_bus.execute(get_query)

            assert get_result.success is True
            assert get_result.data.name == "Workflow User"

            # Update user
            update_command = UpdateUserCommand(user_id, name="Updated Workflow User")
            update_result = await command_bus.execute(update_command)

            assert update_result.success is True
            assert update_result.data.name == "Updated Workflow User"

            # Get all users
            get_all_query = GetAllUsersQuery()
            get_all_result = await query_bus.execute(get_all_query)

            assert get_all_result.success is True
            assert len(get_all_result.data) == 1
            assert get_all_result.data[0].name == "Updated Workflow User"

        asyncio.run(run_test())

    def test_multi_entity_repository(self):
        """Test repository with multiple entity types."""

        async def run_test():
            repo = InMemoryTestRepository()

            # Save different entity types
            user = TestUser(name="Multi User", email="multi@example.com")
            product = TestProduct(name="Test Product", price=29.99)

            saved_user = await repo.save(user)
            saved_product = await repo.save(product)

            # Retrieve them
            found_user = await repo.find_by_id(saved_user.id)
            found_product = await repo.find_by_id(saved_product.id)

            assert found_user.name == "Multi User"
            assert found_product.name == "Test Product"
            assert found_product.price == 29.99

            # Get all entities
            all_entities = await repo.find_all()
            assert len(all_entities) == 2

        asyncio.run(run_test())
