"""
E2E Test for Vault Plugin Integration

This test verifies that the Vault plugin is correctly loaded and active
inside the deployed Identity Service in Kubernetes.

Prerequisites:
1. The environment must be deployed (deploy/deploy.sh).
2. The Identity Service must be accessible at http://localhost:8000 (kubectl port-forward).
"""

import os
import time

import pytest
import requests

# Configuration
IDENTITY_SERVICE_URL = os.getenv("IDENTITY_SERVICE_URL", "http://localhost:8000")


def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for the service to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=1)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def test_vault_plugin_integration():
    """Verify that the Vault plugin is loaded and active in the Identity Service."""

    print(f"Connecting to Identity Service at {IDENTITY_SERVICE_URL}...")

    if not wait_for_service(IDENTITY_SERVICE_URL):
        pytest.fail(
            f"Identity Service not reachable at {IDENTITY_SERVICE_URL}. "
            "Please ensure the service is deployed and port-forwarded: "
            "kubectl port-forward -n mmf-system svc/identity-service 8000:80"
        )

    # Check plugins endpoint
    try:
        response = requests.get(f"{IDENTITY_SERVICE_URL}/plugins", timeout=5)
        assert response.status_code == 200, f"Failed to get plugins: {response.text}"

        data = response.json()
        plugins = data.get("plugins", {})

        # Verify Vault plugin is present
        assert "secrets.vault" in plugins, "Vault plugin not found in loaded plugins list"

        # Verify Vault plugin status
        plugin_info = plugins["secrets.vault"]
        status = plugin_info.get("status")
        version = plugin_info.get("version")

        print(f"Vault Plugin Status: {status}, Version: {version}")

        assert status == "ACTIVE", (
            f"Vault plugin is {status}, expected ACTIVE. Check service logs for errors."
        )

    except requests.RequestException as e:
        pytest.fail(f"Request failed: {e}")


if __name__ == "__main__":
    # Allow running directly
    try:
        test_vault_plugin_integration()
        print("Test passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)
