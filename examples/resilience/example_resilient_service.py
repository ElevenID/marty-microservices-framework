"""
Example Service with Resilience Framework Integration

Demonstrates how to use the enhanced resilience framework with
connection pooling, circuit breakers, and load testing.
"""

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from marty_msf.framework.resilience import (
    HTTPPoolConfig,
    PoolConfig,
    PoolType,
    RedisPoolConfig,
    ResilienceConfig,
    ResilienceMiddleware,
    close_all_pools,
    get_pool_manager,
    initialize_pools,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    await setup_resilience_framework()
    logger.info("Resilience framework initialized")

    yield

    # Shutdown
    await close_all_pools()
    logger.info("Resilience framework closed")


async def setup_resilience_framework():
    """Initialize resilience framework with connection pools"""

    # Configure connection pools
    pool_configs = [
        # HTTP pool for external API calls
        PoolConfig(
            name="external_api",
            pool_type=PoolType.HTTP,
            http_config=HTTPPoolConfig(
                max_connections=50,
                max_connections_per_host=20,
                connect_timeout=5.0,
                request_timeout=15.0,
                health_check_interval=30.0
            ),
            tags={"service": "external_api", "environment": "production"}
        ),

        # Redis pool for caching
        PoolConfig(
            name="cache",
            pool_type=PoolType.REDIS,
            redis_config=RedisPoolConfig(
                host="localhost",
                port=6379,
                max_connections=30,
                decode_responses=True,
                health_check_interval=30.0
            ),
            tags={"service": "cache", "environment": "production"}
        )
    ]

    # Initialize connection pools
    await initialize_pools(pool_configs)


# Create FastAPI app with resilience middleware
app = FastAPI(
    title="Resilience Example Service",
    description="Example service demonstrating resilience framework integration",
    version="1.0.0",
    lifespan=lifespan
)

# Configure resilience middleware
resilience_config = ResilienceConfig(
    enable_circuit_breaker=True,
    enable_bulkhead=True,
    enable_connection_pools=True,
    enable_rate_limiting=True,

    # Circuit breaker settings
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_timeout=60.0,

    # Bulkhead settings
    bulkhead_max_concurrent=100,
    bulkhead_timeout=30.0,

    # Rate limiting
    rate_limit_requests_per_minute=1000,

    # Request timeout
    request_timeout=30.0,

    # Excluded paths (no resilience patterns applied)
    excluded_paths=["/health", "/metrics", "/docs", "/openapi.json"]
)

# Add resilience middleware
app.add_middleware(ResilienceMiddleware, config=resilience_config)


@app.get("/health")
async def health_check():
    """Health check endpoint (excluded from resilience patterns)"""
    pool_manager = get_pool_manager()
    health_status = await pool_manager.health_check()

    return {
        "status": "healthy",
        "timestamp": "2024-12-17T10:30:00Z",
        "pools": health_status
    }


@app.get("/metrics")
async def get_metrics():
    """Metrics endpoint showing resilience framework status"""
    pool_manager = get_pool_manager()
    metrics = pool_manager.get_metrics()

    return {
        "resilience_metrics": metrics,
        "timestamp": "2024-12-17T10:30:00Z"
    }


@app.get("/api/external-data")
async def get_external_data():
    """Example endpoint that uses HTTP connection pool for external API call"""
    try:
        pool_manager = get_pool_manager()
        http_pool = await pool_manager.get_pool("external_api")

        # Make request through connection pool (with automatic retries)
        response = await http_pool.get("https://jsonplaceholder.typicode.com/posts/1")

        if response.status == 200:
            data = await response.json()
            return {"data": data, "pool_metrics": http_pool.get_metrics()}
        else:
            raise HTTPException(status_code=response.status, detail="External API error")

    except Exception as e:
        logger.error(f"Failed to fetch external data: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@app.get("/api/cache/{key}")
async def get_cached_value(key: str):
    """Example endpoint that uses Redis connection pool for caching"""
    try:
        pool_manager = get_pool_manager()
        redis_pool = await pool_manager.get_redis_pool("cache")

        # Check cache first
        cached_value = await redis_pool.get(f"api:cache:{key}")

        if cached_value:
            return {
                "key": key,
                "value": cached_value,
                "source": "cache",
                "pool_metrics": redis_pool.get_metrics()
            }
        else:
            # Simulate data generation and caching
            generated_value = f"generated_data_for_{key}"
            await redis_pool.set(f"api:cache:{key}", generated_value, ex=300)  # 5 min TTL

            return {
                "key": key,
                "value": generated_value,
                "source": "generated",
                "pool_metrics": redis_pool.get_metrics()
            }

    except Exception as e:
        logger.error(f"Cache operation failed: {e}")
        raise HTTPException(status_code=503, detail="Cache service unavailable")


@app.post("/api/cache/{key}")
async def set_cached_value(key: str, value: Dict[str, Any]):
    """Set a value in cache using Redis connection pool"""
    try:
        pool_manager = get_pool_manager()
        redis_pool = await pool_manager.get_redis_pool("cache")

        # Store in cache
        await redis_pool.set(f"api:cache:{key}", str(value.get("data", "")), ex=300)

        return {
            "key": key,
            "status": "stored",
            "ttl": 300,
            "pool_metrics": redis_pool.get_metrics()
        }

    except Exception as e:
        logger.error(f"Cache write failed: {e}")
        raise HTTPException(status_code=503, detail="Cache service unavailable")


@app.get("/api/heavy-computation")
async def heavy_computation():
    """Simulated heavy computation endpoint (tests bulkhead isolation)"""
    try:
        # Simulate CPU-intensive work
        await asyncio.sleep(2.0)  # Simulate processing time

        result = {
            "computation_result": "complex_calculation_completed",
            "processing_time": 2.0,
            "status": "success"
        }

        return result

    except Exception as e:
        logger.error(f"Heavy computation failed: {e}")
        raise HTTPException(status_code=500, detail="Computation failed")


@app.get("/api/error-prone")
async def error_prone_endpoint():
    """Endpoint that occasionally fails (tests circuit breaker)"""

    # Simulate random failures (20% failure rate)
    if random.random() < 0.2:
        logger.warning("Simulated service failure")
        raise HTTPException(status_code=503, detail="Simulated service failure")

    return {
        "status": "success",
        "message": "This endpoint occasionally fails to test circuit breaker behavior"
    }


@app.get("/api/pool-status")
async def get_pool_status():
    """Get status information for all connection pools"""
    try:
        pool_manager = get_pool_manager()
        pools_info = pool_manager.list_pools()

        return {
            "pools": pools_info,
            "total_pools": len(pools_info),
            "timestamp": "2024-12-17T10:30:00Z"
        }

    except Exception as e:
        logger.error(f"Failed to get pool status: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve pool status")


if __name__ == "__main__":

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run the service
    uvicorn.run(
        "example_resilient_service:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=True
    )
