"""
Comprehensive Security Integration Example

This example demonstrates the unified security framework in action,
showing how RBAC, ABAC, service mesh security, and compliance scanning
work together to provide enterprise-grade security.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from marty_msf.security.unified_framework import (
    ComplianceFramework,
    SecurityContext,
    SecurityPrincipal,
    UnifiedSecurityFramework,
    get_default_security_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Demonstrate unified security framework capabilities"""

    print("🔐 Unified Security Framework Demo")
    print("=" * 50)

    # 1. Initialize Security Framework
    print("\n1. Initializing Security Framework...")

    config = get_default_security_config()

    # Enhanced configuration for demo
    config.update({
        "identity_providers": {
            "local": {
                "type": "local",
                "enabled": True,
                "default_users": [
                    {
                        "username": "alice",
                        "password": "alice123",
                        "email": "alice@example.com",
                        "full_name": "Alice Administrator",
                        "roles": ["admin", "user"]
                    },
                    {
                        "username": "bob",
                        "password": "bob123",
                        "email": "bob@example.com",
                        "full_name": "Bob User",
                        "roles": ["user"]
                    },
                    {
                        "username": "charlie",
                        "password": "charlie123",
                        "email": "charlie@example.com",
                        "full_name": "Charlie Guest",
                        "roles": ["guest"]
                    }
                ]
            },
            "oidc": {
                "type": "oidc",
                "enabled": False,  # Would be configured for production
                "client_id": "demo-client",
                "client_secret": "demo-secret",
                "issuer_url": "https://auth.example.com"
            }
        },
        "policy_engines": {
            "builtin": {
                "type": "builtin",
                "enabled": True,
                "policies": [
                    {
                        "name": "admin_full_access",
                        "description": "Administrators have full access",
                        "resource": "*",
                        "action": "*",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    },
                    {
                        "name": "user_api_access",
                        "description": "Users can access API endpoints",
                        "resource": "/api/v1/*",
                        "action": "GET",
                        "principal": {"roles": ["user"]},
                        "effect": "allow"
                    },
                    {
                        "name": "user_profile_write",
                        "description": "Users can update their own profile",
                        "resource": "/api/v1/users/profile",
                        "action": "PUT",
                        "principal": {"roles": ["user"]},
                        "effect": "allow"
                    },
                    {
                        "name": "financial_data_access",
                        "description": "Only financial managers can access financial data",
                        "resource": "/api/v1/financial/*",
                        "action": "*",
                        "principal": {"roles": ["financial_manager"]},
                        "effect": "allow"
                    },
                    {
                        "name": "deny_guest_write",
                        "description": "Guests cannot write anything",
                        "resource": "*",
                        "action": "POST|PUT|DELETE",
                        "principal": {"roles": ["guest"]},
                        "effect": "deny"
                    }
                ]
            }
        },
        "service_mesh": {
            "enabled": True,
            "type": "istio",
            "namespace": "demo"
        },
        "compliance": {
            "enabled": True,
            "frameworks": ["gdpr", "hipaa", "pci_dss"]
        }
    })

    # Initialize framework
    security_framework = await create_unified_security_framework(config)

    if not security_framework:
        print("❌ Failed to initialize security framework")
        return

    print("✅ Security framework initialized successfully")

    # 2. Authentication Demo
    print("\n2. Authentication Demo...")

    # Authenticate different users
    users_to_test = [
        {"username": "alice", "password": "alice123", "expected_roles": ["admin", "user"]},
        {"username": "bob", "password": "bob123", "expected_roles": ["user"]},
        {"username": "charlie", "password": "charlie123", "expected_roles": ["guest"]},
        {"username": "invalid", "password": "wrong", "expected_roles": []}
    ]

    authenticated_users = {}

    for user_test in users_to_test:
        credentials = {
            "username": user_test["username"],
            "password": user_test["password"]
        }

        principal = await security_framework.authenticate(credentials)

        if principal:
            authenticated_users[user_test["username"]] = principal
            print(f"  ✅ {user_test['username']}: authenticated with roles {list(principal.roles)}")
        else:
            print(f"  ❌ {user_test['username']}: authentication failed")

    # 3. Authorization Demo
    print("\n3. Authorization Demo...")

    # Test various authorization scenarios
    authorization_tests = [
        {
            "user": "alice",
            "resource": "/api/v1/admin/users",
            "action": "DELETE",
            "expected": True,
            "description": "Admin deleting users"
        },
        {
            "user": "bob",
            "resource": "/api/v1/users/profile",
            "action": "PUT",
            "expected": True,
            "description": "User updating own profile"
        },
        {
            "user": "bob",
            "resource": "/api/v1/admin/users",
            "action": "DELETE",
            "expected": False,
            "description": "User trying admin operation"
        },
        {
            "user": "charlie",
            "resource": "/api/v1/users/profile",
            "action": "PUT",
            "expected": False,
            "description": "Guest trying to write"
        },
        {
            "user": "alice",
            "resource": "/api/v1/financial/reports",
            "action": "GET",
            "expected": False,
            "description": "Admin accessing financial data (needs financial_manager role)"
        }
    ]

    for test in authorization_tests:
        if test["user"] in authenticated_users:
            principal = authenticated_users[test["user"]]

            decision = await security_framework.authorize(
                principal,
                test["resource"],
                test["action"]
            )

            result = "✅" if decision.allowed == test["expected"] else "❌"
            status = "ALLOWED" if decision.allowed else "DENIED"

            print(f"  {result} {test['description']}: {status}")
            print(f"     Reason: {decision.reason}")
            print(f"     Evaluation time: {decision.evaluation_time_ms:.2f}ms")
        else:
            print(f"  ⏭️  Skipping test for {test['user']} (not authenticated)")

    # 4. Service Mesh Security Demo
    print("\n4. Service Mesh Security Demo...")

    # Apply service mesh security policies
    mesh_policies = [
        {
            "type": "authorization",
            "service": "user-service",
            "rules": [
                {
                    "resource": "/api/v1/users/*",
                    "action": "GET",
                    "principal": {"roles": ["user", "admin"]}
                }
            ]
        },
        {
            "type": "mtls",
            "services": ["user-service", "order-service", "payment-service"],
            "mode": "STRICT"
        },
        {
            "type": "rate_limit",
            "service": "payment-service",
            "rate_limit": {
                "max_tokens": 100,
                "tokens_per_fill": 10,
                "fill_interval": "60s"
            }
        }
    ]

    mesh_result = await security_framework.apply_service_mesh_policies(mesh_policies)

    if mesh_result:
        print("  ✅ Service mesh policies applied successfully")
    else:
        print("  ⚠️  Service mesh policies application failed (may be expected if not in K8s)")

    # Get mesh status
    mesh_status = await security_framework.service_mesh_manager.get_mesh_status() if security_framework.service_mesh_manager else None

    if mesh_status:
        print(f"  📊 Mesh Status: {json.dumps(mesh_status, indent=2)}")

    # 5. Compliance Scanning Demo
    print("\n5. Compliance Scanning Demo...")

    frameworks_to_scan = [
        ComplianceFramework.GDPR,
        ComplianceFramework.HIPAA,
        ComplianceFramework.PCI_DSS
    ]

    scan_results = []

    for framework in frameworks_to_scan:
        print(f"  🔍 Scanning {framework.value.upper()} compliance...")

        scope = {
            "security_framework": security_framework,
            "service_mesh": mesh_status,
            "services": [
                {"name": "user-service", "type": "api", "security_enabled": True},
                {"name": "order-service", "type": "api", "security_enabled": True},
                {"name": "payment-service", "type": "api", "security_enabled": True}
            ],
            "consent_management": False,  # Would be true in real implementation
            "data_retention_policies": False,
            "phi_access_controls": True,
            "audit_logging": True,
            "network_segmentation": False,
            "encryption_in_transit": True
        }

        result = await security_framework.scan_compliance(framework, scope)
        scan_results.append(result)

        compliance_score = result.get("compliance_score", 0.0)
        violations_count = len(result.get("violations", []))

        print(f"    📈 Compliance Score: {compliance_score:.1%}")
        print(f"    ⚠️  Violations Found: {violations_count}")

        # Show top violations
        violations = result.get("violations", [])
        if violations:
            print("    🚨 Top Violations:")
            for violation in violations[:3]:  # Show first 3
                severity = violation.get("severity", "unknown")
                description = violation.get("description", "No description")
                print(f"      - [{severity.upper()}] {description}")

    # Generate compliance report
    if scan_results:
        print("\n  📋 Generating Compliance Report...")
        compliance_report = await security_framework.compliance_scanner.generate_compliance_report(scan_results)

        if "executive_summary" in compliance_report:
            summary = compliance_report["executive_summary"]
            print(f"    📊 Overall Compliance Score: {summary.get('overall_compliance_score', 0):.1%}")
            print(f"    🎯 Total Frameworks Scanned: {summary.get('total_frameworks', 0)}")
            print(f"    🚨 Critical Violations: {summary.get('critical_violations', 0)}")

    # 6. Security Status Overview
    print("\n6. Security Framework Status...")

    status = await security_framework.get_security_status()

    print(f"  📊 Framework Status: {status['framework_status']}")
    print(f"  🔑 Active Sessions: {status['active_sessions']}")
    print(f"  🆔 Identity Providers: {', '.join(status['identity_providers'])}")
    print(f"  📜 Policy Engines: {', '.join(status['policy_engines'])}")
    print(f"  🌐 Service Mesh Enabled: {status['service_mesh_enabled']}")
    print(f"  🔍 Compliance Scanner Enabled: {status['compliance_scanner_enabled']}")

    print("\n  📈 Metrics:")
    metrics = status.get('metrics', {})
    for metric_name, metric_value in metrics.items():
        print(f"    - {metric_name.replace('_', ' ').title()}: {metric_value}")

    # 7. Advanced Scenarios
    print("\n7. Advanced Security Scenarios...")

    # Attribute-based access control
    print("  🎯 Attribute-Based Access Control (ABAC)...")

    # Create a user with specific attributes
    financial_user = SecurityPrincipal(
        id="fin_user_001",
        type="user",
        roles={"financial_manager"},
        attributes={
            "department": "finance",
            "clearance_level": "high",
            "location": "headquarters",
            "employment_type": "full_time"
        }
    )

    # Test time-based access (business hours)
    current_hour = datetime.now().hour
    is_business_hours = 9 <= current_hour <= 17

    context = {
        "time_of_day": current_hour,
        "business_hours": is_business_hours,
        "ip_address": "192.168.1.100",
        "user_agent": "MMF-Client/1.0"
    }

    financial_decision = await security_framework.authorize(
        financial_user,
        "/api/v1/financial/sensitive-reports",
        "GET",
        context
    )

    print(f"    💰 Financial Data Access: {'ALLOWED' if financial_decision.allowed else 'DENIED'}")
    print(f"       Reason: {financial_decision.reason}")

    # Risk-based authentication
    print("\n  🎲 Risk-Based Authentication Demo...")

    # Simulate different risk levels
    risk_scenarios = [
        {"location": "headquarters", "device": "known", "risk": "low"},
        {"location": "remote", "device": "known", "risk": "medium"},
        {"location": "foreign", "device": "unknown", "risk": "high"}
    ]

    for scenario in risk_scenarios:
        risk_context = {
            "location": scenario["location"],
            "device_known": scenario["device"] == "known",
            "risk_level": scenario["risk"]
        }

        # In a real implementation, this would trigger additional authentication steps
        additional_auth_required = scenario["risk"] in ["medium", "high"]

        print(f"    🌍 {scenario['location'].title()} + {scenario['device']} device:")
        print(f"       Risk Level: {scenario['risk'].upper()}")
        print(f"       Additional Auth Required: {'YES' if additional_auth_required else 'NO'}")

    print("\n🎉 Unified Security Framework Demo Complete!")
    print("\n📝 Summary:")
    print("  - Authentication: Multiple identity providers with local fallback")
    print("  - Authorization: RBAC and ABAC with fine-grained policies")
    print("  - Service Mesh: Traffic-level security policy enforcement")
    print("  - Compliance: Automated scanning for GDPR, HIPAA, PCI DSS")
    print("  - Monitoring: Comprehensive security status and metrics")
    print("  - Integration: Unified API for all security operations")


# Import function locally to avoid circular import
async def create_unified_security_framework(config):
    """Create unified security framework with error handling"""
    try:
        framework = UnifiedSecurityFramework(config)
        if await framework.initialize():
            return framework
        else:
            return None
    except Exception as e:
        logger.error(f"Failed to create security framework: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())
