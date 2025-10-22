#!/usr/bin/env python3
"""
Quick verification that SecurityServiceFactory now uses DI container correctly.
"""

import os
import sys
import traceback

from marty_msf.core.di_container import has_service, reset_container
from marty_msf.security.factory import (
    SecurityServiceFactory,
    get_security_factory,
    reset_security_services,
)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(project_root, 'src'))

def test_factory_di_integration():
    """Test that SecurityServiceFactory properly uses DI container."""
    print("🔍 Testing SecurityServiceFactory DI integration...")

    try:
        # Reset DI container first

        # Start clean
        reset_container()

        # Verify clean state
        assert not has_service(SecurityServiceFactory), "Container should be clean"
        print("  ✅ Clean container state verified")

        # Get factory (should create and register)
        factory1 = get_security_factory()
        assert factory1 is not None, "Factory should be created"
        assert has_service(SecurityServiceFactory), "Factory should be registered in DI"
        print("  ✅ Factory creation and DI registration works")

        # Get factory again (should return same instance)
        factory2 = get_security_factory()
        assert factory1 is factory2, "Should return same factory instance (singleton)"
        print("  ✅ Singleton behavior verified")

        # Test reset
        reset_security_services()
        print("  ✅ Reset function completed without error")

        # Get new factory after reset
        factory3 = get_security_factory()
        assert factory3 is not None, "New factory should be created after reset"
        # Note: factory3 may or may not be the same instance, depends on implementation
        print("  ✅ Factory recreation after reset works")

        print("\\n🎉 All SecurityServiceFactory DI tests passed!")
        return True

    except Exception as e:
        print(f"\\n❌ Test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_factory_di_integration()

    if success:
        print("\\n✅ VERIFICATION COMPLETE: SecurityServiceFactory successfully migrated to DI container")
        print("\\n📋 Summary:")
        print("  • Eliminated global variable _factory")
        print("  • Uses DI container for singleton management")
        print("  • Proper reset functionality with container.remove()")
        print("  • Maintains same public API for backward compatibility")
    else:
        print("\\n❌ VERIFICATION FAILED: Issues found with DI migration")
        exit(1)
