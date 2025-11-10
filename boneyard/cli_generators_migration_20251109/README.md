# CLI and Generators Migration - November 9, 2024

This directory contains the CLI and generator components that have been moved to the boneyard as part of the framework simplification.

## Components Moved

### CLI Components
- `cli/` - Complete CLI package with Click-based command interface
- `test_cli.py` - CLI unit tests

### Generator Components
- `generators/` - Service and project generators
- `test_sql_generator.py` - SQL generator tests

## Reason for Migration

These components were removed as part of the transition to the new `mmf_new` architecture that focuses on:
- Core domain patterns (DDD, CQRS, Event Sourcing)
- Infrastructure abstractions (Repository, Messaging)
- Clean architecture principles

The CLI and generators were primarily focused on scaffolding and code generation, which are not core to the runtime framework functionality.

## Files Modified

The following files were updated to remove references to the moved components:

- `scripts/dev/test_runner.py` - CLI validation disabled
- `.pre-commit-config.yaml` - CLI import check disabled

## Restoration

If these components are needed in the future, they can be restored from this directory. However, they may require updates to work with the new `mmf_new` architecture.

## Related Components

Some related functionality may exist in:
- `tools/scaffolding/` - Project template tools
- `ops/ci-cd/` - CI/CD pipeline tools

These were left in place as they serve different purposes (project setup vs. runtime framework).
