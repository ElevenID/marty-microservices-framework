# Old Database Framework - Moved to Boneyard

**Date Moved**: November 7, 2025
**Migration Status**: ✅ COMPLETE

## What Was Moved

This directory contains the old database framework that was migrated to the new hexagonal architecture at `mmf_new/core/`.

### Files Moved:
- `__init__.py` - Database framework exports and API
- `config.py` - Database configuration classes
- `manager.py` - Database manager implementation
- `transaction.py` - Transaction management utilities
- `utilities.py` - Database utility functions
- `sql_generator.py` - SQL generation utilities

### Migration Destination:

| Old File | New Location | Layer |
|----------|-------------|-------|
| `config.py` | `mmf_new/core/application/database.py` | Application |
| `manager.py` | `mmf_new/core/infrastructure/database.py` + `mmf_new/core/domain/database.py` | Infrastructure + Domain |
| `transaction.py` | `mmf_new/core/application/transaction.py` | Application |
| `utilities.py` | `mmf_new/core/application/utilities.py` | Application |
| `sql_generator.py` | `mmf_new/core/application/sql.py` | Application |

## Why Moved

1. **Architecture Migration**: Migrated to hexagonal architecture with proper separation of concerns
2. **Better Structure**: Split into domain, application, and infrastructure layers
3. **Improved Testability**: Domain logic isolated from infrastructure concerns
4. **Enhanced Maintainability**: Clear dependency direction and single responsibility

## Migration Notes

- ✅ All functionality has been migrated with feature parity
- ✅ Backwards compatibility maintained through updated imports
- ✅ Error handling improved with centralized domain errors
- ✅ Enhanced with better async/await support
- ✅ Repository patterns moved to new structure

## Import Updates Required

If any code still imports from the old location, update imports:

```python
# OLD
from marty_msf.framework.database import DatabaseManager, DatabaseConfig

# NEW
from mmf_new.core.infrastructure.database import DatabaseManager
from mmf_new.core.application.database import DatabaseConfig
```

## Status

These files are safe to delete after confirming no remaining imports reference the old paths.

See `DATABASE_MIGRATION_SUMMARY.md` and `MIGRATION_COVERAGE_ANALYSIS.md` for complete migration details.
