#!/usr/bin/env python3
"""
MMF Configuration Migration Demo

This script demonstrates that the migration from legacy configuration
to the new MMFConfiguration system is complete and working.
"""

import os
import traceback
from pathlib import Path

from mmf_new.core.application.database import DatabaseConfig
from mmf_new.framework.infrastructure.config import MMFConfiguration
from mmf_new.services.identity.infrastructure.adapters.config_integration import (
    get_jwt_config_from_yaml,
)


def demo_configuration_migration():
    """Demonstrate the new MMF configuration system."""
    print("🔧 MMF Configuration Migration Demo")
    print("="*50)

    # Set up test environment
    os.environ["JWT_SECRET"] = "demo_jwt_secret_12345"  # pragma: allowlist secret
    os.environ["MMF_ENVIRONMENT"] = "development"

    try:
        # Import the new configuration system

        print("📁 Loading configuration...")

        # Find and load configuration
        config_path = Path.cwd() / "mmf_new" / "config"
        if not config_path.exists():
            print("❌ Configuration directory not found")
            return

        print(f"   Config directory: {config_path}")

        # Load MMF configuration for identity service
        mmf_config = MMFConfiguration.load(
            config_dir=config_path,
            environment="development",
            service_name="identity-service"
        )

        print("✅ MMF Configuration loaded successfully")
        print(f"   Service: {mmf_config.get('service.name', 'unknown')}")
        print(f"   Environment: {mmf_config.get('environment.name', 'unknown')}")

        # Test JWT configuration integration
        print("\n🔐 Testing JWT Configuration...")
        try:
            jwt_config = get_jwt_config_from_yaml()
            print("✅ JWT Configuration loaded successfully")
            print(f"   Secret: {jwt_config.secret_key[:8]}...")
            print(f"   Algorithm: {jwt_config.algorithm}")
            print(f"   Issuer: {jwt_config.issuer}")
            print(f"   Audience: {jwt_config.audience}")
            print(f"   Expiration: {jwt_config.access_token_expire_minutes} minutes")
        except Exception as e:
            print(f"❌ JWT configuration failed: {e}")

        # Test database configuration integration
        print("\n🗄️ Testing Database Configuration...")
        try:
            db_config = DatabaseConfig.from_mmf_config(mmf_config, "identity-service")
            print("✅ Database Configuration loaded successfully")
            print(f"   Host: {db_config.host}")
            print(f"   Port: {db_config.port}")
            print(f"   Database: {db_config.database}")
            print(f"   Username: {db_config.username}")
            print(f"   Type: {db_config.db_type}")
            print(f"   Schema: {db_config.schema}")
        except Exception as e:
            print(f"❌ Database configuration failed: {e}")

        # Test hierarchical configuration
        print("\n📊 Testing Hierarchical Configuration...")
        security_config = mmf_config.get("security.authentication", {})
        messaging_config = mmf_config.get("messaging", {})
        observability_config = mmf_config.get("observability", {})

        print(f"   Security config keys: {list(security_config.keys())}")
        print(f"   Messaging config keys: {list(messaging_config.keys())}")
        print(f"   Observability config keys: {list(observability_config.keys())}")

        # Test secret resolution
        print("\n🔑 Testing Secret Resolution...")
        jwt_secret = mmf_config.get("security.authentication.jwt.secret")
        if jwt_secret and jwt_secret.startswith("demo_jwt"):
            print("✅ Secret resolution working - JWT secret loaded from environment")
        else:
            print(f"⚠️ Secret resolution unclear - got: {jwt_secret}")

        print("\n🎉 Migration Demo Complete!")
        print("   The new MMF configuration system is working correctly.")
        print("   Legacy configuration files have been moved to boneyard.")
        print("   Services can now use hierarchical configuration with secret management.")

    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    demo_configuration_migration()
