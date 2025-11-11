# Migration Quick Reference

## Legacy to Framework Migration

### Import Updates

**Before (Legacy):**

```python
from marty_chassis.config import ConfigManager
from marty_chassis.logging import Logger
from marty_chassis.discovery import ServiceRegistry
```

**After (Framework):**

```python
from marty_msf.framework.config import create_service_config
from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.discovery import ServiceDiscoveryManager
```

### Configuration Updates

**Before:**

```python
config = ConfigManager.load("service.yaml")
```

**After:**

```python
config = create_service_config("your_service")
```

### Plugin Configuration

**Before (Deprecated):**

```python
plugin_config = PluginContext.get_plugin_config_sync()
```

**After:**

```python
from marty_msf.framework.plugins import PluginConfigManager
plugin_config = await PluginConfigManager.get_config()
```

### gRPC Server Updates

**Before:**

```python
from framework.grpc.service_factory import GRPCServiceFactory
server = GRPCServiceFactory.create_server()
```

**After:**

```python
from marty_msf.framework.grpc import UnifiedGrpcServer
server = UnifiedGrpcServer(config)
```

**Testing:**

```python
from framework.testing import (
    TestEventCollector,
    ServiceTestMixin,
    AsyncTestCase
)
```

### Service Creation Pattern

**Modern Service Template:**

```python
#!/usr/bin/env python3
"""
Modern Marty Microservice

Uses the unified framework patterns.
"""

import asyncio
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from framework.config_factory import create_service_config
from framework.logging import UnifiedServiceLogger
from observability import init_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Service lifecycle management."""
    # Startup
    logger.info("Service starting up...")
    await init_observability()

    yield

    # Shutdown
    logger.info("Service shutting down...")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    config = create_service_config()
    logger = UnifiedServiceLogger(__name__)

    app = FastAPI(
        title="My Service",
        version="1.0.0",
        lifespan=lifespan
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Legacy Reference (For Historical Context)

The following patterns were used in the legacy `marty_chassis` system and have been fully migrated:

- `from marty_chassis import ChassisConfig` → `from framework.config_factory import create_service_config`
- `from marty_chassis.logger import get_logger` → `from framework.logging import UnifiedServiceLogger`
- `from marty_chassis.metrics import MetricsCollector` → `from observability.monitoring import MetricsCollector`
- `from marty_chassis.plugins.manager import PluginManager` → `from framework.plugins import PluginManager`

All chassis code has been successfully migrated and removed from the repository.
