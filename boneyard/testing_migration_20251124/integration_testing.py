"""
Integration testing framework for Marty Microservices Framework.

This module provides comprehensive integration testing capabilities including
service-to-service integration tests, database integration tests, message
queue integration tests, and end-to-end testing scenarios.
"""

import asyncio
import builtins
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp
import docker
import pika
import psycopg2
import pymongo
import redis

from .core import TestCase, TestMetrics, TestResult, TestSeverity, TestStatus, TestType

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Types of integration tests."""

    SERVICE_TO_SERVICE = "service_to_service"
    DATABASE_INTEGRATION = "database_integration"
    MESSAGE_QUEUE = "message_queue"
    EXTERNAL_API = "external_api"
    END_TO_END = "end_to_end"
    COMPONENT_INTEGRATION = "component_integration"


class TestEnvironment(Enum):
    """Test environment types."""

    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    STAGING = "staging"
    SANDBOX = "sandbox"


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration."""

    name: str
    url: str
    health_check_path: str = "/health"
    timeout: float = 30.0
    headers: builtins.dict[str, str] = field(default_factory=dict)
    auth: builtins.dict[str, Any] | None = None


@dataclass
class DatabaseConfig:
    """Database configuration."""

    type: str  # postgres, mysql, mongodb, redis, etc.
    host: str
    port: int
    database: str
    username: str
    password: str
    connection_params: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageQueueConfig:
    """Message queue configuration."""

    type: str  # rabbitmq, kafka, sqs, etc.
    host: str
    port: int
    queue_name: str
    username: str | None = None
    password: str | None = None
    connection_params: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class TestScenario:
    """Integration test scenario definition."""

    name: str
    description: str
    steps: builtins.list[Callable] = field(default_factory=list)
    setup_steps: builtins.list[Callable] = field(default_factory=list)
    teardown_steps: builtins.list[Callable] = field(default_factory=list)
    dependencies: builtins.list[str] = field(default_factory=list)
    timeout: float = 300.0
    retry_attempts: int = 3


class IntegrationTestEnvironment:
    """Manages integration test environment."""

    def __init__(self, environment_type: TestEnvironment = TestEnvironment.LOCAL):
        self.environment_type = environment_type
        self.services: builtins.dict[str, ServiceEndpoint] = {}
        self.databases: builtins.dict[str, DatabaseConfig] = {}
        self.message_queues: builtins.dict[str, MessageQueueConfig] = {}
        self.containers: builtins.dict[str, Any] = {}
        self.docker_client: docker.DockerClient | None = None

        if environment_type == TestEnvironment.DOCKER:
            self.docker_client = docker.from_env()

    def add_service(self, service: ServiceEndpoint):
        """Add service endpoint."""
        self.services[service.name] = service
        logger.info(f"Added service: {service.name} at {service.url}")

    def add_database(self, name: str, config: DatabaseConfig):
        """Add database configuration."""
        self.databases[name] = config
        logger.info(f"Added database: {name} ({config.type})")

    def add_message_queue(self, name: str, config: MessageQueueConfig):
        """Add message queue configuration."""
        self.message_queues[name] = config
        logger.info(f"Added message queue: {name} ({config.type})")

    async def setup(self):
        """Setup test environment."""
        logger.info(f"Setting up {self.environment_type.value} test environment")

        if self.environment_type == TestEnvironment.DOCKER:
            await self._setup_docker_environment()
        elif self.environment_type == TestEnvironment.LOCAL:
            await self._setup_local_environment()

        # Wait for services to be ready
        await self._wait_for_services()

    async def teardown(self):
        """Teardown test environment."""
        logger.info("Tearing down test environment")

        if self.environment_type == TestEnvironment.DOCKER:
            await self._teardown_docker_environment()

    async def _setup_docker_environment(self):
        """Setup Docker-based test environment."""
        # This is a simplified implementation
        # In practice, you might use docker-compose or orchestration tools

    async def _setup_local_environment(self):
        """Setup local test environment."""
        # Verify local services are available

    async def _teardown_docker_environment(self):
        """Teardown Docker containers."""
        for container_name, container in self.containers.items():
            try:
                container.stop()
                container.remove()
                logger.info(f"Stopped and removed container: {container_name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup container {container_name}: {e}")

    async def _wait_for_services(self):
        """Wait for all services to be ready."""
        logger.info("Waiting for services to be ready...")

        async with aiohttp.ClientSession() as session:
            for _service_name, service in self.services.items():
                await self._wait_for_service(session, service)

    async def _wait_for_service(self, session: aiohttp.ClientSession, service: ServiceEndpoint):
        """Wait for a specific service to be ready."""
        health_url = f"{service.url.rstrip('/')}{service.health_check_path}"
        max_attempts = 30
        attempt = 0

        while attempt < max_attempts:
            try:
                async with session.get(health_url, timeout=5) as response:
                    if response.status == 200:
                        logger.info(f"Service {service.name} is ready")
                        return
            except Exception:
                pass

            attempt += 1
            await asyncio.sleep(2)

        raise Exception(f"Service {service.name} failed to become ready")


class DatabaseIntegrationHelper:
    """Helper for database integration testing."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Connect to database."""
        if self.config.type == "postgresql":
            self.connection = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                **self.config.connection_params,
            )
        elif self.config.type == "mongodb":
            self.connection = pymongo.MongoClient(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                **self.config.connection_params,
            )
        elif self.config.type == "redis":
            self.connection = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                **self.config.connection_params,
            )
        else:
            raise ValueError(f"Unsupported database type: {self.config.type}")

        logger.info(f"Connected to {self.config.type} database")

    async def disconnect(self):
        """Disconnect from database."""
        if self.connection:
            if hasattr(self.connection, "close"):
                self.connection.close()
            self.connection = None
            logger.info("Disconnected from database")

    def execute_query(self, query: str, params: builtins.tuple = None):
        """Execute database query."""
        if self.config.type == "postgresql":
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.fetchall()
        if self.config.type == "mongodb":
            # For MongoDB, query should be a collection name and operation
            collection_name, operation = query.split(":", 1)
            collection = self.connection[self.config.database][collection_name]

            # Security: Replace dangerous eval() with safe method dispatch
            # Only allow specific safe operations
            safe_operations = {
                "find()": lambda: list(collection.find()),
                "find_one()": lambda: collection.find_one(),
                "count_documents({})": lambda: collection.count_documents({}),
                "estimated_document_count()": lambda: collection.estimated_document_count(),
            }

            if operation in safe_operations:
                return safe_operations[operation]()
            else:
                raise ValueError(f"Unsafe MongoDB operation: {operation}")

        if self.config.type == "redis":
            # For Redis, query should be a command
            # Security: Replace dangerous eval() with safe method dispatch
            # Only allow specific safe operations
            safe_commands = {
                "ping()": lambda: self.connection.ping(),
                "info()": lambda: self.connection.info(),
                "dbsize()": lambda: self.connection.dbsize(),
                'get("test")': lambda: self.connection.get("test"),
            }

            if query in safe_commands:
                return safe_commands[query]()
            else:
                raise ValueError(f"Unsafe Redis command: {query}")
        raise ValueError(f"Query execution not supported for {self.config.type}")

    def insert_test_data(self, table_or_collection: str, data: Any):
        """Insert test data."""
        if self.config.type == "postgresql":
            if isinstance(data, dict):
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["%s"] * len(data))
                query = f"INSERT INTO {table_or_collection} ({columns}) VALUES ({placeholders})"
                self.execute_query(query, tuple(data.values()))
            elif isinstance(data, list):
                for record in data:
                    self.insert_test_data(table_or_collection, record)
        elif self.config.type == "mongodb":
            collection = self.connection[self.config.database][table_or_collection]
            if isinstance(data, dict):
                collection.insert_one(data)
            elif isinstance(data, list):
                collection.insert_many(data)
        elif self.config.type == "redis":
            if isinstance(data, dict):
                for key, value in data.items():
                    self.connection.set(f"{table_or_collection}:{key}", json.dumps(value))

    def cleanup_test_data(self, table_or_collection: str, condition: str = None):
        """Clean up test data."""
        if self.config.type == "postgresql":
            query = f"DELETE FROM {table_or_collection}"
            if condition:
                query += f" WHERE {condition}"
            self.execute_query(query)
        elif self.config.type == "mongodb":
            collection = self.connection[self.config.database][table_or_collection]
            if condition:
                # condition should be a MongoDB filter dict
                collection.delete_many(json.loads(condition))
            else:
                collection.delete_many({})
        elif self.config.type == "redis":
            # For Redis, delete keys matching pattern
            pattern = f"{table_or_collection}:*"
            keys = self.connection.keys(pattern)
            if keys:
                self.connection.delete(*keys)


class MessageQueueIntegrationHelper:
    """Helper for message queue integration testing."""

    def __init__(self, config: MessageQueueConfig):
        self.config = config
        self.connection = None
        self.channel = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Connect to message queue."""
        if self.config.type == "rabbitmq":
            credentials = pika.PlainCredentials(
                self.config.username or "guest", self.config.password or "guest"
            )
            connection_params = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                credentials=credentials,
                **self.config.connection_params,
            )
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()

            # Declare queue if it doesn't exist
            self.channel.queue_declare(queue=self.config.queue_name, durable=True)

        else:
            raise ValueError(f"Unsupported message queue type: {self.config.type}")

        logger.info(f"Connected to {self.config.type} message queue")

    async def disconnect(self):
        """Disconnect from message queue."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.channel = None
            logger.info("Disconnected from message queue")

    def publish_message(self, message: Any, routing_key: str = None):
        """Publish message to queue."""
        if self.config.type == "rabbitmq":
            routing_key = routing_key or self.config.queue_name
            message_body = json.dumps(message) if not isinstance(message, str) else message

            self.channel.basic_publish(
                exchange="",
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                ),
            )
            logger.info(f"Published message to {routing_key}")

    def consume_messages(self, timeout: float = 10.0) -> builtins.list[Any]:
        """Consume messages from queue."""
        messages = []

        if self.config.type == "rabbitmq":
            start_time = time.time()

            def callback(ch, method, properties, body):
                try:
                    message = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    message = body.decode("utf-8")

                messages.append(message)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            self.channel.basic_consume(queue=self.config.queue_name, on_message_callback=callback)

            # Consume messages for specified timeout
            while time.time() - start_time < timeout:
                self.connection.process_data_events(time_limit=1)
                if messages:  # If we got at least one message, we can break early
                    break

        return messages

    def purge_queue(self):
        """Purge all messages from queue."""
        if self.config.type == "rabbitmq":
            self.channel.queue_purge(queue=self.config.queue_name)
            logger.info(f"Purged queue: {self.config.queue_name}")


class ServiceToServiceTestCase(TestCase):
    """Test case for service-to-service integration."""

    def __init__(
        self,
        name: str,
        source_service: ServiceEndpoint,
        target_service: ServiceEndpoint,
        test_scenario: TestScenario,
    ):
        super().__init__(
            name=f"Service Integration: {name}",
            test_type=TestType.INTEGRATION,
            tags=["integration", "service-to-service"],
        )
        self.source_service = source_service
        self.target_service = target_service
        self.test_scenario = test_scenario
        self.session: aiohttp.ClientSession | None = None

    async def setup(self):
        """Setup test case."""
        await super().setup()
        self.session = aiohttp.ClientSession()

        # Execute scenario setup steps
        for setup_step in self.test_scenario.setup_steps:
            if asyncio.iscoroutinefunction(setup_step):
                await setup_step(self)
            else:
                setup_step(self)

    async def teardown(self):
        """Teardown test case."""
        # Execute scenario teardown steps
        for teardown_step in self.test_scenario.teardown_steps:
            try:
                if asyncio.iscoroutinefunction(teardown_step):
                    await teardown_step(self)
                else:
                    teardown_step(self)
            except Exception as e:
                logger.warning(f"Teardown step failed: {e}")

        if self.session:
            await self.session.close()

        await super().teardown()

    async def execute(self) -> TestResult:
        """Execute service-to-service integration test."""
        start_time = datetime.utcnow()
        step_results = []

        try:
            # Execute test scenario steps
            for i, step in enumerate(self.test_scenario.steps):
                step_start = time.time()

                try:
                    if asyncio.iscoroutinefunction(step):
                        result = await step(self)
                    else:
                        result = step(self)

                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": True,
                            "result": result,
                        }
                    )

                except Exception as e:
                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": False,
                            "error": str(e),
                        }
                    )
                    raise e

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "steps_executed": len(step_results),
                        "source_service": self.source_service.name,
                        "target_service": self.target_service.name,
                    },
                ),
                artifacts={"step_results": step_results},
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.FAILED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.HIGH,
                artifacts={"step_results": step_results},
            )

    async def make_request(
        self, service: ServiceEndpoint, path: str, method: str = "GET", **kwargs
    ) -> aiohttp.ClientResponse:
        """Make HTTP request to service."""
        url = f"{service.url.rstrip('/')}{path}"
        headers = {**service.headers, **kwargs.get("headers", {})}

        async with self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=service.timeout),
            **{k: v for k, v in kwargs.items() if k != "headers"},
        ) as response:
            return response


class DatabaseIntegrationTestCase(TestCase):
    """Test case for database integration testing."""

    def __init__(self, name: str, database_config: DatabaseConfig, test_scenario: TestScenario):
        super().__init__(
            name=f"Database Integration: {name}",
            test_type=TestType.INTEGRATION,
            tags=["integration", "database"],
        )
        self.database_config = database_config
        self.test_scenario = test_scenario
        self.db_helper: DatabaseIntegrationHelper | None = None

    async def setup(self):
        """Setup test case."""
        await super().setup()
        self.db_helper = DatabaseIntegrationHelper(self.database_config)
        await self.db_helper.connect()

        # Execute scenario setup steps
        for setup_step in self.test_scenario.setup_steps:
            if asyncio.iscoroutinefunction(setup_step):
                await setup_step(self)
            else:
                setup_step(self)

    async def teardown(self):
        """Teardown test case."""
        # Execute scenario teardown steps
        for teardown_step in self.test_scenario.teardown_steps:
            try:
                if asyncio.iscoroutinefunction(teardown_step):
                    await teardown_step(self)
                else:
                    teardown_step(self)
            except Exception as e:
                logger.warning(f"Teardown step failed: {e}")

        if self.db_helper:
            await self.db_helper.disconnect()

        await super().teardown()

    async def execute(self) -> TestResult:
        """Execute database integration test."""
        start_time = datetime.utcnow()
        step_results = []

        try:
            # Execute test scenario steps
            for i, step in enumerate(self.test_scenario.steps):
                step_start = time.time()

                try:
                    if asyncio.iscoroutinefunction(step):
                        result = await step(self)
                    else:
                        result = step(self)

                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": True,
                            "result": result,
                        }
                    )

                except Exception as e:
                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": False,
                            "error": str(e),
                        }
                    )
                    raise e

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "steps_executed": len(step_results),
                        "database_type": self.database_config.type,
                    },
                ),
                artifacts={"step_results": step_results},
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.FAILED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.HIGH,
                artifacts={"step_results": step_results},
            )


class MessageQueueIntegrationTestCase(TestCase):
    """Test case for message queue integration testing."""

    def __init__(self, name: str, mq_config: MessageQueueConfig, test_scenario: TestScenario):
        super().__init__(
            name=f"Message Queue Integration: {name}",
            test_type=TestType.INTEGRATION,
            tags=["integration", "message-queue"],
        )
        self.mq_config = mq_config
        self.test_scenario = test_scenario
        self.mq_helper: MessageQueueIntegrationHelper | None = None

    async def setup(self):
        """Setup test case."""
        await super().setup()
        self.mq_helper = MessageQueueIntegrationHelper(self.mq_config)
        await self.mq_helper.connect()

        # Execute scenario setup steps
        for setup_step in self.test_scenario.setup_steps:
            if asyncio.iscoroutinefunction(setup_step):
                await setup_step(self)
            else:
                setup_step(self)

    async def teardown(self):
        """Teardown test case."""
        # Execute scenario teardown steps
        for teardown_step in self.test_scenario.teardown_steps:
            try:
                if asyncio.iscoroutinefunction(teardown_step):
                    await teardown_step(self)
                else:
                    teardown_step(self)
            except Exception as e:
                logger.warning(f"Teardown step failed: {e}")

        if self.mq_helper:
            await self.mq_helper.disconnect()

        await super().teardown()

    async def execute(self) -> TestResult:
        """Execute message queue integration test."""
        start_time = datetime.utcnow()
        step_results = []

        try:
            # Execute test scenario steps
            for i, step in enumerate(self.test_scenario.steps):
                step_start = time.time()

                try:
                    if asyncio.iscoroutinefunction(step):
                        result = await step(self)
                    else:
                        result = step(self)

                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": True,
                            "result": result,
                        }
                    )

                except Exception as e:
                    step_duration = time.time() - step_start
                    step_results.append(
                        {
                            "step": i + 1,
                            "duration": step_duration,
                            "success": False,
                            "error": str(e),
                        }
                    )
                    raise e

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "steps_executed": len(step_results),
                        "queue_type": self.mq_config.type,
                    },
                ),
                artifacts={"step_results": step_results},
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.FAILED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.HIGH,
                artifacts={"step_results": step_results},
            )


class IntegrationTestManager:
    """Manages integration testing workflow."""

    def __init__(self, environment: IntegrationTestEnvironment):
        self.environment = environment
        self.test_data_cleanup_callbacks: builtins.list[Callable] = []

    async def setup_environment(self):
        """Setup test environment."""
        await self.environment.setup()

    async def teardown_environment(self):
        """Teardown test environment."""
        # Execute test data cleanup
        for cleanup_callback in reversed(self.test_data_cleanup_callbacks):
            try:
                if asyncio.iscoroutinefunction(cleanup_callback):
                    await cleanup_callback()
                else:
                    cleanup_callback()
            except Exception as e:
                logger.warning(f"Test data cleanup failed: {e}")

        await self.environment.teardown()

    def create_service_test(
        self,
        name: str,
        source_service_name: str,
        target_service_name: str,
        test_scenario: TestScenario,
    ) -> ServiceToServiceTestCase:
        """Create service-to-service integration test."""
        source_service = self.environment.services.get(source_service_name)
        target_service = self.environment.services.get(target_service_name)

        if not source_service:
            raise ValueError(f"Source service not found: {source_service_name}")
        if not target_service:
            raise ValueError(f"Target service not found: {target_service_name}")

        return ServiceToServiceTestCase(name, source_service, target_service, test_scenario)

    def create_database_test(
        self, name: str, database_name: str, test_scenario: TestScenario
    ) -> DatabaseIntegrationTestCase:
        """Create database integration test."""
        database_config = self.environment.databases.get(database_name)

        if not database_config:
            raise ValueError(f"Database not found: {database_name}")

        return DatabaseIntegrationTestCase(name, database_config, test_scenario)

    def create_message_queue_test(
        self, name: str, queue_name: str, test_scenario: TestScenario
    ) -> MessageQueueIntegrationTestCase:
        """Create message queue integration test."""
        mq_config = self.environment.message_queues.get(queue_name)

        if not mq_config:
            raise ValueError(f"Message queue not found: {queue_name}")

        return MessageQueueIntegrationTestCase(name, mq_config, test_scenario)

    def add_test_data_cleanup(self, cleanup_callback: Callable):
        """Add test data cleanup callback."""
        self.test_data_cleanup_callbacks.append(cleanup_callback)


# Utility functions for common integration test scenarios
def create_api_integration_scenario(
    api_calls: builtins.list[builtins.dict[str, Any]],
) -> TestScenario:
    """Create API integration test scenario."""

    async def make_api_calls(test_case: ServiceToServiceTestCase):
        results = []
        for call in api_calls:
            response = await test_case.make_request(
                service=test_case.target_service,
                path=call["path"],
                method=call.get("method", "GET"),
                **call.get("params", {}),
            )

            # Verify response
            expected_status = call.get("expected_status", 200)
            if response.status != expected_status:
                raise AssertionError(f"Expected status {expected_status}, got {response.status}")

            response_data = (
                await response.json()
                if response.content_type == "application/json"
                else await response.text()
            )
            results.append(response_data)

        return results

    return TestScenario(
        name="API Integration Test",
        description="Test API calls between services",
        steps=[make_api_calls],
    )


def create_database_crud_scenario(
    table_name: str, test_data: builtins.list[builtins.dict[str, Any]]
) -> TestScenario:
    """Create database CRUD test scenario."""

    def setup_test_data(test_case: DatabaseIntegrationTestCase):
        test_case.db_helper.insert_test_data(table_name, test_data)

    def test_read_operations(test_case: DatabaseIntegrationTestCase):
        # Example read operation
        if test_case.database_config.type == "postgresql":
            result = test_case.db_helper.execute_query(f"SELECT * FROM {table_name}")
            assert len(result) == len(test_data), (
                f"Expected {len(test_data)} records, got {len(result)}"
            )
        return result

    def cleanup_test_data(test_case: DatabaseIntegrationTestCase):
        test_case.db_helper.cleanup_test_data(table_name)

    return TestScenario(
        name="Database CRUD Test",
        description="Test database create, read, update, delete operations",
        setup_steps=[setup_test_data],
        steps=[test_read_operations],
        teardown_steps=[cleanup_test_data],
    )


def create_message_flow_scenario(
    messages: builtins.list[Any], expected_count: int = None
) -> TestScenario:
    """Create message queue flow test scenario."""

    def publish_messages(test_case: MessageQueueIntegrationTestCase):
        for message in messages:
            test_case.mq_helper.publish_message(message)
        return len(messages)

    def consume_and_verify_messages(test_case: MessageQueueIntegrationTestCase):
        received_messages = test_case.mq_helper.consume_messages(timeout=10.0)
        expected = expected_count if expected_count is not None else len(messages)

        assert len(received_messages) == expected, (
            f"Expected {expected} messages, got {len(received_messages)}"
        )
        return received_messages

    def cleanup_queue(test_case: MessageQueueIntegrationTestCase):
        test_case.mq_helper.purge_queue()

    return TestScenario(
        name="Message Flow Test",
        description="Test message publishing and consumption",
        steps=[publish_messages, consume_and_verify_messages],
        teardown_steps=[cleanup_queue],
    )
