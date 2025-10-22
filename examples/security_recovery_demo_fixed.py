"""
Security Recovery Demonstration

This script demonstrates the recovered security functionality:
1. SecurityHardeningFramework - Comprehensive security integration
2. SecurityStatusReporter - Detailed status reporting
3. SecurityEventManager - Enhanced event management

Usage:
    python examples/security_recovery_demo.py
"""

import asyncio
from datetime import datetime, timedelta, timezone

from marty_msf.security import (
    ComplianceFramework,
    create_event_manager,
    create_security_framework,
    create_status_reporter,
)
from marty_msf.security.monitoring import SecurityEventSeverity, SecurityEventType


async def demonstrate_security_recovery():
    """Demonstrate the recovered security functionality."""
    print("🔐 Security Recovery Demonstration")
    print("=" * 50)

    # 1. Create Security Hardening Framework
    print("\n1. 📊 Creating Security Hardening Framework...")
    config = {
        "compliance_standards": ["GDPR", "HIPAA"],
        "threat_detection": {"enabled": True},
        "authentication": {"type": "environment"},
        "authorization": {"type": "role_based"},
        "secret_manager": {"type": "environment"}
    }

    framework = create_security_framework("demo_service", config)
    print(f"   ✅ Framework created for service: {framework.service_name}")

    # 2. Demonstrate Authentication
    print("\n2. 🔐 Testing Authentication...")
    principal = framework.authenticate_principal(
        credentials={"username": "demo_user", "password": "demo_pass"},
        provider="demo"
    )

    if principal:
        print(f"   ✅ Authentication successful for: {principal.id}")

        # 3. Demonstrate Authorization
        print("\n3. 🛡️  Testing Authorization...")
        decision = framework.authorize_action(
            principal=principal,
            resource="demo_resource",
            action="read",
            context={"ip_address": "127.0.0.1"}
        )

        print(f"   {'✅' if decision.allowed else '❌'} Authorization: {decision.reason}")
    else:
        print("   ❌ Authentication failed")

    # 4. Demonstrate Security Status Reporting
    print("\n4. 📈 Security Status Report...")
    status_reporter = create_status_reporter(framework.bootstrap)
    status = status_reporter.get_comprehensive_status()

    print(f"   Overall Status: {status['overall_status']}")
    print(f"   Components Initialized: {len([c for c in status['components'].values() if c.get('initialized')])}")
    print(f"   Alerts: {len(status['alerts'])}")
    print(f"   Recommendations: {len(status['recommendations'])}")

    # 5. Demonstrate Enhanced Event Management
    print("\n5. 📝 Enhanced Event Management...")
    event_manager = create_event_manager()

    # Log some demonstration events
    auth_event = event_manager.log_authentication_event(
        success=True,
        user_id="demo_user",
        source_ip="127.0.0.1",
        method="password"
    )
    print(f"   ✅ Logged authentication event: {auth_event.event_id[:8]}")

    authz_event = event_manager.log_authorization_event(
        allowed=True,
        user_id="demo_user",
        resource="demo_resource",
        action="read",
        reason="User has required role"
    )
    print(f"   ✅ Logged authorization event: {authz_event.event_id[:8]}")

    # Simulate multiple failed authentications to trigger threat detection
    print("\n6. 🚨 Threat Detection Demonstration...")
    for i in range(6):
        event_manager.log_authentication_event(
            success=False,
            user_id="attacker",
            source_ip="192.168.1.100",
            method="password",
            details={"attempt": i + 1}
        )

    # Get event summary
    summary = event_manager.get_event_summary(timedelta(minutes=1))
    print(f"   📊 Events in last minute: {summary['total_events']}")
    print(f"   🔍 Threat indicators: {len(summary['threat_indicators'])}")

    if summary['threat_indicators']:
        print("   ⚠️  Threat indicators detected:")
        for indicator in summary['threat_indicators']:
            print(f"      - {indicator}")

    # 7. Demonstrate Framework Status
    print("\n7. 🎯 Framework Comprehensive Status...")
    framework_status = framework.get_security_status()

    print(f"   Service: {framework_status['service']}")
    print(f"   Framework Status: {framework_status['framework_status']}")
    print(f"   Security Events: {framework_status['metrics']['security_events']}")
    print(f"   Threats Detected: {framework_status['metrics']['threats_detected']}")

    # 8. Demonstrate Compliance Scanning
    print("\n8. 📋 Compliance Scanning...")
    for standard in [ComplianceFramework.GDPR, ComplianceFramework.HIPAA]:
        compliance_result = framework.scan_compliance(standard)
        status_icon = "✅" if compliance_result["passed"] else "❌"
        print(f"   {status_icon} {standard.value.upper()}: {compliance_result['score']:.1%} ({compliance_result['summary']})")

    # 9. Show Security Events
    print("\n9. 📜 Recent Security Events...")
    recent_events = framework.get_security_events(limit=5)
    for event in recent_events:
        severity_icon = {
            'info': 'ℹ️',
            'low': '🟡',
            'medium': '🟠',
            'high': '🔴',
            'critical': '🚨'
        }.get(event.raw_data.get('threat_level', 'low'), 'ℹ️')

        print(f"   {severity_icon} {event.timestamp.strftime('%H:%M:%S')} - {event.raw_data.get('result', 'unknown')} ({event.action})")

    print("\n" + "=" * 50)
    print("🎉 Security Recovery Demonstration Complete!")
    print("\nRecovered Functionality:")
    print("✅ SecurityHardeningFramework - Unified security management")
    print("✅ SecurityStatusReporter - Comprehensive status reporting")
    print("✅ SecurityEventManager - Enhanced event management with threat detection")
    print("✅ Compliance scanning and reporting")
    print("✅ Real-time security monitoring")


if __name__ == "__main__":
    asyncio.run(demonstrate_security_recovery())
