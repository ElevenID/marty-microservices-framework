#!/usr/bin/env python3
"""
Example: Accessing Old Configuration During Migration

This example shows how to access the old configuration files from the boneyard
if needed during the migration process. This should only be used temporarily
during migration - use the new configuration system for all new code.
"""

from pathlib import Path

import yaml

from mmf_new.framework.infrastructure.config import load_service_configuration


def load_old_config_from_boneyard(environment: str = "development") -> dict:
    """
    Load old configuration from boneyard for migration purposes only.

    Args:
        environment: Environment name (development, testing, production)

    Returns:
        Dictionary with old configuration

    Note:
        This is only for migration purposes. Use mmf_new.framework.infrastructure.config
        for all new development.
    """
    boneyard_path = Path("boneyard/config_migration_20251112")

    # Load base config
    base_config_path = boneyard_path / "base.yaml"
    if not base_config_path.exists():
        raise FileNotFoundError(f"Old base config not found: {base_config_path}")

    with open(base_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Load environment-specific config if it exists
    env_config_path = boneyard_path / f"{environment}.yaml"
    if env_config_path.exists():
        with open(env_config_path, encoding="utf-8") as f:
            env_config = yaml.safe_load(f)

        # Simple merge (new system does deep merge)
        config.update(env_config)

    return config


def compare_old_vs_new_config():
    """Compare old and new configuration systems."""
    print("=== Configuration System Comparison ===")

    try:
        # Load old config from boneyard
        old_config = load_old_config_from_boneyard("development")
        print("✅ Old config loaded from boneyard")
        print(f"Old config keys: {list(old_config.keys())}")

        # Load new config
        new_config = load_service_configuration(
            service_name="identity-service", environment="development"
        )
        print("✅ New config loaded successfully")
        print(f"New config service: {new_config.get_service_name()}")

        print("\n=== Key Differences ===")
        print("Old system: Flat dictionary access")
        print(f"  Database host: {old_config.get('database', {}).get('host', 'N/A')}")

        print("New system: Structured access with type safety")
        print(f"  Database host: {new_config.get('database.host', 'N/A')}")

        print("\nOld system: Mixed service and platform config")
        print("New system: Separated service, platform, and environment configs")

    except Exception as e:
        print(f"❌ Error during comparison: {e}")


def main():
    """Run configuration examples."""
    print("Old Configuration Access Example")
    print("=" * 50)
    print("⚠️  WARNING: This is for migration purposes only!")
    print("    Use mmf_new.framework.infrastructure.config for new development")
    print()

    # Show how to access old config during migration
    try:
        old_config = load_old_config_from_boneyard("development")
        print("Old configuration loaded from boneyard:")
        print(f"  Service name: {old_config.get('service', {}).get('name', 'N/A')}")
        print(f"  Database config: {bool(old_config.get('database'))}")
        print(f"  Security config: {bool(old_config.get('security'))}")

    except Exception as e:
        print(f"❌ Error loading old config: {e}")

    print()
    compare_old_vs_new_config()

    print("\n" + "=" * 50)
    print("Migration complete! Use new configuration system:")
    print("from mmf_new.framework.infrastructure.config import load_service_configuration")


if __name__ == "__main__":
    main()
