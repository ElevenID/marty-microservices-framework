"""
Integration tests for NATS adapter using Testcontainers.
"""

import asyncio

import docker
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from mmf.framework.messaging.domain.extended import (
    MessageMetadata,
    MessagingPattern,
    NATSConfig,
)
from mmf.framework.messaging.infrastructure.adapters.nats import NATSBackend


def is_docker_available():
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


class NatsContainer(DockerContainer):
    """NATS container for testing."""

    def __init__(self, image="nats:latest", **kwargs):
        super().__init__(image, **kwargs)
        self.with_exposed_ports(4222)
        self.with_command("-js")  # Enable JetStream

    def get_connection_url(self) -> str:
        host = self.get_container_host_ip()
        port = self.get_exposed_port(4222)
        return f"nats://{host}:{port}"


@pytest.fixture(scope="module")
def nats_container():
    """Start NATS container."""
    if not is_docker_available():
        pytest.skip("Docker is not available")

    with NatsContainer() as container:
        wait_for_logs(container, "Server is ready")
        yield container


@pytest.fixture
async def nats_backend(nats_container):
    """Create and connect NATS backend."""
    url = nats_container.get_connection_url()
    config = NATSConfig(servers=[url])
    backend = NATSBackend(config)

    await backend.connect()
    yield backend
    await backend.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nats_publish_subscribe(nats_backend):
    """Test basic publish/subscribe with NATS."""
    topic = "test.topic"
    received_messages = []

    # Define handler
    async def handler(msg):
        received_messages.append(msg)
        await msg.ack()

    # Subscribe
    await nats_backend.subscribe(topic, handler)

    # Publish
    metadata = MessageMetadata(
        message_id="msg-1",
        correlation_id="corr-1",
        timestamp=None,
        source="test",
        content_type="text/plain",
    )
    await nats_backend.publish(
        "Hello NATS", topic, metadata=metadata, pattern=MessagingPattern.PUBSUB
    )

    # Wait for message
    for _ in range(10):
        if received_messages:
            break
        await asyncio.sleep(0.1)

    assert len(received_messages) == 1
    assert received_messages[0].payload == "Hello NATS"
    assert received_messages[0].metadata.message_id == "msg-1"
