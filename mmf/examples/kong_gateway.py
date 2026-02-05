"""
Example: Using KongRouteSynchronizer for API Gateway Integration

This example shows how to automatically synchronize service routes
with Kong API Gateway for centralized traffic management.
"""

import asyncio
import os

from mmf.gateway import KongRouteSynchronizer, RouteConfig, ServiceConfig


async def main():
    # Create Kong synchronizer
    kong = KongRouteSynchronizer(
        admin_url=os.getenv("KONG_ADMIN_URL", "http://localhost:8001"),
        admin_token=os.getenv("KONG_ADMIN_TOKEN"),
        workspace="default",
        auto_sync_interval=60,
    )

    await kong.start()

    try:
        # Define services
        services = [
            ServiceConfig(
                name="issuance-service",
                url="http://issuance-service:8005",
                retries=3,
                connect_timeout=5000,
                tags=["credentials", "issuance"],
            ),
            ServiceConfig(
                name="verification-service",
                url="http://verification-service:8006",
                retries=3,
                connect_timeout=5000,
                tags=["credentials", "verification"],
            ),
        ]

        # Define routes
        routes = [
            RouteConfig(
                name="issuance-api",
                service_name="issuance-service",
                paths=["/v1/issuance"],
                methods=["GET", "POST", "PUT", "DELETE"],
                strip_path=False,
                tags=["api", "credentials"],
                plugins=[
                    {
                        "name": "rate-limiting",
                        "config": {
                            "minute": 100,
                            "policy": "local",
                        },
                    },
                    {
                        "name": "cors",
                        "config": {
                            "origins": ["*"],
                            "methods": ["GET", "POST", "PUT", "DELETE"],
                        },
                    },
                ],
            ),
            RouteConfig(
                name="verification-api",
                service_name="verification-service",
                paths=["/v1/verification"],
                methods=["GET", "POST"],
                strip_path=False,
                tags=["api", "credentials"],
                plugins=[
                    {
                        "name": "rate-limiting",
                        "config": {
                            "minute": 200,
                            "policy": "local",
                        },
                    },
                ],
            ),
        ]

        # Synchronize all routes
        result = await kong.sync_routes(services, routes)
        print(f"Sync result: {result}")

        # Individual operations
        await kong.register_service(
            ServiceConfig(
                name="new-service",
                url="http://new-service:9000",
            )
        )

        await kong.register_route(
            RouteConfig(
                name="new-route",
                service_name="new-service",
                paths=["/v1/new"],
            )
        )

        # Statistics
        stats = kong.get_stats()
        print(f"Kong stats: {stats}")

    finally:
        await kong.stop()


if __name__ == "__main__":
    asyncio.run(main())
