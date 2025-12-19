import sys
from unittest.mock import MagicMock, patch

import pytest

# We want to test that the module can be imported even if cloud SDKs are missing.
# We don't need to mock them here because we want to verify the real behavior
# in an environment where they might be missing (like this one).


def test_unified_config_importable_without_cloud_deps():
    """Test that the module can be imported even if cloud SDKs are missing."""
    try:
        from mmf.framework.infrastructure.unified_config import (
            AZURE_AVAILABLE,
            BOTO3_AVAILABLE,
            GCP_AVAILABLE,
            AWSSecretsManagerBackend,
            AzureKeyVaultBackend,
            GCPSecretManagerBackend,
        )
    except ImportError as e:
        pytest.fail(f"mmf.framework.infrastructure.unified_config could not be imported: {e}")

    # Verify that the flags are set correctly (should be False in this env)
    # Note: If we install them later, this test might need adjustment or mocking.
    # For now, we assume they are missing based on previous checks.

    # We can't strictly assert False because the environment might change,
    # but we can assert that the module imported successfully.
    pass


def test_aws_backend_availability():
    """Test that AWS backend handles missing boto3 gracefully."""
    from mmf.framework.infrastructure.unified_config import (
        BOTO3_AVAILABLE,
        AWSSecretsManagerBackend,
    )

    backend = AWSSecretsManagerBackend()
    assert backend._check_availability() == BOTO3_AVAILABLE

    if not BOTO3_AVAILABLE:
        # Accessing client raises RuntimeError
        with pytest.raises(RuntimeError, match="boto3 is required"):
            _ = backend.client


def test_gcp_backend_availability():
    """Test that GCP backend handles missing google-cloud-secret-manager gracefully."""
    from mmf.framework.infrastructure.unified_config import (
        GCP_AVAILABLE,
        GCPSecretManagerBackend,
    )

    backend = GCPSecretManagerBackend()
    assert backend._check_availability() == GCP_AVAILABLE

    if not GCP_AVAILABLE:
        with pytest.raises(RuntimeError, match="google-cloud-secret-manager is required"):
            _ = backend.client


def test_azure_backend_availability():
    """Test that Azure backend handles missing azure-identity gracefully."""
    from mmf.framework.infrastructure.unified_config import (
        AZURE_AVAILABLE,
        AzureKeyVaultBackend,
    )

    backend = AzureKeyVaultBackend()
    assert backend._check_availability() == AZURE_AVAILABLE

    if not AZURE_AVAILABLE:
        with pytest.raises(RuntimeError, match="azure-keyvault-secrets is required"):
            _ = backend.client
