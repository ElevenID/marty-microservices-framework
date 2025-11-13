# Boneyard

This directory temporarily holds modules and assets that are slated for removal or major refactoring.

- Move legacy code here before deleting so we can keep it available while porting functionality.
- Nothing inside the boneyard is packaged or imported by the new minimal example.
- Delete entries once their replacements are stable and covered by tests.

> Reminder: keep commits focused when moving files into the boneyard so history stays readable.

## Current Migrations

### Configuration System Migration (2025-11-12)
- **Directory:** `config_migration_20251112/`
- **Status:** Replaced with new hierarchical configuration system
- **New Location:** `mmf_new/config/`
- **Reason:** Old flat configuration structure replaced with hierarchical system supporting service-specific configs, platform configs, and advanced secret management

### Framework Migration (2025-11-06)
- **Directory:** `framework_migration_20251106/`
- **Status:** Replaced with hexagonal architecture
- **New Location:** `mmf_new/core/`

### Database Infrastructure Migration (2024-11-10)  
- **Directory:** `database_infrastructure_migration_20241110/`
- **Status:** Replaced with new database framework
- **New Location:** `mmf_new/core/infrastructure/`

### CLI Generators Migration (2025-11-09)
- **Directory:** `cli_generators_migration_20251109/`
- **Status:** Replaced with new service generation framework
