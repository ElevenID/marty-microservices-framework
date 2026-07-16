"""Core dependency injection base classes and protocols.

This module provides the base DI container that all services must inherit from,
ensuring a consistent dependency injection pattern across the framework.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseDIContainer(ABC):
    """Base dependency injection container.

    All service DI containers MUST inherit from this base class to ensure
    consistent lifecycle management and error handling.

    Lifecycle:
    1. __init__(): Store configuration, initialize lazy properties to None
    2. initialize(): Wire all dependencies, create instances
    3. [Use container properties to access components]
    4. cleanup(): Release resources, close connections

    Example:
        ```python
        class MyServiceDIContainer(BaseDIContainer):
            def __init__(self, config: MyServiceConfig):
                super().__init__()
                self.config = config
                self._repository: Optional[MyRepository] = None
                self._use_case: Optional[MyUseCase] = None

            def initialize(self) -> None:
                self._repository = MyRepositoryImpl(self.config.db_url)
                self._use_case = MyUseCase(repository=self._repository)
                self._mark_initialized()

            @property
            def use_case(self) -> MyUseCase:
                self._ensure_initialized()
                return self._use_case

            def cleanup(self) -> None:
                if self._repository:
                    self._repository.close()
                self._mark_cleanup()
        ```
    """

    def __init__(self) -> None:
        """Initialize base container."""
        self._is_initialized: bool = False
        self._is_cleaned_up: bool = False

    @abstractmethod
    def initialize(self) -> None:
        """Wire all dependencies.

        This method MUST be called once after __init__ and before using
        any container properties. Implementations should:
        1. Create all infrastructure adapters
        2. Wire application use cases
        3. Call self._mark_initialized() at the end

        Raises:
            RuntimeError: If already initialized
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Release all resources.

        This method MUST be called during shutdown. Implementations should:
        1. Close all connections
        2. Release all resources
        3. Call self._mark_cleanup() at the end
        """
        pass

    def _mark_initialized(self) -> None:
        """Mark container as initialized.

        Call this at the end of your initialize() implementation.
        """
        if self._is_initialized:
            msg = "Container already initialized"
            raise RuntimeError(msg)
        self._is_initialized = True

    def _mark_cleanup(self) -> None:
        """Mark container as cleaned up.

        Call this at the end of your cleanup() implementation.
        """
        self._is_cleaned_up = True

    def _ensure_initialized(self) -> None:
        """Ensure container is initialized.

        Call this at the start of every property getter.

        Raises:
            RuntimeError: If not initialized or already cleaned up
        """
        if not self._is_initialized:
            msg = "Container not initialized. Call initialize() first."
            raise RuntimeError(msg)
        if self._is_cleaned_up:
            msg = "Container already cleaned up"
            raise RuntimeError(msg)

    @property
    def is_initialized(self) -> bool:
        """Check if container is initialized."""
        return self._is_initialized

    @property
    def is_cleaned_up(self) -> bool:
        """Check if container is cleaned up."""
        return self._is_cleaned_up


class AsyncBaseDIContainer(ABC):
    """Base dependency injection container for async services.

    Use this for services that require async initialization (e.g., database
    connection pools, async HTTP clients).

    Example:
        ```python
        class MyServiceDIContainer(AsyncBaseDIContainer):
            async def initialize(self) -> None:
                self._pool = await create_pool(self.config.db_url)
                self._repository = MyRepositoryImpl(self._pool)
                self._mark_initialized()

            async def cleanup(self) -> None:
                if self._pool:
                    await self._pool.close()
                self._mark_cleanup()
        ```
    """

    def __init__(self) -> None:
        """Initialize base container."""
        self._is_initialized: bool = False
        self._is_cleaned_up: bool = False

    @abstractmethod
    async def initialize(self) -> None:
        """Wire all dependencies asynchronously.

        This method MUST be called once after __init__ and before using
        any container properties.

        Raises:
            RuntimeError: If already initialized
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Release all resources asynchronously.

        This method MUST be called during shutdown.
        """
        pass

    def _mark_initialized(self) -> None:
        """Mark container as initialized."""
        if self._is_initialized:
            msg = "Container already initialized"
            raise RuntimeError(msg)
        self._is_initialized = True

    def _mark_cleanup(self) -> None:
        """Mark container as cleaned up."""
        self._is_cleaned_up = True

    def _ensure_initialized(self) -> None:
        """Ensure container is initialized.

        Raises:
            RuntimeError: If not initialized or already cleaned up
        """
        if not self._is_initialized:
            msg = "Container not initialized. Call initialize() first."
            raise RuntimeError(msg)
        if self._is_cleaned_up:
            msg = "Container already cleaned up"
            raise RuntimeError(msg)

    @property
    def is_initialized(self) -> bool:
        """Check if container is initialized."""
        return self._is_initialized

    @property
    def is_cleaned_up(self) -> bool:
        """Check if container is cleaned up."""
        return self._is_cleaned_up
