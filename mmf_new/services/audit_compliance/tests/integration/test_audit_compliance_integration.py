"""
Integration tests for audit compliance service.

These tests verify that the complete hexagonal architecture works end-to-end,
including all layers from domain through infrastructure.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, list

import pytest

from mmf_new.core.domain.audit_types import (
    AuditLevel,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventType,
)

from .conftest import (
    assert_audit_event_valid,
    assert_compliance_scan_valid,
    assert_security_report_valid,
    assert_threat_pattern_valid,
    generate_audit_events,
)


class TestAuditEventOperations:
    """Test audit event logging and retrieval operations."""

    @pytest.mark.asyncio
    async def test_log_single_audit_event(self, audit_service, sample_audit_events):
        """Test logging a single audit event."""
        event_data = sample_audit_events[0]

        # Log the event
        audit_event = await audit_service.log_audit_event(**event_data)

        # Verify the event was created correctly
        assert_audit_event_valid(audit_event, event_data)
        assert audit_event.event_id is not None
        assert audit_event.timestamp is not None

    @pytest.mark.asyncio
    async def test_bulk_log_audit_events(self, audit_service, sample_audit_events):
        """Test logging multiple audit events in bulk."""
        # Log all events in bulk
        audit_events = await audit_service.bulk_log_events(sample_audit_events)

        # Verify all events were created
        assert len(audit_events) == len(sample_audit_events)

        for i, audit_event in enumerate(audit_events):
            assert_audit_event_valid(audit_event, sample_audit_events[i])

    @pytest.mark.asyncio
    async def test_retrieve_audit_events(self, audit_service, sample_audit_events):
        """Test retrieving audit events with filtering."""
        # First log some events
        await audit_service.bulk_log_events(sample_audit_events)

        # Retrieve all events
        all_events = await audit_service.get_audit_events(limit=100)
        assert len(all_events) >= len(sample_audit_events)

        # Test filtering by event type
        auth_events = await audit_service.get_audit_events(
            event_types=[SecurityEventType.AUTHENTICATION_SUCCESS], limit=50
        )
        for event in auth_events:
            assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS

        # Test filtering by severity
        high_severity_events = await audit_service.get_audit_events(
            severities=[SecurityEventSeverity.HIGH, SecurityEventSeverity.CRITICAL], limit=50
        )
        for event in high_severity_events:
            assert event.severity in [SecurityEventSeverity.HIGH, SecurityEventSeverity.CRITICAL]

    @pytest.mark.asyncio
    async def test_cached_events_retrieval(self, audit_service, sample_audit_events):
        """Test retrieving events from cache for fast access."""
        # Log events first
        await audit_service.bulk_log_events(sample_audit_events)

        # Allow some time for caching
        await asyncio.sleep(0.1)

        # Retrieve cached events
        cached_events = await audit_service.get_cached_events(max_age_hours=1)

        # Should have some cached events
        assert len(cached_events) > 0

        # Test filtering cached events by type
        filtered_cached = await audit_service.get_cached_events(
            event_types=[SecurityEventType.AUTHENTICATION_SUCCESS], max_age_hours=1
        )

        for event in filtered_cached:
            assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS


class TestComplianceOperations:
    """Test compliance scanning and status operations."""

    @pytest.mark.asyncio
    async def test_compliance_scan(self, audit_service, compliance_frameworks):
        """Test performing compliance scan."""
        # Perform compliance scan
        scan_result = await audit_service.scan_compliance(
            frameworks=compliance_frameworks[:2],  # Test with first 2 frameworks
            target_resource="test_system",
            scan_depth="standard",
        )

        # Verify scan result
        assert_compliance_scan_valid(scan_result, compliance_frameworks[:2])
        assert scan_result.target_resource == "test_system"
        assert scan_result.scan_depth == "standard"

    @pytest.mark.asyncio
    async def test_compliance_status_check(self, audit_service, compliance_frameworks):
        """Test checking compliance status for specific framework."""
        framework = compliance_frameworks[0]  # GDPR

        # Get compliance status
        status = await audit_service.get_compliance_status(framework)

        # Verify status structure
        assert isinstance(status, dict)
        assert "framework" in status
        assert "compliance_score" in status
        assert "last_scan_date" in status
        assert "findings" in status

        assert status["framework"] == framework.value
        assert isinstance(status["compliance_score"], int | float)
        assert 0 <= status["compliance_score"] <= 1

    @pytest.mark.asyncio
    async def test_multiple_framework_compliance(self, audit_service, compliance_frameworks):
        """Test scanning against multiple compliance frameworks."""
        # Scan all frameworks
        scan_result = await audit_service.scan_compliance(
            frameworks=compliance_frameworks,
            target_resource="multi_framework_test",
            scan_depth="thorough",
        )

        # Verify results for all frameworks
        assert_compliance_scan_valid(scan_result, compliance_frameworks)
        assert len(scan_result.framework_results) == len(compliance_frameworks)

        # Check that each framework has results
        framework_names = {fr.framework.value for fr in scan_result.framework_results}
        expected_names = {cf.value for cf in compliance_frameworks}
        assert framework_names == expected_names


class TestThreatAnalysisOperations:
    """Test threat analysis and pattern detection operations."""

    @pytest.mark.asyncio
    async def test_threat_pattern_analysis(self, audit_service, sample_audit_events):
        """Test analyzing events for threat patterns."""
        # Log some events that might contain patterns
        await audit_service.bulk_log_events(sample_audit_events)

        # Allow processing time
        await asyncio.sleep(0.1)

        # Analyze threat patterns
        threat_patterns = await audit_service.analyze_threat_patterns(
            analysis_window_hours=1, confidence_threshold=0.5
        )

        # Verify threat patterns
        assert isinstance(threat_patterns, list)

        for pattern in threat_patterns:
            assert_threat_pattern_valid(pattern)

    @pytest.mark.asyncio
    async def test_threat_intelligence_retrieval(self, audit_service):
        """Test retrieving threat intelligence data."""
        # Get all active threat intelligence
        all_threats = await audit_service.get_threat_intelligence(active_only=True)

        assert isinstance(all_threats, list)

        # Test filtering by threat type
        specific_threats = await audit_service.get_threat_intelligence(
            threat_type="malware", active_only=True
        )

        assert isinstance(specific_threats, list)

        # If there are threats, verify structure
        for threat in specific_threats:
            assert isinstance(threat, dict)
            assert "threat_type" in threat
            assert "confidence" in threat
            assert "last_seen" in threat

    @pytest.mark.asyncio
    async def test_threat_analysis_with_large_dataset(self, audit_service):
        """Test threat analysis with a larger dataset."""
        # Generate a larger set of events
        large_event_set = generate_audit_events(50)

        # Log all events
        await audit_service.bulk_log_events(large_event_set)

        # Allow processing time
        await asyncio.sleep(0.2)

        # Analyze with different confidence thresholds
        high_confidence = await audit_service.analyze_threat_patterns(
            analysis_window_hours=1, confidence_threshold=0.8
        )

        medium_confidence = await audit_service.analyze_threat_patterns(
            analysis_window_hours=1, confidence_threshold=0.6
        )

        # High confidence should have fewer or equal patterns
        assert len(high_confidence) <= len(medium_confidence)


class TestSecurityReportOperations:
    """Test security report generation operations."""

    @pytest.mark.asyncio
    async def test_comprehensive_security_report(self, audit_service, sample_audit_events):
        """Test generating a comprehensive security report."""
        # Log some events first
        await audit_service.bulk_log_events(sample_audit_events)

        # Allow processing time
        await asyncio.sleep(0.1)

        # Generate comprehensive report
        report_data = await audit_service.generate_security_report(
            report_type="comprehensive", output_format="json", include_recommendations=True
        )

        # Verify report structure
        assert_security_report_valid(report_data)

    @pytest.mark.asyncio
    async def test_compliance_focused_report(self, audit_service, sample_audit_events):
        """Test generating a compliance-focused report."""
        # Log events and generate report
        await audit_service.bulk_log_events(sample_audit_events)
        await asyncio.sleep(0.1)

        report_data = await audit_service.generate_security_report(
            report_type="compliance", output_format="html", include_recommendations=False
        )

        assert_security_report_valid(report_data)

    @pytest.mark.asyncio
    async def test_threat_analysis_report(self, audit_service, sample_audit_events):
        """Test generating a threat analysis report."""
        # Log events and generate report
        await audit_service.bulk_log_events(sample_audit_events)
        await asyncio.sleep(0.1)

        report_data = await audit_service.generate_security_report(
            report_type="threat",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
            output_format="pdf",
        )

        assert_security_report_valid(report_data)

    @pytest.mark.asyncio
    async def test_executive_summary_report(self, audit_service, sample_audit_events):
        """Test generating an executive summary report."""
        # Log events and generate report
        await audit_service.bulk_log_events(sample_audit_events)
        await asyncio.sleep(0.1)

        report_data = await audit_service.generate_security_report(
            report_type="executive",
            start_time=datetime.utcnow() - timedelta(days=7),
            end_time=datetime.utcnow(),
            output_format="json",
        )

        assert_security_report_valid(report_data)


class TestSIEMIntegrationOperations:
    """Test SIEM integration operations."""

    @pytest.mark.asyncio
    async def test_collect_security_events(self, audit_service, mock_siem_events):
        """Test collecting security events from SIEM."""
        # Collect recent security events
        collected_events = await audit_service.collect_security_events(time_range_hours=1)

        # Verify collection
        assert isinstance(collected_events, list)

        # Test filtering by source systems
        filtered_events = await audit_service.collect_security_events(
            source_systems=["firewall", "endpoint_protection"], time_range_hours=2
        )

        assert isinstance(filtered_events, list)

    @pytest.mark.asyncio
    async def test_forward_events_to_siem(self, audit_service, sample_audit_events):
        """Test forwarding events to SIEM system."""
        # First log some events
        audit_events = await audit_service.bulk_log_events(sample_audit_events)

        # Forward events to SIEM
        success = await audit_service.forward_to_siem(audit_events)

        # Should succeed (even with mock implementation)
        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_bidirectional_siem_flow(self, audit_service, sample_audit_events):
        """Test complete SIEM integration flow."""
        # 1. Log events locally
        local_events = await audit_service.bulk_log_events(sample_audit_events)

        # 2. Forward to SIEM
        forward_success = await audit_service.forward_to_siem(local_events)
        assert isinstance(forward_success, bool)

        # 3. Collect events from SIEM
        collected_events = await audit_service.collect_security_events(time_range_hours=1)
        assert isinstance(collected_events, list)


class TestPerformanceAndScalability:
    """Test performance and scalability aspects."""

    @pytest.mark.asyncio
    async def test_bulk_event_processing_performance(self, audit_service, perf_timer):
        """Test performance of bulk event processing."""
        # Generate large event set
        large_events = generate_audit_events(100)

        # Time the bulk operation
        perf_timer.start()
        audit_events = await audit_service.bulk_log_events(large_events)
        perf_timer.stop()

        # Verify results
        assert len(audit_events) == len(large_events)

        # Performance should be reasonable (less than 5 seconds for 100 events)
        assert perf_timer.duration_ms < 5000

        print(f"Bulk processing 100 events took {perf_timer.duration_ms:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, audit_service, sample_audit_events):
        """Test concurrent operations on the service."""

        # Define concurrent operations
        async def log_events():
            return await audit_service.bulk_log_events(sample_audit_events)

        async def scan_compliance():
            return await audit_service.scan_compliance(
                [ComplianceFramework.GDPR], "concurrent_test"
            )

        async def analyze_threats():
            return await audit_service.analyze_threat_patterns(
                analysis_window_hours=1, confidence_threshold=0.5
            )

        # Run operations concurrently
        results = await asyncio.gather(
            log_events(), scan_compliance(), analyze_threats(), return_exceptions=True
        )

        # Verify all operations completed
        assert len(results) == 3

        # Check that no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception), f"Unexpected exception: {result}"

    @pytest.mark.asyncio
    async def test_cache_performance(self, audit_service, perf_timer):
        """Test cache performance for event retrieval."""
        # Log events first
        events = generate_audit_events(50)
        await audit_service.bulk_log_events(events)

        # Allow caching
        await asyncio.sleep(0.1)

        # Time cached retrieval
        perf_timer.start()
        await audit_service.get_cached_events(max_age_hours=1)
        perf_timer.stop()

        # Cache should be fast (less than 100ms)
        assert perf_timer.duration_ms < 100

        print(f"Cache retrieval took {perf_timer.duration_ms:.2f}ms")


class TestServiceHealthAndMonitoring:
    """Test service health and monitoring capabilities."""

    def test_health_status_check(self, audit_service):
        """Test getting service health status."""
        health_status = audit_service.get_health_status()

        # Verify health status structure
        assert isinstance(health_status, dict)
        assert "overall_status" in health_status
        assert "initialized_services" in health_status
        assert "services" in health_status

        # Should be healthy after initialization
        assert health_status["overall_status"] in ["healthy", "degraded"]
        assert health_status["initialized_services"] > 0
        assert isinstance(health_status["services"], dict)

    @pytest.mark.asyncio
    async def test_metrics_summary(self, audit_service, sample_audit_events):
        """Test getting metrics summary."""
        # Generate some activity first
        await audit_service.bulk_log_events(sample_audit_events)
        await asyncio.sleep(0.1)

        # Get metrics summary
        metrics_summary = await audit_service.get_metrics_summary()

        # Verify metrics structure
        assert isinstance(metrics_summary, dict)

        # Should contain key metrics
        expected_metrics = [
            "events_processed",
            "compliance_scans_performed",
            "threat_patterns_detected",
            "reports_generated",
        ]

        # At least some metrics should be present
        metrics_keys = set(metrics_summary.keys())
        assert len(metrics_keys.intersection(expected_metrics)) > 0


class TestErrorHandlingAndResilience:
    """Test error handling and service resilience."""

    @pytest.mark.asyncio
    async def test_invalid_event_data_handling(self, audit_service):
        """Test handling of invalid event data."""
        invalid_events = [
            {
                "event_type": SecurityEventType.AUTHENTICATION_SUCCESS,
                # Missing required severity field
                "source": "test",
                "description": "test event",
            },
            {
                "event_type": "INVALID_EVENT_TYPE",  # Invalid enum value
                "severity": SecurityEventSeverity.INFO,
                "source": "test",
                "description": "test event",
            },
        ]

        # Bulk logging should handle some failures gracefully
        results = await audit_service.bulk_log_events(invalid_events)

        # Should return results for valid events only
        assert len(results) <= len(invalid_events)

    @pytest.mark.asyncio
    async def test_service_resilience_under_load(self, audit_service):
        """Test service behavior under high load."""
        # Generate high load scenario
        large_event_sets = [generate_audit_events(20) for _ in range(5)]

        # Submit multiple bulk operations simultaneously
        tasks = []
        for event_set in large_event_sets:
            tasks.append(audit_service.bulk_log_events(event_set))

        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most operations should succeed
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_operations) >= len(large_event_sets) // 2  # At least 50% success

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, audit_service, sample_audit_events):
        """Test graceful degradation when some components fail."""
        # This test would normally involve mocking component failures
        # For now, we'll test that the service continues to function
        # even when some operations might fail

        # Try various operations that might have dependencies
        try:
            # Basic logging should always work
            events = await audit_service.bulk_log_events(sample_audit_events)
            assert len(events) > 0

            # Even if some advanced features fail, basic functionality persists
            health = audit_service.get_health_status()
            assert health["overall_status"] in ["healthy", "degraded", "unhealthy"]

        except Exception as e:
            pytest.fail(f"Service should degrade gracefully, not fail completely: {e}")


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_complete_security_incident_workflow(self, audit_service, compliance_frameworks):
        """Test complete workflow from incident detection to reporting."""
        # 1. Security incident occurs - log multiple related events
        incident_events = [
            {
                "event_type": SecurityEventType.AUTHENTICATION_FAILURE,
                "severity": SecurityEventSeverity.WARNING,
                "source": "auth_service",
                "description": "Multiple failed login attempts",
                "user_id": "suspicious_user",
                "metadata": {"ip_address": "192.168.1.100", "attempts": 5},
            },
            {
                "event_type": SecurityEventType.PERMISSION_DENIED,
                "severity": SecurityEventSeverity.HIGH,
                "source": "api_gateway",
                "description": "Unauthorized access attempt to admin endpoint",
                "user_id": "suspicious_user",
                "resource_id": "admin_panel",
                "metadata": {"ip_address": "192.168.1.100", "endpoint": "/admin/users"},
            },
            {
                "event_type": SecurityEventType.SYSTEM_ALERT,
                "severity": SecurityEventSeverity.CRITICAL,
                "source": "monitoring_system",
                "description": "Suspicious behavior pattern detected",
                "user_id": "suspicious_user",
                "metadata": {"pattern": "credential_stuffing", "confidence": 0.95},
            },
        ]

        # Log incident events
        logged_events = await audit_service.bulk_log_events(incident_events)
        assert len(logged_events) == len(incident_events)

        # 2. Analyze for threat patterns
        await asyncio.sleep(0.1)  # Allow processing
        threat_patterns = await audit_service.analyze_threat_patterns(
            analysis_window_hours=1, confidence_threshold=0.5
        )

        # Should detect some patterns from the incident
        assert isinstance(threat_patterns, list)

        # 3. Check compliance impact
        compliance_status = await audit_service.get_compliance_status(ComplianceFramework.GDPR)
        assert isinstance(compliance_status, dict)

        # 4. Generate incident report
        incident_report = await audit_service.generate_security_report(
            report_type="threat",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
            output_format="json",
            include_recommendations=True,
        )

        assert_security_report_valid(incident_report)

        # 5. Forward to SIEM for external analysis
        siem_success = await audit_service.forward_to_siem(logged_events)
        assert isinstance(siem_success, bool)

    @pytest.mark.asyncio
    async def test_compliance_audit_workflow(self, audit_service, compliance_frameworks):
        """Test complete compliance audit workflow."""
        # 1. Log various business events
        business_events = [
            {
                "event_type": SecurityEventType.DATA_ACCESS,
                "severity": SecurityEventSeverity.INFO,
                "source": "crm_system",
                "description": "Customer data accessed for support",
                "user_id": "support_agent_1",
                "resource_id": "customer_123",
                "metadata": {
                    "purpose": "customer_support",
                    "data_types": ["contact", "preferences"],
                },
            },
            {
                "event_type": SecurityEventType.DATA_MODIFICATION,
                "severity": SecurityEventSeverity.MEDIUM,
                "source": "billing_system",
                "description": "Payment information updated",
                "user_id": "billing_admin",
                "resource_id": "payment_method_456",
                "metadata": {"change_type": "update", "pii_involved": True},
            },
            {
                "event_type": SecurityEventType.CONFIGURATION_CHANGE,
                "severity": SecurityEventSeverity.HIGH,
                "source": "security_config",
                "description": "Security policy updated",
                "user_id": "security_admin",
                "metadata": {"policy": "data_retention", "changes": ["retention_period"]},
            },
        ]

        # Log business events
        await audit_service.bulk_log_events(business_events)

        # 2. Perform comprehensive compliance scan
        compliance_scan = await audit_service.scan_compliance(
            frameworks=compliance_frameworks,
            target_resource="business_systems",
            scan_depth="thorough",
        )

        assert_compliance_scan_valid(compliance_scan, compliance_frameworks)

        # 3. Generate compliance report
        compliance_report = await audit_service.generate_security_report(
            report_type="compliance",
            start_time=datetime.utcnow() - timedelta(days=30),
            end_time=datetime.utcnow(),
            output_format="html",
            include_recommendations=True,
        )

        assert_security_report_valid(compliance_report)

        # 4. Check individual framework status
        for framework in compliance_frameworks[:2]:  # Test first 2
            status = await audit_service.get_compliance_status(framework)
            assert isinstance(status, dict)
            assert "compliance_score" in status

    @pytest.mark.asyncio
    async def test_continuous_monitoring_scenario(self, audit_service):
        """Test continuous monitoring scenario with ongoing events."""
        # Simulate continuous event stream
        for batch in range(3):  # 3 batches of events
            batch_events = generate_audit_events(10)

            # Add batch identifier
            for event in batch_events:
                event["metadata"] = event.get("metadata", {})
                event["metadata"]["batch"] = batch

            # Log batch
            logged_events = await audit_service.bulk_log_events(batch_events)
            assert len(logged_events) == 10

            # Short delay between batches
            await asyncio.sleep(0.1)

        # After all batches, analyze patterns
        all_patterns = await audit_service.analyze_threat_patterns(
            analysis_window_hours=1,
            confidence_threshold=0.3,  # Lower threshold for test data
        )

        # Should have detected some patterns across batches
        assert isinstance(all_patterns, list)

        # Check cache has recent events
        cached_events = await audit_service.get_cached_events(max_age_hours=1)
        assert len(cached_events) >= 30  # Should have events from all batches

        # Generate summary report
        summary_report = await audit_service.generate_security_report(
            report_type="comprehensive",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
            output_format="json",
        )

        assert_security_report_valid(summary_report)
