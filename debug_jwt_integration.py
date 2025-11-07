#!/usr/bin/env python3
"""
Simple test runner for JWT integration to debug issues.
"""

import os
import sys
import traceback

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mmf_new.services.identity.integration import (
    AuthenticatedUserResponse,
    AuthenticateJWTRequestModel,
    AuthenticationResponse,
    JWTAuthConfig,
    JWTAuthenticationMiddleware,
    TokenValidationResponse,
    ValidateTokenRequestModel,
    create_development_config,
    create_production_config,
    create_testing_config,
    get_config_for_environment,
    get_current_user,
    load_config_from_env,
    require_authenticated_user,
    require_permission,
    require_role,
    router,
)

sys.path.insert(0, os.getcwd())


def test_imports():
    """Test JWT integration imports."""
    try:
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False


def test_config_creation():
    """Test configuration creation."""
    try:
        config = create_testing_config("test-secret")
        print(f"✅ Testing config created: {config}")
        return True
    except Exception as e:
        print(f"❌ Config creation failed: {e}")
        traceback.print_exc()
        return False


def test_fastapi_integration():
    """Test FastAPI integration."""
    try:

        app = FastAPI()
        config = create_testing_config("test-secret")

        print(f"✅ Config created: {type(config)}")

        # Try to add middleware
        app.add_middleware(
            JWTAuthenticationMiddleware,
            jwt_config=config.to_jwt_config(),
            excluded_paths=config.excluded_paths,
        )

        print("✅ Middleware added")

        # Include router
        app.include_router(router)
        print("✅ Router included")

        # Create test client
        client = TestClient(app)
        print("✅ Test client created")

        # Test health endpoint
        response = client.get("/auth/jwt/health")
        print(f"✅ Health endpoint: {response.status_code} - {response.json()}")

        return True
    except Exception as e:
        print(f"❌ FastAPI integration failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("🔧 JWT Integration Debug Tests")
    print("=" * 40)

    tests = [
        ("Imports", test_imports),
        ("Config Creation", test_config_creation),
        ("FastAPI Integration", test_fastapi_integration),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\n🧪 Testing {name}...")
        if test_func():
            passed += 1
        print("-" * 40)

    print(f"\n📊 Results: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
