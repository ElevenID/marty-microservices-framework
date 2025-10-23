#!/usr/bin/env python3
"""
Quick verification test for the migrated security factory.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from marty_msf.security_core.factory import (
    SecurityServiceFactory,
    check_security_services_health,
    get_security_factory,
    initialize_security_services,
)


def test_migrated_factory():
    """Test that the migrated factory has the same interface as the legacy factory."""
    print("🔍 Testing migrated security factory...")

    # Test 1: Create factory instance
    factory = SecurityServiceFactory()
    print(f"✅ Created factory instance: {type(factory).__name__}")

    # Test 2: Check initialization state
    assert not factory.is_initialized(), "Factory should not be initialized initially"
    print("✅ Initial state: factory not initialized")

    # Test 3: Check health before initialization
    health = check_security_services_health()
    print(f"✅ Health check works: {health}")

    # Test 4: Test global factory access
    global_factory = get_security_factory()
    print(f"✅ Global factory access: {type(global_factory).__name__}")

    # Test 5: Test factory reset
    factory.reset()
    assert not factory.is_initialized(), "Factory should be reset"
    print("✅ Factory reset works")

    print("🎉 All basic factory tests passed!")

if __name__ == "__main__":
    test_migrated_factory()
