"""
End-to-end tests for MMF framework.

Tests complete user workflows with real services and minimal mocking.
"""

import asyncio
import random
import re
import subprocess
import time
from pathlib import Path

import httpx
import pytest
import yaml

from mmf_new.framework.events import Event


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
class TestEndToEnd:
    """End-to-end tests for complete workflows."""

    async def test_service_lifecycle_management(
        self, temp_dir, real_database_connection, real_redis_client
    ):
        """Test complete service lifecycle from creation to shutdown."""
        service_name = "test-lifecycle-service"
        service_dir = temp_dir / service_name

        # Step 1: Create service using CLI
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--with-database",
                "--with-monitoring",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert service_dir.exists()

        # Step 2: Verify service structure
        required_files = ["main.py", "config.yaml", "requirements.txt", "Dockerfile"]

        for file_name in required_files:
            assert (service_dir / file_name).exists(), f"Missing {file_name}"

        # Step 3: Build and start service
        build_result = subprocess.run(
            ["docker", "build", "-t", f"{service_name}:test", "."],
            capture_output=True,
            text=True,
            cwd=service_dir,
        )

        assert build_result.returncode == 0, f"Docker build failed: {build_result.stderr}"

        # Step 4: Run service in container
        run_result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                f"{service_name}-container",
                "-p",
                "8080:8080",
                "-e",
                "DATABASE_URL=postgresql://test:test@host.docker.internal:5432/test",
                "-e",
                "REDIS_URL=redis://host.docker.internal:6379",
                f"{service_name}:test",
            ],
            capture_output=True,
            text=True,
        )

        container_id = run_result.stdout.strip()

        try:
            # Wait for service to start
            await asyncio.sleep(5)

            # Step 5: Test service health

            async with httpx.AsyncClient() as client:
                health_response = await client.get("http://localhost:8080/health")
                assert health_response.status_code == 200

                health_data = health_response.json()
                assert health_data["status"] == "healthy"

            # Step 6: Test service functionality
            async with httpx.AsyncClient() as client:
                # Test creating a resource
                create_response = await client.post(
                    "http://localhost:8080/items",
                    json={"name": "test-item", "description": "Test description"},
                )
                assert create_response.status_code == 201

                item_data = create_response.json()
                item_id = item_data["id"]

                # Test retrieving the resource
                get_response = await client.get(f"http://localhost:8080/items/{item_id}")
                assert get_response.status_code == 200

                retrieved_item = get_response.json()
                assert retrieved_item["name"] == "test-item"

            # Step 7: Test metrics endpoint
            async with httpx.AsyncClient() as client:
                metrics_response = await client.get("http://localhost:8080/metrics")
                assert metrics_response.status_code == 200

                # Verify metrics format
                metrics_text = metrics_response.text
                assert "http_requests_total" in metrics_text
                assert "service_up" in metrics_text

        finally:
            # Cleanup: Stop and remove container
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)
            subprocess.run(["docker", "rmi", f"{service_name}:test"], capture_output=True)

    async def test_multi_service_communication(
        self, temp_dir, real_database_connection, real_redis_client
    ):
        """Test communication between multiple services."""
        # Create two services
        user_service_dir = temp_dir / "user-service"
        order_service_dir = temp_dir / "order-service"

        # Create user service
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                "user-service",
                "--type",
                "fastapi",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Create order service
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                "order-service",
                "--type",
                "fastapi",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Build both services
        for service_dir, service_name in [
            (user_service_dir, "user-service"),
            (order_service_dir, "order-service"),
        ]:
            subprocess.run(
                ["docker", "build", "-t", f"{service_name}:test", "."],
                capture_output=True,
                text=True,
                cwd=service_dir,
            )

        # Start both services
        user_container = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "user-service-container",
                "-p",
                "8081:8080",
                "-e",
                "SERVICE_NAME=user-service",
                "user-service:test",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()

        order_container = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "order-service-container",
                "-p",
                "8082:8080",
                "-e",
                "SERVICE_NAME=order-service",
                "-e",
                "USER_SERVICE_URL=http://host.docker.internal:8081",
                "order-service:test",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()

        try:
            # Wait for services to start
            await asyncio.sleep(10)

            # Test user service
            async with httpx.AsyncClient() as client:
                user_response = await client.post(
                    "http://localhost:8081/users",
                    json={"name": "John Doe", "email": "john@example.com"},
                )
                assert user_response.status_code == 201
                user_data = user_response.json()
                user_id = user_data["id"]

            # Test order service calling user service
            async with httpx.AsyncClient() as client:
                order_response = await client.post(
                    "http://localhost:8082/orders",
                    json={"user_id": user_id, "product_id": 123, "quantity": 2},
                )
                assert order_response.status_code == 201
                order_data = order_response.json()
                assert order_data["user_id"] == user_id

        finally:
            # Cleanup
            for container in [user_container, order_container]:
                subprocess.run(["docker", "stop", container], capture_output=True)
                subprocess.run(["docker", "rm", container], capture_output=True)

            for service_name in ["user-service", "order-service"]:
                subprocess.run(["docker", "rmi", f"{service_name}:test"], capture_output=True)

    async def test_event_driven_workflow(
        self, temp_dir, real_database_connection, real_redis_client, real_event_bus
    ):
        """Test event-driven workflow across services."""
        workflow_events = []

        # Event handlers to track workflow
        async def track_user_created(event):
            workflow_events.append(("user_created", event.data))

        async def track_welcome_email_sent(event):
            workflow_events.append(("welcome_email_sent", event.data))

        async def track_user_profile_created(event):
            workflow_events.append(("user_profile_created", event.data))

        # Register event handlers
        real_event_bus.register_handler(
            name="track-user-created", event_type="user.created", handler_func=track_user_created
        )

        real_event_bus.register_handler(
            name="track-welcome-email",
            event_type="email.welcome.sent",
            handler_func=track_welcome_email_sent,
        )

        real_event_bus.register_handler(
            name="track-profile-created",
            event_type="profile.created",
            handler_func=track_user_profile_created,
        )

        await real_event_bus.start()

        # Simulate user registration workflow

        # Step 1: User registration
        user_created_event = Event(
            id="user-created-123",
            type="user.created",
            data={"user_id": 123, "email": "test@example.com", "name": "Test User"},
        )

        await real_event_bus.publish(user_created_event)

        # Step 2: Welcome email service responds
        email_sent_event = Event(
            id="email-sent-123",
            type="email.welcome.sent",
            data={"user_id": 123, "email": "test@example.com", "template": "welcome"},
        )

        await real_event_bus.publish(email_sent_event)

        # Step 3: Profile service responds
        profile_created_event = Event(
            id="profile-created-123",
            type="profile.created",
            data={"user_id": 123, "profile_id": 456},
        )

        await real_event_bus.publish(profile_created_event)

        # Wait for event processing
        await asyncio.sleep(1.0)

        # Verify workflow completion
        assert len(workflow_events) == 3

        event_types = [event[0] for event in workflow_events]
        assert "user_created" in event_types
        assert "welcome_email_sent" in event_types
        assert "user_profile_created" in event_types

        # Verify event data
        user_event = next(e for e in workflow_events if e[0] == "user_created")
        assert user_event[1]["user_id"] == 123

        await real_event_bus.stop()

    async def test_database_migration_and_seeding(
        self, temp_dir, real_database_connection, postgres_container
    ):
        """Test database migration and seeding workflows."""
        # Create service with database migrations
        service_name = "db-test-service"
        service_dir = temp_dir / service_name

        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--with-database",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Verify migration files were created
        migrations_dir = service_dir / "migrations"
        assert migrations_dir.exists()

        migration_files = list(migrations_dir.glob("*.sql"))
        assert len(migration_files) > 0

        # Get database connection details from container
        db_host = postgres_container.get_container_host_ip()
        db_port = postgres_container.get_exposed_port(5432)
        db_name = postgres_container.dbname
        db_user = postgres_container.username
        db_password = postgres_container.password

        # Run migrations
        migration_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "db",
                "migrate",
                "--service-path",
                str(service_dir),
                "--db-host",
                db_host,
                "--db-port",
                str(db_port),
                "--db-name",
                db_name,
                "--db-user",
                db_user,
                "--db-password",
                db_password,
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert migration_result.returncode == 0

        # Verify tables were created
        tables = await real_database_connection.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )

        table_names = [table["table_name"] for table in tables]
        assert "users" in table_names or "items" in table_names

        # Run seed data
        seed_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "db",
                "seed",
                "--service-path",
                str(service_dir),
                "--db-host",
                db_host,
                "--db-port",
                str(db_port),
                "--db-name",
                db_name,
                "--db-user",
                db_user,
                "--db-password",
                db_password,
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert seed_result.returncode == 0

        # Verify seed data was inserted
        if "users" in table_names:
            users = await real_database_connection.fetch("SELECT * FROM users")
            assert len(users) > 0
        elif "items" in table_names:
            items = await real_database_connection.fetch("SELECT * FROM items")
            assert len(items) > 0

    async def test_monitoring_and_observability(
        self, temp_dir, real_database_connection, real_redis_client
    ):
        """Test monitoring and observability features."""
        service_name = "monitoring-test-service"
        service_dir = temp_dir / service_name

        # Create service with monitoring enabled
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--with-monitoring",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Build and start service
        subprocess.run(
            ["docker", "build", "-t", f"{service_name}:test", "."],
            capture_output=True,
            text=True,
            cwd=service_dir,
        )

        container_id = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                f"{service_name}-container",
                "-p",
                "8083:8080",
                f"{service_name}:test",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()

        try:
            await asyncio.sleep(5)

            # Generate some traffic for metrics
            async with httpx.AsyncClient() as client:
                for _i in range(10):
                    await client.get("http://localhost:8083/health")
                    await client.get("http://localhost:8083/items")

            # Check metrics endpoint
            async with httpx.AsyncClient() as client:
                metrics_response = await client.get("http://localhost:8083/metrics")
                assert metrics_response.status_code == 200

                metrics_text = metrics_response.text

                # Verify standard metrics
                assert "http_requests_total" in metrics_text
                assert "http_request_duration_seconds" in metrics_text
                assert "service_up" in metrics_text

                # Verify custom metrics
                assert "mmf_framework" in metrics_text

            # Check health endpoint details
            async with httpx.AsyncClient() as client:
                health_response = await client.get("http://localhost:8083/health")
                health_data = health_response.json()

                assert "status" in health_data
                assert "checks" in health_data
                assert "version" in health_data
                assert "uptime" in health_data

                # Verify health checks
                checks = health_data["checks"]
                assert "database" in checks or "redis" in checks

        finally:
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)
            subprocess.run(["docker", "rmi", f"{service_name}:test"], capture_output=True)

    async def test_configuration_management(self, temp_dir):
        """Test configuration management across environments."""
        service_name = "config-test-service"
        service_dir = temp_dir / service_name

        # Create service
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Verify environment-specific configs were created (new MMF structure)
        config_files = [
            "mmf_new/config/base.yaml",
            "mmf_new/config/environments/development.yaml",
            "mmf_new/config/environments/testing.yaml",
            "mmf_new/config/environments/production.yaml",
        ]

        for config_file in config_files:
            config_path = service_dir / config_file
            assert config_path.exists(), f"Missing {config_file}"

            # Verify config content

            with open(config_path) as f:
                config_data = yaml.safe_load(f)

            assert "service_name" in config_data
            assert "environment" in config_data
            assert config_data["service_name"] == service_name

        # Test config validation
        validate_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "config",
                "validate",
                "--service-path",
                str(service_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert validate_result.returncode == 0

        # Test config merging
        merge_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "config",
                "show",
                "--service-path",
                str(service_dir),
                "--environment",
                "development",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        assert merge_result.returncode == 0
        assert service_name in merge_result.stdout

    async def test_security_features(self, temp_dir):
        """Test security features and compliance."""
        service_name = "security-test-service"
        service_dir = temp_dir / service_name

        # Create service with security features
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--with-auth",
                "--with-tls",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Verify security files were created
        security_files = [
            "certs/server.crt",
            "certs/server.key",
            "auth/jwt_config.py",
            "middleware/security.py",
        ]

        for security_file in security_files:
            security_path = service_dir / security_file
            assert security_path.exists(), f"Missing {security_file}"

        # Run security scan
        security_result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "security",
                "scan",
                "--service-path",
                str(service_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Should pass basic security checks
        assert security_result.returncode == 0

        # Verify no critical vulnerabilities
        assert "CRITICAL" not in security_result.stdout
        assert "HIGH" not in security_result.stdout

    @pytest.mark.performance
    async def test_performance_benchmarks(
        self, temp_dir, real_database_connection, real_redis_client
    ):
        """Test performance benchmarks and load handling."""
        service_name = "perf-test-service"
        service_dir = temp_dir / service_name

        # Create optimized service
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "marty_mmf",
                "create",
                "service",
                "--name",
                service_name,
                "--type",
                "fastapi",
                "--with-caching",
                "--with-monitoring",
                "--output",
                str(temp_dir),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Build and start service
        subprocess.run(
            ["docker", "build", "-t", f"{service_name}:test", "."],
            capture_output=True,
            text=True,
            cwd=service_dir,
        )

        container_id = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                f"{service_name}-container",
                "-p",
                "8084:8080",
                "-e",
                "REDIS_URL=redis://host.docker.internal:6379",
                f"{service_name}:test",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()

        try:
            await asyncio.sleep(5)

            # Performance test using concurrent requests

            async def make_request(client, url):
                start_time = time.time()
                response = await client.get(url)
                end_time = time.time()
                return response.status_code, end_time - start_time

            # Test concurrent requests
            async with httpx.AsyncClient() as client:
                tasks = []
                for _i in range(100):  # 100 concurrent requests
                    task = make_request(client, "http://localhost:8084/health")
                    tasks.append(task)

                results = await asyncio.gather(*tasks)

                # Verify all requests succeeded
                success_count = sum(1 for status, _ in results if status == 200)
                assert success_count >= 95  # 95% success rate

                # Verify response times
                response_times = [duration for _, duration in results]
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)

                # Performance assertions
                assert (
                    avg_response_time < 0.2
                )  # Average under 200ms (realistic for Docker test environment)
                assert max_response_time < 1.0  # Max under 1 second

            # Check metrics after load test
            async with httpx.AsyncClient() as client:
                metrics_response = await client.get("http://localhost:8084/metrics")
                metrics_text = metrics_response.text

                # Verify metrics show the load
                assert "http_requests_total" in metrics_text
                # Should have at least 100 requests recorded

                requests_match = re.search(r"http_requests_total\{.*\} (\d+)", metrics_text)
                if requests_match:
                    total_requests = int(requests_match.group(1))
                    assert total_requests >= 100

        finally:
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)
            subprocess.run(["docker", "rmi", f"{service_name}:test"], capture_output=True)
