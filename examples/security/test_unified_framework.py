#!/usr/bin/env python3
"""
Simple test to verify the unified security framework works correctly
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import asyncio
import logging

from marty_msf.security.bridge import SecurityPolicyType
from marty_msf.security.bridge import (
    UnifiedSecurityFrameworkBridge as UnifiedSecurityFramework,
)
from marty_msf.security.bridge import create_unified_security_framework
from marty_msf.security.interfaces import SecurityContext, SecurityPrincipal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_unified_framework():
    """Test basic unified framework functionality"""

    print("🔐 Testing Unified Security Framework")
    print("=" * 40)

    # Configuration for the unified security framework
    security_config = {
        "default_identity_provider": "local",
        "policy_cache_ttl": 300,
        "audit_enabled": True,
        "service_mesh_enabled": False,
        "compliance_scanning_enabled": False
    }

    # Create unified security framework
    security_framework = await create_unified_security_framework(security_config)

    if not security_framework:
        print("❌ Failed to initialize security framework")
        return False

    print("✅ Security framework initialized successfully")

    # Create a test principal
    test_principal = SecurityPrincipal(
        id="test_user",
        type="user",
        roles={"user", "admin"},
        attributes={"department": "engineering", "level": "senior"}
    )

    print(f"✅ Created test principal: {test_principal.id}")

    # Test authorization
    decision = await security_framework.authorize(
        test_principal,
        "/api/v1/users",
        "GET"
    )

    print(f"✅ Authorization check completed: {decision.allowed}")
    print(f"   Reason: {decision.reason}")

    # Check metrics
    print(f"✅ Authorization checks performed: {security_framework.metrics['authorization_checks']}")

    return True

if __name__ == "__main__":
    success = asyncio.run(test_unified_framework())
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
