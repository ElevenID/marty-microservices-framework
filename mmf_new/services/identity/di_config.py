"""Dependency injection configuration for identity service."""

import logging

from mmf_new.core.di import BaseDIContainer
from mmf_new.services.identity.config import (
    APIKeyConfig,
    AuthenticationConfig,
    BasicAuthConfig,
    JWTConfig,
)
from mmf_new.services.identity.application.use_cases.authenticate_with_jwt import (
    AuthenticateWithJWTUseCase,
)
from mmf_new.services.identity.application.use_cases.authenticate_with_basic import (
    AuthenticateWithBasicUseCase,
)
from mmf_new.services.identity.application.use_cases.validate_token import (
    ValidateTokenUseCase,
)
from mmf_new.services.identity.application.ports_out.token_provider import TokenProvider
from mmf_new.services.identity.application.ports_out import BasicAuthenticationProvider
from mmf_new.services.identity.infrastructure.adapters.out.auth.jwt_adapter import (
    JWTTokenProvider,
    JWTConfig as JWTAdapterConfig,
)
from mmf_new.services.identity.infrastructure.adapters.out.auth.basic_auth_adapter import (
    BasicAuthAdapter,
    BasicAuthConfig as BasicAuthAdapterConfig,
)

logger = logging.getLogger(__name__)


class IdentityDIContainer(BaseDIContainer):
    """Dependency injection container for identity service.

    This container wires all identity service dependencies following the
    Hexagonal Architecture pattern. It manages:
    - Infrastructure adapters (JWT token provider, repositories, etc.)
    - Application use cases (authentication, token validation)
    - Lifecycle management (initialization and cleanup)

    Example:
        ```python
        config = AuthenticationConfig()
        container = IdentityDIContainer(config)
        container.initialize()

        # Use container to get components
        auth_use_case = container.authenticate_use_case

        # Cleanup on shutdown
        container.cleanup()
        ```
    """

    def __init__(self, config: AuthenticationConfig):
        """Initialize DI container.

        Args:
            config: Identity service configuration
        """
        super().__init__()
        self.config = config

        # Infrastructure (driven adapters - out)
        self._token_provider: TokenProvider | None = None
        self._basic_auth_provider: BasicAuthenticationProvider | None = None

        # Application (use cases)
        self._authenticate_use_case: AuthenticateWithJWTUseCase | None = None
        self._authenticate_basic_use_case: AuthenticateWithBasicUseCase | None = None
        self._validate_token_use_case: ValidateTokenUseCase | None = None

    def initialize(self) -> None:
        """Wire all dependencies.

        This method creates all infrastructure adapters and wires them to
        application use cases. Must be called once after __init__.
        """
        logger.info("Initializing Identity DI Container")

        # Initialize infrastructure adapters
        self._initialize_token_provider()
        self._initialize_basic_auth_provider()

        # Initialize application use cases
        self._initialize_use_cases()

        # Mark as initialized
        self._mark_initialized()
        logger.info("Identity DI Container initialized successfully")

    def cleanup(self) -> None:
        """Release all resources.

        Cleans up all infrastructure adapters and use cases.
        """
        logger.info("Cleaning up Identity DI Container")

        # Cleanup token provider (if it has cleanup logic)
        if self._token_provider:
            # JWT token provider is stateless, no cleanup needed
            self._token_provider = None

        # Clear use cases
        self._authenticate_use_case = None
        self._validate_token_use_case = None

        self._mark_cleanup()
        logger.info("Identity DI Container cleanup complete")

    def _initialize_token_provider(self) -> None:
        """Initialize token provider based on configuration."""
        # Currently only JWT is implemented
        jwt_config = self.config.jwt

        # Create JWT adapter config
        adapter_config = JWTAdapterConfig(
            secret_key=jwt_config.secret_key,
            algorithm=jwt_config.algorithm,
            access_token_expire_minutes=jwt_config.access_token_expire_minutes,
        )

        self._token_provider = JWTTokenProvider(config=adapter_config)
        logger.info("Initialized JWT token provider")

    def _initialize_basic_auth_provider(self) -> None:
        """Initialize basic authentication provider."""
        basic_config = self.config.basic_auth

        adapter_config = BasicAuthAdapterConfig(
            password_min_length=basic_config.password_min_length,
            password_require_uppercase=basic_config.password_require_uppercase,
            password_require_lowercase=basic_config.password_require_lowercase,
            password_require_digits=basic_config.password_require_numbers,
            password_require_special=basic_config.password_require_special_chars,
            bcrypt_rounds=basic_config.password_hash_rounds,
            enable_user_registration=False,  # Not in main config yet
        )

        self._basic_auth_provider = BasicAuthAdapter(config=adapter_config)
        logger.info("Initialized Basic Auth provider")

    def _initialize_use_cases(self) -> None:
        """Initialize application use cases."""
        if not self._token_provider:
            msg = "Token provider not initialized"
            raise RuntimeError(msg)

        # Authentication use case
        self._authenticate_use_case = AuthenticateWithJWTUseCase(
            token_provider=self._token_provider
        )

        # Token validation use case
        self._validate_token_use_case = ValidateTokenUseCase(
            token_provider=self._token_provider
        )

        logger.info("Initialized identity use cases")

    # Property accessors for dependencies
    # All properties enforce initialization check via _ensure_initialized()

    @property
    def token_provider(self) -> TokenProvider:
        """Get token provider.

        Returns:
            Token provider instance

        Raises:
            RuntimeError: If container not initialized
        """
        self._ensure_initialized()
        assert self._token_provider is not None
        return self._token_provider

    @property
    def authenticate_use_case(self) -> AuthenticateWithJWTUseCase:
        """Get authenticate use case.

        Returns:
            Authenticate use case instance

        Raises:
            RuntimeError: If container not initialized
        """
        self._ensure_initialized()
        assert self._authenticate_use_case is not None
        return self._authenticate_use_case

    @property
    def validate_token_use_case(self) -> ValidateTokenUseCase:
        """Get validate token use case.

        Returns:
            Validate token use case instance

        Raises:
            RuntimeError: If container not initialized
        """
        self._ensure_initialized()
        assert self._validate_token_use_case is not None
        return self._validate_token_use_case

    @property
    def jwt_config(self) -> JWTConfig:
        """Get JWT configuration.

        Returns:
            JWT configuration
        """
        return self.config.jwt

    @property
    def basic_auth_config(self) -> BasicAuthConfig:
        """Get basic auth configuration.

        Returns:
            Basic auth configuration
        """
        return self.config.basic_auth

    @property
    def api_key_config(self) -> APIKeyConfig:
        """Get API key configuration.

        Returns:
            API key configuration
        """
        return self.config.api_key
