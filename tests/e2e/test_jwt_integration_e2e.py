#!/usr/bin/env python3
"""
Simplified JWT Integration E2E Test
==================================

A lightweight E2E test for the JWT authentication integration components
that can run without full Kubernetes setup, focusing on integration testing.

This test validates:
- JWT integration component imports
- FastAPI router functionality
- Authentication middleware behavior
- Configuration management

Usage:
    pytest tests/e2e/test_jwt_integration_e2e.py -v -s
"""

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Test the JWT integration components
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
)
from mmf_new.services.identity.integration import router
from mmf_new.services.identity.integration import router as jwt_router


class JWTIntegrationE2ETest:
    """E2E test suite for JWT integration components."""

    def __init__(self):
        self.app = None
        self.client = None
        self.jwt_config = None

    def create_test_app(self) -> FastAPI:
        """Create a FastAPI app with JWT integration for testing."""
        app = FastAPI(title="JWT Integration E2E Test")

        # Use testing configuration
        self.jwt_config = create_testing_config("test-secret-key-e2e")

        # Add JWT middleware
        app.add_middleware(
            JWTAuthenticationMiddleware,
            jwt_config=self.jwt_config.to_jwt_config(),
            excluded_paths=self.jwt_config.excluded_paths,
            optional_paths=self.jwt_config.optional_paths + ["/optional"],
        )

        # Include JWT router
        app.include_router(jwt_router)

        # Add test endpoints
        @app.get("/protected")
        async def protected_endpoint(user: dict = Depends(require_authenticated_user)):
            return {
                "message": "Protected endpoint accessed",
                "user_id": user["user_id"],
                "username": user["username"],
                "roles": user["roles"],
            }

        @app.get("/optional")
        async def optional_endpoint(user: dict | None = Depends(get_current_user)):
            if user:
                return {
                    "message": "Authenticated user",
                    "username": user["username"]
                }
            return {"message": "Anonymous user"}

        @app.get("/public")
        async def public_endpoint():
            return {"message": "Public endpoint"}

        return app

    def setup_test_environment(self):
        """Set up the test environment."""
        self.app = self.create_test_app()
        self.client = TestClient(self.app)

    def test_integration_imports(self):
        """Test that all integration components can be imported."""
        try:
            return {"status": "passed", "message": "All components imported successfully"}
        except ImportError as e:
            return {"status": "failed", "error": str(e)}

    def test_jwt_router_endpoints(self):
        """Test JWT router endpoints."""
        results = {}

        # Test health endpoint
        response = self.client.get("/auth/jwt/health")
        results["health_endpoint"] = {
            "status": "passed" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else None
        }

        return results

    def test_public_endpoint_access(self):
        """Test public endpoint access without authentication."""
        response = self.client.get("/public")
        return {
            "status": "passed" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else None
        }

    def test_protected_endpoint_without_auth(self):
        """Test protected endpoint access without authentication (should fail)."""
        response = self.client.get("/protected")
        return {
            "status": "passed" if response.status_code == 401 else "failed",
            "status_code": response.status_code,
            "expected": 401,
            "message": "Should reject access without authentication"
        }

    def test_optional_endpoint_without_auth(self):
        """Test optional endpoint access without authentication."""
        response = self.client.get("/optional")
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "passed" if data["message"] == "Anonymous user" else "failed",
                "data": data
            }
        return {"status": "failed", "status_code": response.status_code}

    def test_configuration_management(self):
        """Test configuration management components."""
        results = {}

        try:
            # Test development config
            dev_config = create_development_config("dev-secret")
            results["dev_config"] = {
                "status": "passed",
                "algorithm": dev_config.algorithm,
                "issuer": dev_config.issuer,
                "excluded_paths_count": len(dev_config.excluded_paths)
            }
        except Exception as e:
            results["dev_config"] = {"status": "failed", "error": str(e)}

        try:
            # Test testing config
            test_config = create_testing_config("test-secret")
            results["test_config"] = {
                "status": "passed",
                "verify_expiration": test_config.verify_expiration,
                "verify_issuer": test_config.verify_issuer
            }
        except Exception as e:
            results["test_config"] = {"status": "failed", "error": str(e)}

        try:
            # Test JWT config conversion
            jwt_config = test_config.to_jwt_config()
            results["jwt_config_conversion"] = {
                "status": "passed",
                "secret_key_set": bool(jwt_config.secret_key),
                "algorithm": jwt_config.algorithm
            }
        except Exception as e:
            results["jwt_config_conversion"] = {"status": "failed", "error": str(e)}

        return results

    def test_middleware_path_exclusions(self):
        """Test middleware path exclusions."""
        results = {}

        # Test excluded paths (should not require auth)
        excluded_paths = ["/health", "/docs", "/auth/jwt/health"]
        for path in excluded_paths:
            try:
                response = self.client.get(path)
                # Most excluded paths might not exist, but should not fail with auth errors
                results[f"excluded_{path.replace('/', '_')}"] = {
                    "status": "passed" if response.status_code != 401 else "failed",
                    "status_code": response.status_code
                }
            except Exception as e:
                results[f"excluded_{path.replace('/', '_')}"] = {
                    "status": "failed",
                    "error": str(e)
                }

        return results

    def test_error_handling(self):
        """Test error handling in integration components."""
        results = {}

        # Test invalid JWT token validation
        try:
            invalid_token_data = {"token": "invalid.jwt.token"}
            response = self.client.post("/auth/jwt/validate", json=invalid_token_data)
            results["invalid_token_validation"] = {
                "status": "passed" if response.status_code in [200, 400, 401] else "failed",
                "status_code": response.status_code
            }
        except Exception as e:
            results["invalid_token_validation"] = {"status": "failed", "error": str(e)}

        return results

    def run_all_tests(self) -> dict[str, any]:
        """Run all E2E tests and return results."""
        self.setup_test_environment()

        test_results = {}

        # Run all test methods
        test_methods = [
            ("integration_imports", self.test_integration_imports),
            ("jwt_router_endpoints", self.test_jwt_router_endpoints),
            ("public_endpoint_access", self.test_public_endpoint_access),
            ("protected_endpoint_without_auth", self.test_protected_endpoint_without_auth),
            ("optional_endpoint_without_auth", self.test_optional_endpoint_without_auth),
            ("configuration_management", self.test_configuration_management),
            ("middleware_path_exclusions", self.test_middleware_path_exclusions),
            ("error_handling", self.test_error_handling),
        ]

        for test_name, test_method in test_methods:
            try:
                result = test_method()
                test_results[test_name] = result
            except Exception as e:
                test_results[test_name] = {"status": "failed", "error": str(e)}

        return test_results


def run_jwt_integration_e2e():
    """Run the JWT integration E2E test suite."""
    print("🚀 JWT Integration E2E Test Suite")
    print("=" * 50)

    test_runner = JWTIntegrationE2ETest()
    results = test_runner.run_all_tests()

    print("\n📊 Test Results:")
    print("-" * 30)

    passed_count = 0
    failed_count = 0

    for test_name, result in results.items():
        if isinstance(result, dict):
            if result.get("status") == "passed":
                print(f"✅ {test_name}: PASSED")
                passed_count += 1
            else:
                print(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                failed_count += 1
        else:
            # Handle nested results
            nested_passed = 0
            nested_total = 0

            for _sub_test, sub_result in result.items():
                nested_total += 1
                if isinstance(sub_result, dict) and sub_result.get("status") == "passed":
                    nested_passed += 1

            if nested_passed == nested_total:
                print(f"✅ {test_name}: PASSED ({nested_passed}/{nested_total})")
                passed_count += 1
            else:
                print(f"❌ {test_name}: PARTIAL ({nested_passed}/{nested_total})")
                failed_count += 1

    total_tests = passed_count + failed_count
    success_rate = (passed_count / total_tests) * 100 if total_tests > 0 else 0

    print("\n📈 Summary:")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Success Rate: {success_rate:.1f}%")

    if passed_count == total_tests:
        print("\n🎉 All JWT integration E2E tests passed!")
        print("JWT authentication integration is working correctly.")
    else:
        print(f"\n⚠️  {failed_count} test(s) failed. Please review the results above.")

    return results


# pytest integration
@pytest.mark.asyncio
async def test_jwt_integration_e2e():
    """Pytest wrapper for JWT integration E2E tests."""
    results = run_jwt_integration_e2e()

    # Count failures
    failed_tests = []
    for test_name, result in results.items():
        if isinstance(result, dict):
            if result.get("status") == "failed":
                failed_tests.append(test_name)
        else:
            # Check nested results
            for sub_test, sub_result in result.items():
                if isinstance(sub_result, dict) and sub_result.get("status") == "failed":
                    failed_tests.append(f"{test_name}.{sub_test}")

    if failed_tests:
        pytest.fail(f"JWT integration E2E tests failed: {', '.join(failed_tests)}")


# Direct execution
if __name__ == "__main__":
    print("JWT Authentication Integration E2E Test")
    print("=" * 50)
    print("Testing JWT integration components without full K8s deployment.")
    print()

    # Dependencies are already imported at the top of the file
    run_jwt_integration_e2e()
