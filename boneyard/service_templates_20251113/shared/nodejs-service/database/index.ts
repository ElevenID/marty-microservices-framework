/**
 * Database Package Index
 *
 * Exports all database-related functionality following Marty framework patterns.
 */

export { DatabaseManager, DatabaseError, ConnectionError } from './manager';
export { DatabaseConfig, getDatabaseConfig, validateDatabaseConfig, DatabaseType } from './config';
export {
  BaseRepository,
  NotFoundError,
  ConflictError,
  ValidationError,
  createRepository
} from './repository';

// Re-export common types
export type { RepositoryError } from './repository';
