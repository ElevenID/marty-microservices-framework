import pytest

from mmf.core.di import AsyncBaseDIContainer, BaseDIContainer


class ConcreteDIContainer(BaseDIContainer):
    def __init__(self):
        super().__init__()
        self.service = None

    def initialize(self) -> None:
        self.service = "ready"
        self._mark_initialized()

    def cleanup(self) -> None:
        self.service = None
        self._mark_cleanup()

    @property
    def get_service(self):
        self._ensure_initialized()
        return self.service


class ConcreteAsyncDIContainer(AsyncBaseDIContainer):
    def __init__(self):
        super().__init__()
        self.service = None

    async def initialize(self) -> None:
        self.service = "ready"
        self._mark_initialized()

    async def cleanup(self) -> None:
        self.service = None
        self._mark_cleanup()

    @property
    def get_service(self):
        self._ensure_initialized()
        return self.service


class TestBaseDIContainer:
    def test_initialization_flow(self):
        container = ConcreteDIContainer()
        assert not container.is_initialized
        assert not container.is_cleaned_up

        container.initialize()
        assert container.is_initialized
        assert not container.is_cleaned_up
        assert container.get_service == "ready"

    def test_double_initialization_raises_error(self):
        container = ConcreteDIContainer()
        container.initialize()

        with pytest.raises(RuntimeError, match="Container already initialized"):
            container._mark_initialized()

    def test_access_before_initialization_raises_error(self):
        container = ConcreteDIContainer()

        with pytest.raises(
            RuntimeError, match=r"Container not initialized. Call initialize\(\) first."
        ):
            _ = container.get_service

    def test_cleanup_flow(self):
        container = ConcreteDIContainer()
        container.initialize()
        container.cleanup()

        assert container.is_cleaned_up

    def test_access_after_cleanup_raises_error(self):
        container = ConcreteDIContainer()
        container.initialize()
        container.cleanup()

        with pytest.raises(RuntimeError, match="Container already cleaned up"):
            _ = container.get_service


class TestAsyncBaseDIContainer:
    @pytest.mark.asyncio
    async def test_initialization_flow(self):
        container = ConcreteAsyncDIContainer()
        assert not container.is_initialized
        assert not container.is_cleaned_up

        await container.initialize()
        assert container.is_initialized
        assert not container.is_cleaned_up
        assert container.get_service == "ready"

    @pytest.mark.asyncio
    async def test_double_initialization_raises_error(self):
        container = ConcreteAsyncDIContainer()
        await container.initialize()

        with pytest.raises(RuntimeError, match="Container already initialized"):
            container._mark_initialized()

    @pytest.mark.asyncio
    async def test_access_before_initialization_raises_error(self):
        container = ConcreteAsyncDIContainer()

        with pytest.raises(
            RuntimeError, match=r"Container not initialized. Call initialize\(\) first."
        ):
            _ = container.get_service

    @pytest.mark.asyncio
    async def test_cleanup_flow(self):
        container = ConcreteAsyncDIContainer()
        await container.initialize()
        await container.cleanup()

        assert container.is_cleaned_up

    @pytest.mark.asyncio
    async def test_access_after_cleanup_raises_error(self):
        container = ConcreteAsyncDIContainer()
        await container.initialize()
        await container.cleanup()

        with pytest.raises(RuntimeError, match="Container already cleaned up"):
            _ = container.get_service
