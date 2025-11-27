"""
End-to-End Test for Auditability and Error Tracking

This test demonstrates:
1. Error logging and event tracking across multiple services
2. Audit trail functionality for compliance and debugging
3. Structured logging for observability
4. Event correlation and traceability
"""

import asyncio
import builtins
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from tests.e2e.conftest import AuditEvent, PerformanceAnalyzer


class AuditTrailCollector:
    """Collects and analyzes audit trail data for compliance and debugging."""

    def __init__(self):
        self.audit_events: builtins.list[AuditEvent] = []
        self.error_events: builtins.list[builtins.dict] = []
        self.business_events: builtins.list[builtins.dict] = []
        self.security_events: builtins.list[builtins.dict] = []
        self.performance_events: builtins.list[builtins.dict] = []
        self.correlation_map: builtins.dict[str, builtins.list[str]] = {}  # request_id -> event_ids

        # Setup structured logging
        self.logger = self._setup_structured_logger()

    def _setup_structured_logger(self) -> logging.Logger:
        """Setup structured logger for audit trails."""
        logger = logging.getLogger("audit_trail_test")
        logger.setLevel(logging.DEBUG)

        # Create formatter for structured logging
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s | "
            "correlation_id=%(correlation_id)s | user_id=%(user_id)s"
        )

        # Create handler
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def record_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        service: str,
        correlation_id: str = None,
        user_id: str = None,
        metadata: builtins.dict = None,
    ) -> str:
        """Record an audit event with full traceability."""

        event_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())

        event = AuditEvent(
            timestamp=datetime.now(),
            service=service,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
            user_id=user_id,
            request_id=correlation_id,
        )

        self.audit_events.append(event)

        # Categorize events
        if event_type == "error":
            self.error_events.append(self._event_to_dict(event, event_id))
        elif event_type == "business":
            self.business_events.append(self._event_to_dict(event, event_id))
        elif event_type == "security":
            self.security_events.append(self._event_to_dict(event, event_id))
        elif event_type == "performance":
            self.performance_events.append(self._event_to_dict(event, event_id))

        # Track correlation
        if correlation_id not in self.correlation_map:
            self.correlation_map[correlation_id] = []
        self.correlation_map[correlation_id].append(event_id)

        # Log structured event
        self.logger.info(
            message,
            extra={
                "correlation_id": correlation_id,
                "user_id": user_id or "system",
                "event_type": event_type,
                "service": service,
                "severity": severity,
                "metadata": json.dumps(metadata or {}),
            },
        )

        return event_id

    def _event_to_dict(self, event: AuditEvent, event_id: str) -> builtins.dict:
        """Convert audit event to dictionary."""
        return {
            "id": event_id,
            "timestamp": event.timestamp.isoformat(),
            "service": event.service,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
            "metadata": event.metadata,
            "user_id": event.user_id,
            "request_id": event.request_id,
        }

    def get_events_by_correlation(self, correlation_id: str) -> builtins.list[builtins.dict]:
        """Get all events for a specific correlation ID."""
        if correlation_id not in self.correlation_map:
            return []

        event_ids = self.correlation_map[correlation_id]
        all_events = (
            self.error_events
            + self.business_events
            + self.security_events
            + self.performance_events
        )

        return [event for event in all_events if event["id"] in event_ids]

    def analyze_error_patterns(self) -> builtins.dict:
        """Analyze error patterns for insights."""
        if not self.error_events:
            return {"patterns": [], "insights": []}

        # Group errors by service
        service_errors = {}
        for event in self.error_events:
            service = event["service"]
            if service not in service_errors:
                service_errors[service] = []
            service_errors[service].append(event)

        # Analyze patterns
        patterns = []
        for service, errors in service_errors.items():
            if len(errors) > 1:
                # Check for error bursts
                timestamps = [datetime.fromisoformat(e["timestamp"]) for e in errors]
                timestamps.sort()

                # Find error clusters (errors within 30 seconds)
                clusters = []
                current_cluster = [timestamps[0]]

                for ts in timestamps[1:]:
                    if ts - current_cluster[-1] <= timedelta(seconds=30):
                        current_cluster.append(ts)
                    else:
                        if len(current_cluster) > 1:
                            clusters.append(current_cluster)
                        current_cluster = [ts]

                if len(current_cluster) > 1:
                    clusters.append(current_cluster)

                patterns.append(
                    {
                        "service": service,
                        "total_errors": len(errors),
                        "error_clusters": len(clusters),
                        "largest_cluster": max(len(cluster) for cluster in clusters)
                        if clusters
                        else 0,
                    }
                )

        # Generate insights
        insights = []
        total_errors = len(self.error_events)
        if total_errors > 10:
            insights.append(f"High error volume detected: {total_errors} errors")

        for pattern in patterns:
            if pattern["error_clusters"] > 0:
                insights.append(
                    f"Service {pattern['service']} shows error clustering pattern "
                    f"({pattern['error_clusters']} clusters, max {pattern['largest_cluster']} errors)"
                )

        return {"patterns": patterns, "insights": insights}

    def generate_compliance_report(self) -> builtins.dict:
        """Generate compliance audit report."""
        now = datetime.now()

        return {
            "report_metadata": {
                "generated_at": now.isoformat(),
                "report_type": "compliance_audit",
                "period_start": min(e.timestamp for e in self.audit_events).isoformat()
                if self.audit_events
                else now.isoformat(),
                "period_end": max(e.timestamp for e in self.audit_events).isoformat()
                if self.audit_events
                else now.isoformat(),
            },
            "event_summary": {
                "total_events": len(self.audit_events),
                "error_events": len(self.error_events),
                "business_events": len(self.business_events),
                "security_events": len(self.security_events),
                "performance_events": len(self.performance_events),
            },
            "traceability_metrics": {
                "total_correlation_chains": len(self.correlation_map),
                "avg_events_per_chain": sum(len(events) for events in self.correlation_map.values())
                / len(self.correlation_map)
                if self.correlation_map
                else 0,
                "max_chain_length": max(len(events) for events in self.correlation_map.values())
                if self.correlation_map
                else 0,
            },
            "compliance_checks": self._run_compliance_checks(),
            "error_analysis": self.analyze_error_patterns(),
        }

    def _run_compliance_checks(self) -> builtins.list[builtins.dict]:
        """Run compliance checks on audit data."""
        checks = []

        # Check 1: All events have timestamps
        events_without_timestamps = [e for e in self.audit_events if not e.timestamp]
        checks.append(
            {
                "check": "timestamp_completeness",
                "passed": len(events_without_timestamps) == 0,
                "details": f"Found {len(events_without_timestamps)} events without timestamps",
            }
        )

        # Check 2: Critical events have correlation IDs
        critical_events = [
            e for e in self.audit_events if e.severity in ["error", "critical"] and not e.request_id
        ]
        checks.append(
            {
                "check": "critical_event_correlation",
                "passed": len(critical_events) == 0,
                "details": f"Found {len(critical_events)} critical events without correlation IDs",
            }
        )

        # Check 3: Security events have user context
        security_events_no_user = [
            e for e in self.audit_events if e.event_type == "security" and not e.user_id
        ]
        checks.append(
            {
                "check": "security_event_user_context",
                "passed": len(security_events_no_user) == 0,
                "details": f"Found {len(security_events_no_user)} security events without user context",
            }
        )

        return checks


class TestAuditability:
    """Test suite for auditability and error tracking."""

    @pytest.mark.asyncio
    async def test_comprehensive_auditability(
        self,
        simulation_plugin,
        pipeline_plugin,
        monitoring_plugin,
        performance_analyzer: PerformanceAnalyzer,
        test_report_dir: Path,
    ):
        """
        Comprehensive test for error logging, event tracking, and audit trails.
        """
        print("\\n📋 Starting comprehensive auditability test...")

        # Initialize audit trail collector
        audit_collector = AuditTrailCollector()

        # Test scenarios that generate different types of audit events
        test_scenarios = [
            {
                "name": "normal_operations",
                "duration": 15,
                "error_injection": False,
                "user_context": "test_user_001",
            },
            {
                "name": "error_scenarios",
                "duration": 20,
                "error_injection": True,
                "user_context": "test_user_002",
            },
            {
                "name": "security_events",
                "duration": 10,
                "error_injection": False,
                "user_context": "admin_user",
                "security_simulation": True,
            },
            {
                "name": "high_load_audit",
                "duration": 25,
                "error_injection": True,
                "user_context": "load_test_user",
                "high_load": True,
            },
        ]

        results = {}

        for scenario in test_scenarios:
            print(f"\\n🎭 Running scenario: {scenario['name']}")

            scenario_results = await self._execute_audit_scenario(
                scenario,
                simulation_plugin,
                pipeline_plugin,
                monitoring_plugin,
                audit_collector,
                performance_analyzer,
            )

            results[scenario["name"]] = scenario_results

            print(f"✅ Completed scenario: {scenario['name']}")
            print(f"   Events generated: {scenario_results['events_generated']}")
            print(f"   Error events: {scenario_results['error_events']}")

            # Brief pause between scenarios
            await asyncio.sleep(2)

        # Analyze audit trail completeness
        audit_analysis = await self._analyze_audit_completeness(audit_collector, results)

        # Generate compliance report
        compliance_report = audit_collector.generate_compliance_report()

        # Generate comprehensive audit report
        report = self._generate_audit_report(
            results, audit_analysis, compliance_report, audit_collector
        )

        # Save report
        report_file = test_report_dir / "auditability_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\\n📋 Audit report saved to: {report_file}")

        # Assertions
        assert len(results) == len(test_scenarios), "Should have results for all scenarios"
        assert len(audit_collector.audit_events) > 0, "Should generate audit events"
        assert len(audit_collector.error_events) > 0, "Should capture error events"
        assert len(audit_collector.correlation_map) > 0, "Should have correlation tracking"

        # Compliance assertions
        compliance_checks = compliance_report["compliance_checks"]
        critical_failures = [
            c for c in compliance_checks if not c["passed"] and "critical" in c["check"]
        ]
        assert len(critical_failures) == 0, (
            f"Critical compliance checks failed: {critical_failures}"
        )

        # Print summary
        self._print_audit_summary(report)

    async def _execute_audit_scenario(
        self,
        scenario,
        simulation_plugin,
        pipeline_plugin,
        monitoring_plugin,
        audit_collector: AuditTrailCollector,
        performance_analyzer: PerformanceAnalyzer,
    ):
        """Execute a single audit scenario."""

        start_time = datetime.now()
        duration = scenario["duration"]

        scenario_results = {
            "events_generated": 0,
            "error_events": 0,
            "business_events": 0,
            "security_events": 0,
            "performance_events": 0,
            "correlation_chains": 0,
        }

        # Configure plugins for scenario
        if scenario.get("error_injection", False):
            simulation_plugin.config.update(
                {
                    "error_rate": 0.3,  # 30% error rate
                    "complexity_multiplier": 3,
                }
            )
        else:
            simulation_plugin.config.update(
                {
                    "error_rate": 0.05,  # 5% error rate
                    "complexity_multiplier": 1,
                }
            )

        # Start background monitoring with audit logging
        monitoring_task = asyncio.create_task(
            self._monitor_with_audit_logging(
                monitoring_plugin, audit_collector, scenario["name"], duration
            )
        )

        # Generate workload with audit tracking
        workload_tasks = []

        # Simulation workload
        for i in range(3):
            task = asyncio.create_task(
                self._run_audited_simulation_workload(
                    simulation_plugin,
                    audit_collector,
                    f"sim_worker_{i}",
                    scenario,
                    duration,
                )
            )
            workload_tasks.append(task)

        # Pipeline workload
        for i in range(2):
            task = asyncio.create_task(
                self._run_audited_pipeline_workload(
                    pipeline_plugin,
                    audit_collector,
                    f"pipeline_worker_{i}",
                    scenario,
                    duration,
                )
            )
            workload_tasks.append(task)

        # Security events (if enabled)
        if scenario.get("security_simulation", False):
            security_task = asyncio.create_task(
                self._simulate_security_events(audit_collector, scenario, duration)
            )
            workload_tasks.append(security_task)

        # Wait for all tasks
        await asyncio.gather(monitoring_task, *workload_tasks, return_exceptions=True)

        # Count events generated during this scenario
        end_time = datetime.now()
        scenario_events = [
            e for e in audit_collector.audit_events if start_time <= e.timestamp <= end_time
        ]

        scenario_results.update(
            {
                "events_generated": len(scenario_events),
                "error_events": len([e for e in scenario_events if e.event_type == "error"]),
                "business_events": len([e for e in scenario_events if e.event_type == "business"]),
                "security_events": len([e for e in scenario_events if e.event_type == "security"]),
                "performance_events": len(
                    [e for e in scenario_events if e.event_type == "performance"]
                ),
            }
        )

        return scenario_results

    async def _monitor_with_audit_logging(
        self, monitoring_plugin, audit_collector, scenario_name, duration
    ):
        """Monitor system with comprehensive audit logging."""
        start_time = datetime.now()

        while (datetime.now() - start_time).seconds < duration:
            try:
                # Simulate monitoring checks with audit trails
                correlation_id = str(uuid.uuid4())

                # Log monitoring start
                audit_collector.record_event(
                    event_type="performance",
                    severity="info",
                    message="Performance monitoring check started",
                    service="monitoring_service",
                    correlation_id=correlation_id,
                    user_id="system",
                    metadata={"scenario": scenario_name, "check_type": "routine"},
                )

                # Simulate monitoring data collection
                await asyncio.sleep(0.5)

                # Randomly generate performance alerts

                if random.random() < 0.2:  # 20% chance of alert
                    alert_severity = random.choice(["warning", "error"])
                    audit_collector.record_event(
                        event_type="performance",
                        severity=alert_severity,
                        message=f"Performance alert triggered: {alert_severity}",
                        service="monitoring_service",
                        correlation_id=correlation_id,
                        user_id="system",
                        metadata={
                            "scenario": scenario_name,
                            "alert_type": f"{alert_severity}_threshold",
                            "metric": random.choice(["cpu", "memory", "response_time"]),
                        },
                    )

                await asyncio.sleep(2)

            except Exception as e:
                audit_collector.record_event(
                    event_type="error",
                    severity="error",
                    message=f"Monitoring error: {e!s}",
                    service="monitoring_service",
                    user_id="system",
                    metadata={
                        "scenario": scenario_name,
                        "error_type": "monitoring_failure",
                    },
                )

    async def _run_audited_simulation_workload(
        self, simulation_plugin, audit_collector, worker_name, scenario, duration
    ):
        """Run simulation workload with comprehensive audit logging."""
        start_time = datetime.now()
        operation_count = 0

        while (datetime.now() - start_time).seconds < duration:
            operation_count += 1
            correlation_id = str(uuid.uuid4())

            try:
                # Log operation start
                audit_collector.record_event(
                    event_type="business",
                    severity="info",
                    message=f"Simulation operation started: {worker_name}_op_{operation_count}",
                    service="simulation_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "worker": worker_name,
                        "operation_id": operation_count,
                        "scenario": scenario["name"],
                    },
                )

                # Execute simulation
                await simulation_plugin.simulate_work(
                    task_name=f"{worker_name}_op_{operation_count}",
                    complexity=getattr(simulation_plugin.config, "complexity_multiplier", 1),
                )

                # Log successful completion
                audit_collector.record_event(
                    event_type="business",
                    severity="info",
                    message="Simulation operation completed successfully",
                    service="simulation_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "worker": worker_name,
                        "operation_id": operation_count,
                        "result": "success",
                        "scenario": scenario["name"],
                    },
                )

            except Exception as e:
                # Log error with full context
                audit_collector.record_event(
                    event_type="error",
                    severity="error",
                    message=f"Simulation operation failed: {e!s}",
                    service="simulation_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "worker": worker_name,
                        "operation_id": operation_count,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "scenario": scenario["name"],
                    },
                )

            await asyncio.sleep(0.3)

    async def _run_audited_pipeline_workload(
        self, pipeline_plugin, audit_collector, worker_name, scenario, duration
    ):
        """Run pipeline workload with audit logging."""
        start_time = datetime.now()
        job_count = 0

        while (datetime.now() - start_time).seconds < duration:
            job_count += 1
            correlation_id = str(uuid.uuid4())

            try:
                job_data = {
                    "id": f"{worker_name}_job_{job_count}",
                    "data": f"audit_test_data_{job_count}",
                    "user_id": scenario["user_context"],
                }

                # Log job submission
                audit_collector.record_event(
                    event_type="business",
                    severity="info",
                    message=f"Pipeline job submitted: {job_data['id']}",
                    service="pipeline_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "job_id": job_data["id"],
                        "worker": worker_name,
                        "scenario": scenario["name"],
                    },
                )

                await pipeline_plugin.submit_job(job_data)

                # Log job completion
                audit_collector.record_event(
                    event_type="business",
                    severity="info",
                    message=f"Pipeline job completed: {job_data['id']}",
                    service="pipeline_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "job_id": job_data["id"],
                        "result": "completed",
                        "scenario": scenario["name"],
                    },
                )

            except Exception as e:
                audit_collector.record_event(
                    event_type="error",
                    severity="error",
                    message=f"Pipeline job failed: {e!s}",
                    service="pipeline_service",
                    correlation_id=correlation_id,
                    user_id=scenario["user_context"],
                    metadata={
                        "job_id": f"{worker_name}_job_{job_count}",
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "scenario": scenario["name"],
                    },
                )

            await asyncio.sleep(0.5)

    async def _simulate_security_events(self, audit_collector, scenario, duration):
        """Simulate security-related events for audit testing."""
        start_time = datetime.now()

        security_events = [
            "user_login_success",
            "user_login_failure",
            "privilege_escalation_attempt",
            "unauthorized_access_attempt",
            "data_access_granted",
            "configuration_change",
        ]

        while (datetime.now() - start_time).seconds < duration:
            event_type = random.choice(security_events)
            correlation_id = str(uuid.uuid4())

            if "failure" in event_type or "attempt" in event_type:
                severity = "warning" if "attempt" in event_type else "error"
            else:
                severity = "info"

            audit_collector.record_event(
                event_type="security",
                severity=severity,
                message=f"Security event: {event_type}",
                service="security_service",
                correlation_id=correlation_id,
                user_id=scenario["user_context"],
                metadata={
                    "event_subtype": event_type,
                    "source_ip": "192.168.1.100",
                    "user_agent": "TestAgent/1.0",
                    "scenario": scenario["name"],
                },
            )

            await asyncio.sleep(random.uniform(1, 3))

    async def _analyze_audit_completeness(
        self, audit_collector: AuditTrailCollector, results: builtins.dict
    ):
        """Analyze completeness and quality of audit trails."""
        analysis = {
            "completeness_score": 0.0,
            "traceability_score": 0.0,
            "coverage_analysis": {},
            "gaps_identified": [],
            "recommendations": [],
        }

        total_events = len(audit_collector.audit_events)

        # Completeness analysis
        events_with_correlation = len([e for e in audit_collector.audit_events if e.request_id])
        events_with_user = len([e for e in audit_collector.audit_events if e.user_id])
        events_with_metadata = len([e for e in audit_collector.audit_events if e.metadata])

        completeness_score = (
            (
                (events_with_correlation / total_events * 0.4)
                + (events_with_user / total_events * 0.3)
                + (events_with_metadata / total_events * 0.3)
            )
            if total_events > 0
            else 0
        )

        analysis["completeness_score"] = completeness_score

        # Traceability analysis
        correlation_chains = len(audit_collector.correlation_map)
        avg_chain_length = (
            sum(len(events) for events in audit_collector.correlation_map.values())
            / correlation_chains
            if correlation_chains > 0
            else 0
        )

        traceability_score = min(
            1.0, (correlation_chains / 10) * 0.7 + (avg_chain_length / 5) * 0.3
        )
        analysis["traceability_score"] = traceability_score

        # Coverage analysis
        services_covered = {e.service for e in audit_collector.audit_events}
        event_types_covered = {e.event_type for e in audit_collector.audit_events}

        analysis["coverage_analysis"] = {
            "services_covered": list(services_covered),
            "event_types_covered": list(event_types_covered),
            "service_count": len(services_covered),
            "event_type_count": len(event_types_covered),
        }

        # Identify gaps
        if completeness_score < 0.8:
            analysis["gaps_identified"].append("Low audit trail completeness")
        if traceability_score < 0.7:
            analysis["gaps_identified"].append("Poor event correlation and traceability")
        if len(services_covered) < 3:
            analysis["gaps_identified"].append("Insufficient service coverage in audit trails")

        return analysis

    def _generate_audit_report(self, results, audit_analysis, compliance_report, audit_collector):
        """Generate comprehensive audit report."""
        return {
            "test_summary": {
                "test_name": "Comprehensive Auditability Test",
                "scenarios_tested": list(results.keys()),
                "total_events_generated": len(audit_collector.audit_events),
                "total_correlation_chains": len(audit_collector.correlation_map),
            },
            "audit_quality_metrics": {
                "completeness_score": audit_analysis["completeness_score"],
                "traceability_score": audit_analysis["traceability_score"],
                "coverage_analysis": audit_analysis["coverage_analysis"],
            },
            "compliance_report": compliance_report,
            "scenario_results": results,
            "error_analysis": audit_collector.analyze_error_patterns(),
            "gaps_and_recommendations": {
                "gaps_identified": audit_analysis["gaps_identified"],
                "recommendations": self._generate_audit_recommendations(
                    audit_analysis, compliance_report
                ),
            },
            "sample_correlation_chains": self._get_sample_correlation_chains(audit_collector),
        }

    def _generate_audit_recommendations(self, audit_analysis, compliance_report):
        """Generate recommendations for improving auditability."""
        recommendations = []

        if audit_analysis["completeness_score"] < 0.8:
            recommendations.append(
                {
                    "category": "Audit Completeness",
                    "priority": "high",
                    "actions": [
                        "Ensure all critical operations generate audit events",
                        "Add correlation IDs to all service calls",
                        "Include user context in all user-initiated operations",
                        "Standardize metadata structure across services",
                    ],
                }
            )

        if audit_analysis["traceability_score"] < 0.7:
            recommendations.append(
                {
                    "category": "Event Traceability",
                    "priority": "medium",
                    "actions": [
                        "Implement distributed tracing with correlation IDs",
                        "Add parent-child relationships for related events",
                        "Create event correlation dashboards",
                        "Implement cross-service event linking",
                    ],
                }
            )

        failed_compliance = [c for c in compliance_report["compliance_checks"] if not c["passed"]]
        if failed_compliance:
            recommendations.append(
                {
                    "category": "Compliance Remediation",
                    "priority": "critical",
                    "actions": [
                        f"Fix compliance issue: {check['check']}" for check in failed_compliance
                    ]
                    + [
                        "Implement automated compliance checking",
                        "Add compliance monitoring alerts",
                    ],
                }
            )

        return recommendations

    def _get_sample_correlation_chains(self, audit_collector, max_samples=3):
        """Get sample correlation chains for demonstration."""
        samples = []

        for correlation_id, _event_ids in list(audit_collector.correlation_map.items())[
            :max_samples
        ]:
            events = audit_collector.get_events_by_correlation(correlation_id)
            samples.append(
                {
                    "correlation_id": correlation_id,
                    "event_count": len(events),
                    "events": events[:5],  # Show first 5 events
                }
            )

        return samples

    def _print_audit_summary(self, report):
        """Print audit test summary."""
        print("\\n" + "=" * 50)
        print("📋 AUDITABILITY TEST SUMMARY")
        print("=" * 50)

        summary = report["test_summary"]
        quality = report["audit_quality_metrics"]

        print(f"📊 Scenarios tested: {len(summary['scenarios_tested'])}")
        print(f"📝 Total events generated: {summary['total_events_generated']}")
        print(f"🔗 Correlation chains: {summary['total_correlation_chains']}")
        print(f"✅ Completeness score: {quality['completeness_score']:.2f}")
        print(f"🔍 Traceability score: {quality['traceability_score']:.2f}")

        compliance = report["compliance_report"]["compliance_checks"]
        passed_checks = len([c for c in compliance if c["passed"]])
        print(f"📋 Compliance checks: {passed_checks}/{len(compliance)} passed")

        gaps = report["gaps_and_recommendations"]["gaps_identified"]
        if gaps:
            print("\\n⚠️  GAPS IDENTIFIED:")
            for gap in gaps[:3]:
                print(f"   • {gap}")

        recommendations = report["gaps_and_recommendations"]["recommendations"]
        if recommendations:
            print("\\n💡 RECOMMENDATIONS:")
            for rec in recommendations[:2]:
                print(f"   🎯 {rec['category']} ({rec['priority']} priority)")
                for action in rec["actions"][:2]:
                    print(f"      - {action}")

        print("\\n✅ Auditability test completed!")
        print("=" * 50)
