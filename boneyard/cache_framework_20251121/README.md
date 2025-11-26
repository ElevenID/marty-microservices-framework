# Cache Framework Migration - November 21, 2025

## Migration Summary

**Source**: `src/marty_msf/framework/cache/`
**Destination**: `mmf_new/infrastructure/cache/`
**Migration Type**: Move and Refactor
**Date**: November 21, 2025

## Changes

- Moved legacy cache framework to boneyard.
- Updated `mmf_new/infrastructure/cache/manager.py` to implement `CachePort` (Hexagonal Architecture).
- Defined `CachePort` in `mmf_new/core/application/ports/cache.py`.
- Updated `mmf_new/services/audit_compliance/di_config.py` to use the new `CacheManager`.
- Updated `mmf_new/services/audit_compliance/infrastructure/caching/audit_event_cache.py` to use the new `CacheManager` (disabled incompatible Redis-specific features).

## Notes

- The new `CacheManager` implements `CachePort` interface.
- `CacheConfig` now supports `url` for Redis connection.
- `audit_event_cache.py` had dependencies on Redis-specific features (sorted sets) which are not exposed by the generic `CachePort`. These features have been temporarily disabled.
