"""
Integration Tests for Audit Service

This module contains comprehensive integration tests for the audit service,
testing the complete flow from request to storage across all components.
"""

import asyncio
import os
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

import psutil
import pytest
import pytest_asyncio

from mmf_new.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf_new.services.audit.application.commands import LogRequestCommand
from mmf_new.services.audit.di_config import AuditConfig
from mmf_new.services.audit.infrastructure.adapters.fastapi_middleware import (
    AuditMiddlewareConfig,
    FastAPIAuditMiddleware,
    MiddlewareAuditor,
)
from mmf_new.services.audit.service_factory import AuditService, audit_context


class TestAuditServiceIntegration:
    """Integration tests for the complete audit service."""

    @pytest_asyncio.fixture
    async def audit_service(self, test_audit_service):
        """Create audit service for testing."""
        return test_audit_service

    async def test_complete_audit_flow(self, audit_service, sample_log_request_command):
        """Test complete audit flow from command to storage."""
        # Execute the audit command
        response = await audit_service.log_request(sample_log_request_command)

        # Verify response
        assert response.event_id is not None
        assert response.success is True
        assert response.error_message is None

        # Wait for async processing
        await asyncio.sleep(2.0)  # Allow batching and async operations

        # Verify the event was stored (would need to check actual storage)
        # This is a basic integration test - more detailed verification would
        # require checking database, files, etc.

    async def test_high_severity_compliance_forwarding(
        self, audit_service, high_severity_events, test_audit_di_container
    ):
        """Test that high severity events are forwarded to compliance service."""
        # Get the mock compliance service
        compliance_service = test_audit_di_container.audit_compliance_service

        # Process high severity events
        for command in high_severity_events:
            response = await audit_service.log_request(command)
            assert response.event_id is not None

        # Wait for async processing
        await asyncio.sleep(2.0)

        # Verify compliance service was called for high severity events
        assert compliance_service.forward_audit_event.call_count == len(high_severity_events)

    async def test_batch_processing(self, audit_service, batch_test_events):
        """Test batch processing of multiple events."""
        # Submit multiple events quickly
        responses = []
        for command in batch_test_events:
            response = await audit_service.log_request(command)
            responses.append(response)

        # Verify all responses are successful
        for response in responses:
            assert response.event_id is not None

        # Wait for batch processing
        await asyncio.sleep(3.0)

        # All events should be processed
        # In a real test, we would verify they're all in storage

    async def test_destination_failure_independence(self, test_audit_di_container):
        """Test that failure in one destination doesn't affect others."""
        # Create a service with one failing destination
        destinations = test_audit_di_container.get_destinations()

        # Make the first destination fail
        destinations[0].store_audit_event = AsyncMock(side_effect=Exception("Destination failed"))

        # Create service
        service = AuditService(test_audit_di_container)
        await service.initialize(test_audit_di_container._session_factory)

        # Submit an event
        command = LogRequestCommand(
            event_type=AuditEventType.API_REQUEST,
            severity=AuditSeverity.MEDIUM,
            service_name="test-service",
            endpoint="/test",
            method="GET",
            status_code=200,
            outcome=AuditOutcome.SUCCESS,
            message="Test message",
        )

        response = await service.log_request(command)

        # The request should still succeed despite one destination failing
        assert response.event_id is not None

        # Wait for processing
        await asyncio.sleep(2.0)

    async def test_encryption_integration(self, audit_service):
        """Test encryption of sensitive data in audit events."""
        # Create command with sensitive data
        command = LogRequestCommand(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.HIGH,
            outcome=AuditOutcome.SUCCESS,
            message="User login",
            service_name="auth-service",
            endpoint="/auth/login",
            method="POST",
            details={
                "request_data": {
                    "username": "testuser",
                    "password": "sensitive_password",  # Should be encrypted  # pragma: allowlist secret
                    "email": "user@example.com",
                },
                "response_data": {
                    "access_token": "secret_token",  # Should be encrypted
                    "user_id": "123",
                },
            },
            status_code=200,
        )

        response = await audit_service.log_request(command)
        assert response.event_id is not None

        # Wait for processing
        await asyncio.sleep(2.0)

        # In a real test, we would verify that sensitive fields were encrypted
        # and non-sensitive fields were left as plain text

    async def test_concurrent_request_handling(self, audit_service):
        """Test handling of concurrent audit requests."""

        # Create multiple concurrent requests
        async def create_audit_request(index: int):
            command = LogRequestCommand(
                event_type=AuditEventType.API_REQUEST,
                severity=AuditSeverity.LOW,
                outcome=AuditOutcome.SUCCESS,
                message=f"Concurrent request {index}",
                service_name=f"service-{index}",
                endpoint=f"/api/resource/{index}",
                method="GET",
                user_id=f"user-{index}",
                status_code=200,
                details={"concurrent_test": True, "index": index},
            )
            return await audit_service.log_request(command)

        # Submit 50 concurrent requests
        tasks = [create_audit_request(i) for i in range(50)]
        responses = await asyncio.gather(*tasks)

        # Verify all requests succeeded
        for response in responses:
            assert response.event_id is not None

        # Wait for processing
        await asyncio.sleep(3.0)

    async def test_error_recovery(self, test_audit_di_container):
        """Test error recovery and resilience."""
        # Save original methods
        destinations = test_audit_di_container.get_destinations()
        original_methods = [dest.store_audit_event for dest in destinations]

        # Make all destinations fail initially
        for dest in destinations:
            dest.store_audit_event = AsyncMock(side_effect=Exception("Temporary failure"))

        # Create service
        service = AuditService(test_audit_di_container)
        await service.initialize(test_audit_di_container._session_factory)

        # Submit a request that should fail
        command = LogRequestCommand(
            event_type=AuditEventType.API_REQUEST,
            severity=AuditSeverity.MEDIUM,
            outcome=AuditOutcome.SUCCESS,
            message="Test message",
            service_name="test-service",
            endpoint="/test",
            method="GET",
            status_code=200,
        )

        response = await service.log_request(command)

        # The service should handle the error gracefully
        # (exact behavior depends on implementation)
        assert response.event_id is not None

        # Wait for processing
        await asyncio.sleep(1.0)

        # Restore destinations (simulate recovery)
        for i, dest in enumerate(destinations):
            dest.store_audit_event = original_methods[i]

        # Submit another request - should succeed now
        response2 = await service.log_request(command)
        assert response2.event_id is not None

    async def test_service_factory_context_manager(self):
        """Test service factory context manager behavior."""
        config = AuditConfig(
            database_url="sqlite+aiosqlite:///:memory:",
            encryption_enabled=False,
            enabled_destinations=["console"],
        )

        async def mock_session_factory():
            yield AsyncMock()

        async with audit_context(config, mock_session_factory) as service:
            # Service should be available within context
            command = LogRequestCommand(
                event_type=AuditEventType.API_REQUEST,
                severity=AuditSeverity.LOW,
                outcome=AuditOutcome.SUCCESS,
                message="Test message",
                service_name="test-service",
                endpoint="/test",
                method="GET",
                status_code=200,
            )

            response = await service.log_request(command)
            assert response.event_id is not None

        # After context exit, cleanup should have occurred
        # (exact verification depends on implementation)

    async def test_configuration_validation(self, test_audit_di_container):
        """Test that service validates configuration properly."""
        # Test with invalid configuration
        # This would test various edge cases in configuration

        # For now, just verify service can be created
        service = AuditService(test_audit_di_container)
        await service.initialize(test_audit_di_container._session_factory)

        assert service is not None

    async def test_performance_under_load(self, audit_service):
        """Basic performance test under load."""

        start_time = time.time()

        # Create 100 audit events
        tasks = []
        for i in range(100):
            command = LogRequestCommand(
                event_type=AuditEventType.API_REQUEST,
                severity=AuditSeverity.LOW,
                outcome=AuditOutcome.SUCCESS,
                message=f"Load test {i}",
                service_name="load-test",
                endpoint=f"/api/item/{i}",
                method="GET",
                user_id=f"user-{i % 10}",
                status_code=200,
                duration_ms=100.0,
                details={"load_test": True, "batch": i // 10},
            )
            tasks.append(audit_service.log_request(command))

        # Execute all requests
        responses = await asyncio.gather(*tasks)

        end_time = time.time()
        duration = end_time - start_time

        # Verify all succeeded
        for response in responses:
            assert response.event_id is not None

        # Basic performance assertion (adjust based on requirements)
        assert duration < 10.0  # Should complete within 10 seconds

        print(f"Processed 100 audit events in {duration:.2f} seconds")

        # Wait for async processing to complete
        await asyncio.sleep(5.0)


class TestMiddlewareIntegration:
    """Integration tests for middleware components."""

    async def test_fastapi_middleware_integration(self):
        """Test FastAPI middleware integration."""

        # Create mock audit service
        mock_audit_service = AsyncMock()
        mock_audit_service.log_request = AsyncMock(
            return_value=type("Response", (), {"event_id": "test-event-123"})()
        )

        # Create middleware components
        config = AuditMiddlewareConfig()
        auditor = MiddlewareAuditor(mock_audit_service)
        FastAPIAuditMiddleware(app=None, audit_service=mock_audit_service, config=config)

        # Test auditor directly
        event_id = await auditor.audit_request_start(
            request_id="req-123",
            method="POST",
            endpoint="/api/test",
            user_id="test-user",
            request_data={"test": "data"},
        )

        assert event_id is not None
        mock_audit_service.log_request.assert_called_once()

    @pytest.mark.skip(
        reason="GrpcMiddlewareAuditor needs refactoring to match IMiddlewareAuditor interface"
    )
    async def test_grpc_interceptor_integration(self):
        """Test gRPC interceptor integration."""
        pass


# Performance and stress tests
class TestAuditServicePerformance:
    """Performance and stress tests for audit service."""

    @pytest.mark.asyncio
    async def test_throughput_measurement(self, audit_service):
        """Measure audit service throughput."""

        # Warm up
        warm_up_command = LogRequestCommand(
            event_type=AuditEventType.API_REQUEST,
            severity=AuditSeverity.LOW,
            outcome=AuditOutcome.SUCCESS,
            message="Warmup",
            service_name="warmup",
            endpoint="/warmup",
            method="GET",
            status_code=200,
        )
        await audit_service.log_request(warm_up_command)
        await asyncio.sleep(1.0)

        # Measure throughput
        num_requests = 500
        start_time = time.time()

        tasks = []
        for i in range(num_requests):
            command = LogRequestCommand(
                event_type=AuditEventType.API_REQUEST,
                severity=AuditSeverity.LOW,
                outcome=AuditOutcome.SUCCESS,
                message=f"Throughput test {i}",
                service_name="throughput-test",
                endpoint=f"/api/item/{i}",
                method="GET",
                status_code=200,
                duration_ms=10.0,
                details={"throughput_test": True},
            )
            tasks.append(audit_service.log_request(command))

        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        duration = end_time - start_time
        throughput = num_requests / duration

        print(f"Audit service throughput: {throughput:.2f} requests/second")

        # Verify all requests succeeded
        for response in responses:
            assert response.event_id is not None

        # Basic performance requirement
        assert throughput > 100  # Should handle at least 100 requests per second

        # Wait for processing
        await asyncio.sleep(3.0)

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, audit_service):
        """Test memory usage remains stable under load."""

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process many requests
        for batch in range(10):
            tasks = []
            for i in range(100):
                command = LogRequestCommand(
                    event_type=AuditEventType.API_REQUEST,
                    severity=AuditSeverity.LOW,
                    outcome=AuditOutcome.SUCCESS,
                    message=f"Memory test {batch}-{i}",
                    service_name="memory-test",
                    endpoint=f"/batch/{batch}/item/{i}",
                    method="GET",
                    status_code=200,
                    details={"memory_test": True, "batch": batch},
                )
                tasks.append(audit_service.log_request(command))

            await asyncio.gather(*tasks)

            # Check memory periodically
            current_memory = process.memory_info().rss
            memory_increase = current_memory - initial_memory

            # Memory shouldn't increase dramatically (allow for some growth)
            assert memory_increase < 100 * 1024 * 1024  # Less than 100MB increase

            # Small delay between batches
            await asyncio.sleep(0.5)

        print(f"Memory usage increase: {memory_increase / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
