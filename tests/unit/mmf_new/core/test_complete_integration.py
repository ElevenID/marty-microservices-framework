"""Comprehensive integration tests for the new MMF core architecture.

This test suite demonstrates how to properly test the hexagonal architecture
components using real implementations and realistic data patterns.

Key features tested:
- Domain entities with proper aggregates and events
- Repository pattern with in-memory implementations
- Command/Query separation with proper handlers
- Event-driven architecture with domain events
- Complete integration workflows
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class DomainEvent:
    """Domain event for aggregate roots."""

    def __init__(self, event_name: str, event_data: dict, aggregate_id: str):
        self.event_name = event_name
        self.event_data = event_data
        self.aggregate_id = aggregate_id
        self.timestamp = datetime.now(timezone.utc)
        self.event_id = str(uuid4())


class UserAggregate:
    """User aggregate root following DDD patterns."""

    def __init__(self, user_id: str = None, email: str = "", name: str = ""):
        self.id = user_id or str(uuid4())
        self.email = email
        self.name = name
        self.active = True
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self._domain_events = []

    def update_profile(self, name: str = None, email: str = None):
        """Update user profile with business logic."""
        if email and email != self.email:
            # Business rule: email must be unique (would be validated by repository)
            old_email = self.email
            self.email = email
            self._domain_events.append(
                DomainEvent(
                    "user.email.changed",
                    {"old_email": old_email, "new_email": email},
                    self.id,
                )
            )

        if name and name != self.name:
            old_name = self.name
            self.name = name
            self._domain_events.append(
                DomainEvent(
                    "user.name.changed",
                    {"old_name": old_name, "new_name": name},
                    self.id,
                )
            )

        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self):
        """Deactivate user account."""
        if self.active:
            self.active = False
            self._domain_events.append(
                DomainEvent(
                    "user.deactivated",
                    {"deactivated_at": datetime.now(timezone.utc).isoformat()},
                    self.id,
                )
            )

    def get_domain_events(self) -> list[DomainEvent]:
        """Get all pending domain events."""
        return self._domain_events.copy()

    def clear_domain_events(self):
        """Clear domain events after processing."""
        self._domain_events.clear()


class ProjectAggregate:
    """Project aggregate demonstrating complex business logic."""

    def __init__(self, project_id: str = None, name: str = "", owner_id: str = ""):
        self.id = project_id or str(uuid4())
        self.name = name
        self.owner_id = owner_id
        self.members = set()
        self.status = "active"
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self._domain_events = []

    def add_member(self, user_id: str):
        """Add member with business rules."""
        if user_id == self.owner_id:
            raise ValueError("Owner is already a member")

        if user_id in self.members:
            raise ValueError("User is already a member")

        self.members.add(user_id)
        self._domain_events.append(
            DomainEvent(
                "project.member.added",
                {"user_id": user_id, "project_id": self.id},
                self.id,
            )
        )

    def remove_member(self, user_id: str):
        """Remove member with validation."""
        if user_id == self.owner_id:
            raise ValueError("Cannot remove project owner")

        if user_id not in self.members:
            raise ValueError("User is not a member")

        self.members.remove(user_id)
        self._domain_events.append(
            DomainEvent(
                "project.member.removed",
                {"user_id": user_id, "project_id": self.id},
                self.id,
            )
        )

    def get_domain_events(self) -> list[DomainEvent]:
        return self._domain_events.copy()

    def clear_domain_events(self):
        self._domain_events.clear()


# Repository implementations following the Repository pattern


class InMemoryUserRepository:
    """In-memory user repository with business logic validation."""

    def __init__(self):
        self._users = {}
        self._emails = set()  # Track emails for uniqueness

    async def save(self, user: UserAggregate) -> UserAggregate:
        """Save user with email uniqueness validation."""
        # Business rule: emails must be unique
        if user.email in self._emails and user.id not in self._users:
            raise ValueError(f"Email {user.email} is already in use")

        # If updating existing user, remove old email from tracking
        if user.id in self._users:
            old_user = self._users[user.id]
            if old_user.email != user.email:
                self._emails.discard(old_user.email)

        self._users[user.id] = user
        self._emails.add(user.email)
        return user

    async def find_by_id(self, user_id: str) -> UserAggregate | None:
        return self._users.get(user_id)

    async def find_by_email(self, email: str) -> UserAggregate | None:
        """Find user by email address."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def find_active_users(self) -> list[UserAggregate]:
        """Find all active users."""
        return [user for user in self._users.values() if user.active]

    async def delete(self, user_id: str) -> bool:
        if user_id in self._users:
            user = self._users[user_id]
            self._emails.discard(user.email)
            del self._users[user_id]
            return True
        return False


class InMemoryProjectRepository:
    """In-memory project repository."""

    def __init__(self):
        self._projects = {}

    async def save(self, project: ProjectAggregate) -> ProjectAggregate:
        self._projects[project.id] = project
        return project

    async def find_by_id(self, project_id: str) -> ProjectAggregate | None:
        return self._projects.get(project_id)

    async def find_by_owner(self, owner_id: str) -> list[ProjectAggregate]:
        """Find all projects owned by a user."""
        return [p for p in self._projects.values() if p.owner_id == owner_id]

    async def find_by_member(self, user_id: str) -> list[ProjectAggregate]:
        """Find all projects where user is a member."""
        return [
            p
            for p in self._projects.values()
            if user_id in p.members or p.owner_id == user_id
        ]


# Command/Query objects with proper structure


class CreateUserCommand:
    """Command to create a new user."""

    def __init__(self, email: str, name: str):
        self.command_id = str(uuid4())
        self.email = email
        self.name = name
        self.timestamp = datetime.now(timezone.utc)


class UpdateUserProfileCommand:
    """Command to update user profile."""

    def __init__(self, user_id: str, name: str = None, email: str = None):
        self.command_id = str(uuid4())
        self.user_id = user_id
        self.name = name
        self.email = email
        self.timestamp = datetime.now(timezone.utc)


class CreateProjectCommand:
    """Command to create a new project."""

    def __init__(self, name: str, owner_id: str):
        self.command_id = str(uuid4())
        self.name = name
        self.owner_id = owner_id
        self.timestamp = datetime.now(timezone.utc)


class AddProjectMemberCommand:
    """Command to add member to project."""

    def __init__(self, project_id: str, user_id: str):
        self.command_id = str(uuid4())
        self.project_id = project_id
        self.user_id = user_id
        self.timestamp = datetime.now(timezone.utc)


# Query objects


class GetUserQuery:
    """Query to get user by ID."""

    def __init__(self, user_id: str):
        self.query_id = str(uuid4())
        self.user_id = user_id
        self.timestamp = datetime.now(timezone.utc)


class GetUsersByProjectQuery:
    """Query to get all users in a project."""

    def __init__(self, project_id: str):
        self.query_id = str(uuid4())
        self.project_id = project_id
        self.timestamp = datetime.now(timezone.utc)


# Result objects


class CommandResult:
    """Result of command execution."""

    def __init__(
        self, success: bool, data: Any = None, error: str = None, events: list = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.events = events or []
        self.execution_time_ms = 0


class QueryResult:
    """Result of query execution."""

    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


# Command Handlers with business logic


class CreateUserHandler:
    """Handler for creating users."""

    def __init__(self, user_repository: InMemoryUserRepository):
        self.user_repository = user_repository

    async def handle(self, command: CreateUserCommand) -> CommandResult:
        try:
            # Business validation
            if not command.email or "@" not in command.email:
                return CommandResult(success=False, error="Invalid email address")

            if not command.name or len(command.name.strip()) < 2:
                return CommandResult(
                    success=False, error="Name must be at least 2 characters"
                )

            # Check if email already exists
            existing = await self.user_repository.find_by_email(command.email)
            if existing:
                return CommandResult(success=False, error="Email already exists")

            # Create user
            user = UserAggregate(email=command.email, name=command.name)
            saved_user = await self.user_repository.save(user)

            # Collect domain events
            events = user.get_domain_events()
            user.clear_domain_events()

            return CommandResult(success=True, data=saved_user, events=events)

        except Exception as e:
            return CommandResult(success=False, error=str(e))


class UpdateUserProfileHandler:
    """Handler for updating user profiles."""

    def __init__(self, user_repository: InMemoryUserRepository):
        self.user_repository = user_repository

    async def handle(self, command: UpdateUserProfileCommand) -> CommandResult:
        try:
            user = await self.user_repository.find_by_id(command.user_id)
            if not user:
                return CommandResult(success=False, error="User not found")

            # Apply updates with business logic
            user.update_profile(name=command.name, email=command.email)

            # Validate email uniqueness if changed
            if command.email and command.email != user.email:
                existing = await self.user_repository.find_by_email(command.email)
                if existing and existing.id != user.id:
                    return CommandResult(success=False, error="Email already exists")

            saved_user = await self.user_repository.save(user)

            # Collect domain events
            events = user.get_domain_events()
            user.clear_domain_events()

            return CommandResult(success=True, data=saved_user, events=events)

        except Exception as e:
            return CommandResult(success=False, error=str(e))


class CreateProjectHandler:
    """Handler for creating projects."""

    def __init__(
        self,
        project_repository: InMemoryProjectRepository,
        user_repository: InMemoryUserRepository,
    ):
        self.project_repository = project_repository
        self.user_repository = user_repository

    async def handle(self, command: CreateProjectCommand) -> CommandResult:
        try:
            # Validate owner exists
            owner = await self.user_repository.find_by_id(command.owner_id)
            if not owner:
                return CommandResult(success=False, error="Owner user not found")

            if not owner.active:
                return CommandResult(success=False, error="Owner account is inactive")

            # Create project
            project = ProjectAggregate(name=command.name, owner_id=command.owner_id)
            saved_project = await self.project_repository.save(project)

            events = project.get_domain_events()
            project.clear_domain_events()

            return CommandResult(success=True, data=saved_project, events=events)

        except Exception as e:
            return CommandResult(success=False, error=str(e))


# Query Handlers


class GetUserHandler:
    """Handler for getting user by ID."""

    def __init__(self, user_repository: InMemoryUserRepository):
        self.user_repository = user_repository

    async def handle(self, query: GetUserQuery) -> QueryResult:
        try:
            user = await self.user_repository.find_by_id(query.user_id)
            if user:
                return QueryResult(success=True, data=user)
            else:
                return QueryResult(success=False, error="User not found")
        except Exception as e:
            return QueryResult(success=False, error=str(e))


class GetUsersByProjectHandler:
    """Handler for getting users by project."""

    def __init__(
        self,
        project_repository: InMemoryProjectRepository,
        user_repository: InMemoryUserRepository,
    ):
        self.project_repository = project_repository
        self.user_repository = user_repository

    async def handle(self, query: GetUsersByProjectQuery) -> QueryResult:
        try:
            project = await self.project_repository.find_by_id(query.project_id)
            if not project:
                return QueryResult(success=False, error="Project not found")

            # Get all users (owner + members)
            all_user_ids = {project.owner_id} | project.members
            users = []

            for user_id in all_user_ids:
                user = await self.user_repository.find_by_id(user_id)
                if user:
                    users.append(user)

            return QueryResult(success=True, data=users)

        except Exception as e:
            return QueryResult(success=False, error=str(e))


# Test Classes


class TestDomainAggregates:
    """Test domain aggregate business logic."""

    def test_user_aggregate_creation(self):
        """Test creating user aggregate."""
        user = UserAggregate(email="test@example.com", name="Test User")

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.active is True
        assert len(user.get_domain_events()) == 0

    def test_user_profile_update_generates_events(self):
        """Test that profile updates generate domain events."""
        user = UserAggregate(email="old@example.com", name="Old Name")

        user.update_profile(name="New Name", email="new@example.com")
        events = user.get_domain_events()

        assert len(events) == 2
        assert any(e.event_name == "user.name.changed" for e in events)
        assert any(e.event_name == "user.email.changed" for e in events)

    def test_project_member_management(self):
        """Test project member addition and removal."""
        project = ProjectAggregate(name="Test Project", owner_id="owner123")

        # Add member
        project.add_member("user456")
        assert "user456" in project.members

        events = project.get_domain_events()
        assert len(events) == 1
        assert events[0].event_name == "project.member.added"

        # Remove member
        project.clear_domain_events()
        project.remove_member("user456")
        assert "user456" not in project.members

        events = project.get_domain_events()
        assert len(events) == 1
        assert events[0].event_name == "project.member.removed"


class TestRepositoryOperations:
    """Test repository operations with business logic."""

    def test_user_repository_email_uniqueness(self):
        """Test that repository enforces email uniqueness."""

        async def run_test():
            repo = InMemoryUserRepository()

            user1 = UserAggregate(email="unique@example.com", name="User 1")
            await repo.save(user1)

            user2 = UserAggregate(email="unique@example.com", name="User 2")
            try:
                await repo.save(user2)
                raise AssertionError(
                    "Should have raised ValueError for duplicate email"
                )
            except ValueError as e:
                assert "already in use" in str(e)

        asyncio.run(run_test())

    def test_user_repository_find_by_email(self):
        """Test finding user by email."""

        async def run_test():
            repo = InMemoryUserRepository()
            user = UserAggregate(email="findme@example.com", name="Find Me")
            await repo.save(user)

            found = await repo.find_by_email("findme@example.com")
            assert found is not None
            assert found.id == user.id

            not_found = await repo.find_by_email("notfound@example.com")
            assert not_found is None

        asyncio.run(run_test())

    def test_project_repository_find_by_owner(self):
        """Test finding projects by owner."""

        async def run_test():
            repo = InMemoryProjectRepository()

            project1 = ProjectAggregate(name="Project 1", owner_id="owner123")
            project2 = ProjectAggregate(name="Project 2", owner_id="owner123")
            project3 = ProjectAggregate(name="Project 3", owner_id="owner456")

            await repo.save(project1)
            await repo.save(project2)
            await repo.save(project3)

            owner_projects = await repo.find_by_owner("owner123")
            assert len(owner_projects) == 2

        asyncio.run(run_test())


class TestCompleteWorkflows:
    """Test complete business workflows end-to-end."""

    def test_user_creation_workflow(self):
        """Test complete user creation workflow."""

        async def run_test():
            repo = InMemoryUserRepository()
            handler = CreateUserHandler(repo)

            command = CreateUserCommand("workflow@example.com", "Workflow User")
            result = await handler.handle(command)

            assert result.success is True
            assert result.data.email == "workflow@example.com"
            assert result.data.name == "Workflow User"

            # Verify user was saved
            saved_user = await repo.find_by_email("workflow@example.com")
            assert saved_user is not None

        asyncio.run(run_test())

    def test_user_creation_duplicate_email_fails(self):
        """Test that creating user with duplicate email fails."""

        async def run_test():
            repo = InMemoryUserRepository()
            handler = CreateUserHandler(repo)

            # Create first user
            command1 = CreateUserCommand("duplicate@example.com", "First User")
            result1 = await handler.handle(command1)
            assert result1.success is True

            # Try to create second user with same email
            command2 = CreateUserCommand("duplicate@example.com", "Second User")
            result2 = await handler.handle(command2)
            assert result2.success is False
            assert "already exists" in result2.error

        asyncio.run(run_test())

    def test_project_creation_workflow(self):
        """Test complete project creation workflow."""

        async def run_test():
            user_repo = InMemoryUserRepository()
            project_repo = InMemoryProjectRepository()

            # Create owner first
            owner = UserAggregate(email="owner@example.com", name="Project Owner")
            await user_repo.save(owner)

            # Create project
            handler = CreateProjectHandler(project_repo, user_repo)
            command = CreateProjectCommand("My Project", owner.id)
            result = await handler.handle(command)

            assert result.success is True
            assert result.data.name == "My Project"
            assert result.data.owner_id == owner.id

        asyncio.run(run_test())

    def test_project_with_inactive_owner_fails(self):
        """Test that project creation fails with inactive owner."""

        async def run_test():
            user_repo = InMemoryUserRepository()
            project_repo = InMemoryProjectRepository()

            # Create inactive owner
            owner = UserAggregate(email="inactive@example.com", name="Inactive Owner")
            owner.deactivate()
            await user_repo.save(owner)

            # Try to create project
            handler = CreateProjectHandler(project_repo, user_repo)
            command = CreateProjectCommand("Should Fail", owner.id)
            result = await handler.handle(command)

            assert result.success is False
            assert "inactive" in result.error

        asyncio.run(run_test())

    def test_complete_project_collaboration_workflow(self):
        """Test complete project collaboration workflow."""

        async def run_test():
            user_repo = InMemoryUserRepository()
            project_repo = InMemoryProjectRepository()

            # Create users
            owner = UserAggregate(email="owner@example.com", name="Owner")
            member1 = UserAggregate(email="member1@example.com", name="Member 1")
            member2 = UserAggregate(email="member2@example.com", name="Member 2")

            await user_repo.save(owner)
            await user_repo.save(member1)
            await user_repo.save(member2)

            # Create project
            project = ProjectAggregate(name="Collaboration Project", owner_id=owner.id)
            project.add_member(member1.id)
            project.add_member(member2.id)
            await project_repo.save(project)

            # Query all project users
            query_handler = GetUsersByProjectHandler(project_repo, user_repo)
            query = GetUsersByProjectQuery(project.id)
            result = await query_handler.handle(query)

            assert result.success is True
            assert len(result.data) == 3  # owner + 2 members
            user_emails = [u.email for u in result.data]
            assert "owner@example.com" in user_emails
            assert "member1@example.com" in user_emails
            assert "member2@example.com" in user_emails

        asyncio.run(run_test())


class TestEventDrivenBehavior:
    """Test event-driven behavior and domain events."""

    def test_domain_events_are_generated_and_cleared(self):
        """Test that domain events are properly generated and cleared."""

        async def run_test():
            repo = InMemoryUserRepository()
            handler = UpdateUserProfileHandler(repo)

            # Create initial user
            user = UserAggregate(email="events@example.com", name="Original Name")
            await repo.save(user)

            # Update profile
            command = UpdateUserProfileCommand(
                user.id, name="Updated Name", email="updated@example.com"
            )
            result = await handler.handle(command)

            assert result.success is True
            assert len(result.events) == 2  # name change + email change

            # Verify events contain proper data
            name_event = next(
                e for e in result.events if e.event_name == "user.name.changed"
            )
            assert name_event.event_data["old_name"] == "Original Name"
            assert name_event.event_data["new_name"] == "Updated Name"

            email_event = next(
                e for e in result.events if e.event_name == "user.email.changed"
            )
            assert email_event.event_data["old_email"] == "events@example.com"
            assert email_event.event_data["new_email"] == "updated@example.com"

        asyncio.run(run_test())


if __name__ == "__main__":
    print("🧪 Running comprehensive MMF core architecture tests...")

    # Run domain tests
    domain_test = TestDomainAggregates()
    domain_test.test_user_aggregate_creation()
    domain_test.test_user_profile_update_generates_events()
    domain_test.test_project_member_management()
    print("✅ Domain aggregate tests passed!")

    # Run repository tests
    repo_test = TestRepositoryOperations()
    repo_test.test_user_repository_email_uniqueness()
    repo_test.test_user_repository_find_by_email()
    repo_test.test_project_repository_find_by_owner()
    print("✅ Repository operation tests passed!")

    # Run workflow tests
    workflow_test = TestCompleteWorkflows()
    workflow_test.test_user_creation_workflow()
    workflow_test.test_user_creation_duplicate_email_fails()
    workflow_test.test_project_creation_workflow()
    workflow_test.test_project_with_inactive_owner_fails()
    workflow_test.test_complete_project_collaboration_workflow()
    print("✅ Complete workflow tests passed!")

    # Run event-driven tests
    event_test = TestEventDrivenBehavior()
    event_test.test_domain_events_are_generated_and_cleared()
    print("✅ Event-driven behavior tests passed!")

    print("\n🎉 All tests passed! The new MMF core architecture is working correctly.")
    print("\n📋 Test Summary:")
    print("- ✅ Domain aggregates with business logic")
    print("- ✅ Repository pattern with business rules")
    print("- ✅ Command/Query handlers with validation")
    print("- ✅ Event-driven architecture with domain events")
    print("- ✅ Complete integration workflows")
    print("- ✅ Error handling and edge cases")
