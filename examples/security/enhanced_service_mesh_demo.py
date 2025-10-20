"""
Enhanced Service Mesh Integration Demo
Demonstrates real-time security policy enforcement and monitoring
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from marty_msf.framework.service_mesh import create_enhanced_service_mesh_manager
from marty_msf.security.bridge import (
    UnifiedSecurityFrameworkBridge as UnifiedSecurityFramework,
)
from marty_msf.security.unified_framework import (
    BuiltinPolicyEngine,
    SecurityPolicyType,
    SecurityPrincipal,
    create_unified_security_framework,
    get_default_security_config,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_enhanced_service_mesh_integration():
    """Demonstrate enhanced service mesh integration with real-time security"""

    print("🚀 Enhanced Service Mesh Integration Demo")
    print("=" * 60)

    # 1. Initialize Unified Security Framework
    print("\n📋 Step 1: Initialize Unified Security Framework")
    config = get_default_security_config()
    config.update({
        "service_mesh": {
            "enabled": True,
            "type": "istio"
        },
        "identity_providers": {
            "oidc": {
                "type": "oidc",
                "issuer": "https://accounts.google.com",
                "client_id": "demo-client-id",
                "enabled": True
            },
            "local": {
                "type": "local",
                "enabled": True
            }
        }
    })

    security_framework = await create_unified_security_framework(config)
    print("✅ Unified Security Framework initialized")

    # 2. Enable Service Mesh Integration
    print("\n🔒 Step 2: Enable Service Mesh Integration")
    integration_success = await security_framework.enable_service_mesh_integration(
        mesh_type="istio",
        namespace="production"
    )

    if integration_success:
        print("✅ Service mesh integration enabled successfully")
    else:
        print("⚠️  Service mesh integration failed (likely due to missing istioctl)")

    # 3. Define Real-World Security Policies
    print("\n📜 Step 3: Define Real-World Security Policies")

    security_policies = [
        {
            "metadata": {
                "name": "payment-service-protection",
                "description": "Protect payment service with strict access controls"
            },
            "type": "authorization",
            "spec": {
                "action": "ALLOW",
                "rules": [
                    {
                        "from": [
                            {
                                "source": {
                                    "principals": ["cluster.local/ns/frontend/sa/web-service"]
                                }
                            }
                        ],
                        "to": [
                            {
                                "operation": {
                                    "methods": ["POST"],
                                    "paths": ["/api/v1/payments/*"]
                                }
                            }
                        ]
                    }
                ]
            }
        },
        {
            "metadata": {
                "name": "database-access-control",
                "description": "Restrict database access to authorized services only"
            },
            "type": "authorization",
            "spec": {
                "action": "ALLOW",
                "rules": [
                    {
                        "from": [
                            {
                                "source": {
                                    "principals": [
                                        "cluster.local/ns/backend/sa/user-service",
                                        "cluster.local/ns/backend/sa/order-service"
                                    ]
                                }
                            }
                        ],
                        "to": [
                            {
                                "operation": {
                                    "ports": ["5432"]
                                }
                            }
                        ]
                    }
                ]
            }
        },
        {
            "metadata": {
                "name": "rate-limiting-policy",
                "description": "Rate limiting for public APIs"
            },
            "type": "rate_limiting",
            "spec": {
                "rate_limiting": {
                    "max_tokens": 1000,
                    "tokens_per_fill": 100,
                    "fill_interval": "60s"
                }
            }
        }
    ]

    for policy in security_policies:
        print(f"  📋 {policy['metadata']['name']}: {policy['metadata']['description']}")

    # 4. Demonstrate Runtime Policy Enforcement
    print("\n⚡ Step 4: Demonstrate Runtime Policy Enforcement")

    # Simulate deploying services with security policies
    services = [
        {"name": "payment-service", "namespace": "production"},
        {"name": "user-service", "namespace": "production"},
        {"name": "order-service", "namespace": "production"}
    ]

    for service in services:
        print(f"\n🔧 Enforcing policies for {service['name']}...")

        if hasattr(security_framework, '_enhanced_mesh_manager'):
            # Apply service-specific policies
            service_policies = [
                policy for policy in security_policies
                if service['name'] in policy['metadata']['description'].lower()
            ]

            if not service_policies:
                service_policies = [security_policies[0]]  # Default policy

            success = await security_framework.enforce_service_policies(
                service_name=service['name'],
                namespace=service['namespace'],
                policies=service_policies
            )

            if success:
                print(f"  ✅ Policies enforced for {service['name']}")
            else:
                print(f"  ⚠️  Policy enforcement simulation for {service['name']}")
        else:
            print(f"  ⚠️  Service mesh not available - simulating policy enforcement for {service['name']}")

    # 5. Demonstrate Security Monitoring
    print("\n📊 Step 5: Demonstrate Security Monitoring")

    # Monitor security events
    print("🔍 Monitoring security events...")
    security_events = await security_framework.monitor_service_mesh_security("production")

    if security_events:
        print(f"  📈 Found {len(security_events)} security events:")
        for event in security_events[:3]:  # Show first 3 events
            print(f"    • {event.get('type', 'unknown')}: {event.get('message', 'No details')}")
    else:
        print("  📈 No security events found (service mesh may not be available)")

    # 6. Authentication and Authorization Demo
    print("\n🔐 Step 6: Authentication and Authorization Demo")

    # Simulate authentication
    credentials = {
        "username": "service-account-payment",
        "password": "secure-token-123",
        "type": "service_account"
    }

    principal = await security_framework.authenticate(credentials, provider="local")
    if principal:
        print(f"✅ Authenticated principal: {principal.id}")
        print(f"   Roles: {', '.join(principal.roles) if principal.roles else 'None'}")
        print(f"   Provider: {principal.identity_provider}")

        # Test authorization for different resources
        authorization_tests = [
            {"resource": "/api/v1/payments", "action": "POST"},
            {"resource": "/api/v1/users", "action": "GET"},
            {"resource": "/admin/config", "action": "PUT"},
        ]

        print("\n🔍 Authorization Tests:")
        for test in authorization_tests:
            decision = await security_framework.authorize(
                principal=principal,
                resource=test["resource"],
                action=test["action"]
            )

            status = "✅ ALLOWED" if decision.allowed else "❌ DENIED"
            print(f"  {status} {test['action']} {test['resource']} - {decision.reason}")
    else:
        print("❌ Authentication failed")

    # 7. Enhanced Service Mesh Manager Direct Demo
    print("\n🛠️  Step 7: Enhanced Service Mesh Manager Direct Demo")

    # Create enhanced service mesh manager directly
    enhanced_manager = create_enhanced_service_mesh_manager(
        service_mesh_type="istio",
        config={"security": {"mtls_mode": "STRICT"}},
        security_manager=security_framework
    )

    print(f"🔧 Enhanced manager created for: {enhanced_manager.service_mesh_type}")
    print(f"   Service mesh available: {enhanced_manager.is_installed}")

    # Generate deployment script with security
    security_config = {
        "security": {
            "mtls_mode": "STRICT",
            "allowed_principals": ["cluster.local/ns/production/sa/frontend"],
            "allowed_methods": ["GET", "POST"],
            "rate_limiting": {
                "max_tokens": 1000,
                "tokens_per_fill": 100,
                "fill_interval": "60s"
            },
            "authorization_policies": True
        },
        "port": 8080
    }

    deployment_script = enhanced_manager.generate_deployment_script(
        service_name="secure-payment-service",
        config=security_config
    )

    print("\n📜 Generated deployment script preview:")
    print("─" * 40)
    script_lines = deployment_script.split('\n')
    for i, line in enumerate(script_lines[:15]):  # Show first 15 lines
        print(line)
    if len(script_lines) > 15:
        print(f"... ({len(script_lines) - 15} more lines)")
    print("─" * 40)

    # 8. Security Validation
    print("\n🔍 Step 8: Security Validation")

    validation_results = await enhanced_manager.validate_security_integration("production")

    print("🔒 Security Integration Validation:")
    print(f"  Security Manager Available: {'✅' if validation_results.get('security_manager_available') else '❌'}")
    print(f"  Service Mesh Installed: {'✅' if validation_results.get('service_mesh_installed') else '❌'}")
    print(f"  Namespace Secured: {'✅' if validation_results.get('namespace_secured') else '❌'}")
    print(f"  mTLS Enabled: {'✅' if validation_results.get('mtls_enabled') else '❌'}")
    print(f"  Policies Applied: {'✅' if validation_results.get('policies_applied') else '❌'}")

    if validation_results.get('issues'):
        print("  Issues found:")
        for issue in validation_results['issues']:
            print(f"    ⚠️  {issue}")

    # 9. Performance Metrics
    print("\n📊 Step 9: Performance Metrics")

    status = await security_framework.get_security_status()
    print("🎯 Security Framework Metrics:")
    print(f"  Active Sessions: {status['active_sessions']}")
    print(f"  Policy Cache Size: {status['policy_cache_size']}")
    print(f"  Audit Log Size: {status['audit_log_size']}")

    metrics = status.get('metrics', {})
    print("📈 Operation Metrics:")
    for metric_name, value in metrics.items():
        print(f"  {metric_name.replace('_', ' ').title()}: {value}")

    print("\n🎉 Enhanced Service Mesh Integration Demo Complete!")
    print("=" * 60)

    return {
        "security_framework": security_framework,
        "enhanced_manager": enhanced_manager,
        "validation_results": validation_results,
        "status": status
    }


async def demo_policy_scenarios():
    """Demonstrate specific policy enforcement scenarios"""

    print("\n🎭 Policy Enforcement Scenarios")
    print("=" * 40)

    # Initialize framework
    config = get_default_security_config()
    security_framework = await create_unified_security_framework(config)

    # Scenario 1: Microservice Communication
    print("\n🔄 Scenario 1: Microservice Communication Policy")

    frontend_principal = await security_framework.authenticate({
        "username": "frontend-service",
        "service_account": True
    })

    if frontend_principal:
        frontend_principal.roles.add("frontend-service")

        # Test different API endpoints
        api_tests = [
            ("/api/v1/users/profile", "GET", "Should be allowed for frontend"),
            ("/api/v1/payments/charge", "POST", "Should be allowed for frontend"),
            ("/admin/users/delete", "DELETE", "Should be denied for frontend"),
        ]

        for resource, action, expectation in api_tests:
            decision = await security_framework.authorize(
                principal=frontend_principal,
                resource=resource,
                action=action
            )

            status = "✅" if decision.allowed else "❌"
            print(f"  {status} {action} {resource}")
            print(f"     {expectation}")
            print(f"     Reason: {decision.reason}")

    # Scenario 2: Database Access Control
    print("\n🗄️  Scenario 2: Database Access Control")

    db_service_principal = await security_framework.authenticate({
        "username": "db-service",
        "service_account": True
    })

    if db_service_principal:
        db_service_principal.roles.add("database-service")

        # Test database operations
        db_tests = [
            ("postgres://db:5432/users", "READ", "Should be allowed for db service"),
            ("postgres://db:5432/users", "WRITE", "Should be allowed for db service"),
            ("postgres://db:5432/admin", "DELETE", "Should be restricted"),
        ]

        for resource, action, expectation in db_tests:
            decision = await security_framework.authorize(
                principal=db_service_principal,
                resource=resource,
                action=action
            )

            status = "✅" if decision.allowed else "❌"
            print(f"  {status} {action} {resource}")
            print(f"     {expectation}")
            print(f"     Reason: {decision.reason}")


if __name__ == "__main__":
    # Run the enhanced demo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Main demo
        demo_results = loop.run_until_complete(demo_enhanced_service_mesh_integration())

        # Additional scenarios
        loop.run_until_complete(demo_policy_scenarios())

        print("\n💡 Demo Notes:")
        print("• This demo shows real service mesh integration capabilities")
        print("• Install istioctl or linkerd CLI for full functionality")
        print("• The unified security framework consolidates all MMF security features")
        print("• Runtime policy enforcement provides real-time protection")
        print("• Security monitoring enables proactive threat detection")

    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        logger.exception("Demo failed")
    finally:
        loop.close()
