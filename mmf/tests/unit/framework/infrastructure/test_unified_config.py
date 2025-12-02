import sys
from unittest.mock import MagicMock, patch

# Mock cloud dependencies before importing unified_config
sys.modules["boto3"] = MagicMock()
sys.modules["azure.identity"] = MagicMock()
sys.modules["azure.keyvault.secrets"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.secretmanager"] = MagicMock()
sys.modules["kubernetes"] = MagicMock()

import pytest
from pydantic import BaseModel

from mmf.framework.infrastructure.unified_config import (
    ConfigurationStrategy,
    Environment,
    HostingEnvironment,
    UnifiedConfigurationManager,
    create_unified_config_manager,
)


class TestConfig(BaseModel):
    service_name: str = "test-service"
    debug: bool = False


@pytest.mark.asyncio
class TestUnifiedConfig:
    async def test_create_manager_local(self):
        manager = create_unified_config_manager(
            service_name="test-service",
            environment=Environment.TESTING,
            config_class=TestConfig,
            hosting_environment=HostingEnvironment.LOCAL,
            enable_file_secrets=False,
        )
        assert isinstance(manager, UnifiedConfigurationManager)
        assert manager.context.service_name == "test-service"
        assert manager.context.environment == Environment.TESTING

    async def test_load_config_defaults(self):
        manager = create_unified_config_manager(
            service_name="test-service",
            environment=Environment.TESTING,
            config_class=TestConfig,
            hosting_environment=HostingEnvironment.LOCAL,
            enable_file_secrets=False,
        )
        # Mock the config loading part since we don't have actual config files
        with patch.object(
            manager, "_load_hierarchical_config", return_value={"service_name": "test-service"}
        ):
            config = await manager.get_configuration()
            assert config.service_name == "test-service"

    async def test_health_check(self):
        manager = create_unified_config_manager(
            service_name="test-service",
            environment=Environment.TESTING,
            config_class=TestConfig,
            hosting_environment=HostingEnvironment.LOCAL,
            enable_file_secrets=False,
        )
        health = await manager.health_check()
        assert isinstance(health, dict)
