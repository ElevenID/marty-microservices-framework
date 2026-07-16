import contextlib

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from mmf.services.identity.domain.models.authenticated_user import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters.out.persistence.models import Base
from mmf.services.identity.infrastructure.adapters.out.persistence.user_repository import (
    AuthenticatedUserRepository,
)


class TestDatabaseManager:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @contextlib.asynccontextmanager
    async def get_transaction(self):
        async with self.session_factory() as session:
            async with session.begin():
                yield session


@pytest.mark.integration
@pytest.mark.asyncio
async def test_identity_repository_integration(postgres_container: PostgresContainer):
    """Test Identity Repository with real Postgres container."""

    # 1. Setup Database Connection
    connection_url = postgres_container.get_connection_url()
    asyncpg_url = connection_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    engine = create_async_engine(asyncpg_url, echo=False)

    # 2. Create Schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    db_manager = TestDatabaseManager(session_factory)

    # 3. Initialize Repository
    repo = AuthenticatedUserRepository(db_manager)

    # 4. Create Test User
    user = AuthenticatedUser(
        user_id="user-123",
        username="testuser",
        email="test@example.com",
        roles={"admin", "user"},
        permissions={"read", "write"},
        auth_method="password",
    )

    # 5. Save User
    saved_user = await repo.save(user)
    assert saved_user.user_id == "user-123"

    # 6. Retrieve User
    fetched_user = await repo.find_by_id("user-123")
    assert fetched_user is not None
    assert fetched_user.user_id == "user-123"
    assert fetched_user.username == "testuser"
    assert fetched_user.roles == {"admin", "user"}

    # 7. Update User
    updated_user = await repo.update("user-123", {"email": "new@example.com"})
    assert updated_user.email == "new@example.com"

    # 8. Verify Update
    fetched_user_2 = await repo.find_by_id("user-123")
    assert fetched_user_2.email == "new@example.com"

    # 9. Delete User
    deleted = await repo.delete("user-123")
    assert deleted is True

    # 10. Verify Deletion
    fetched_user_3 = await repo.find_by_id("user-123")
    assert fetched_user_3 is None

    await engine.dispose()
