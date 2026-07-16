from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.platform.base_services import BaseService, ServiceWithDependencies
from mmf.core.platform.contracts import IContainer


class ConcreteService(BaseService):
    """Concrete implementation of BaseService for testing."""

    def __init__(self, container, config=None):
        super().__init__(container, config)
        self.initialized_called = False
        self.shutdown_called = False

    async def _on_initialize(self) -> None:
        self.initialized_called = True

    async def _on_shutdown(self) -> None:
        self.shutdown_called = True


class ConcreteServiceWithDeps(ServiceWithDependencies):
    """Concrete implementation of ServiceWithDependencies for testing."""

    async def _on_initialize(self) -> None:
        await super()._on_initialize()

    async def _on_shutdown(self) -> None:
        pass


class TestBaseService:
    @pytest.fixture
    def container(self):
        return Mock(spec=IContainer)

    @pytest.mark.asyncio
    async def test_lifecycle(self, container):
        service = ConcreteService(container, {"key": "value"})

        assert service.is_initialized is False
        assert service.config == {"key": "value"}

        # Test configure
        service.configure({"new_key": "new_value"})
        assert service.config == {"key": "value", "new_key": "new_value"}

        # Test initialize
        await service.initialize()
        assert service.is_initialized is True
        assert service.initialized_called is True

        # Test double initialize (should be no-op)
        service.initialized_called = False
        await service.initialize()
        assert service.initialized_called is False

        # Test shutdown
        await service.shutdown()
        assert service.is_initialized is False
        assert service.shutdown_called is True

        # Test double shutdown (should be no-op)
        service.shutdown_called = False
        await service.shutdown()
        assert service.shutdown_called is False


class TestServiceWithDependencies:
    @pytest.fixture
    def container(self):
        return Mock(spec=IContainer)

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, container):
        # Setup mock dependency
        mock_dep = Mock()
        container.get.return_value = mock_dep

        service = ConcreteServiceWithDeps(container)
        service.add_dependency("dep1", str)

        # Test get_dependency
        resolved = service.get_dependency("dep1")
        assert resolved == mock_dep
        container.get.assert_called_with(str)

        # Test cached dependency
        container.get.reset_mock()
        resolved_again = service.get_dependency("dep1")
        assert resolved_again == mock_dep
        container.get.assert_not_called()

    def test_missing_dependency(self, container):
        service = ConcreteServiceWithDeps(container)
        with pytest.raises(ValueError, match="Dependency 'missing' not registered"):
            service.get_dependency("missing")

    @pytest.mark.asyncio
    async def test_initialize_resolves_dependencies(self, container):
        mock_dep = Mock()
        container.get.return_value = mock_dep

        service = ConcreteServiceWithDeps(container)
        service.add_dependency("dep1", str)

        await service.initialize()

        # Verify dependency was resolved during initialization
        container.get.assert_called_with(str)
