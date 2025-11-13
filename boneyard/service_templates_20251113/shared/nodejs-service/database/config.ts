/**
 * Database Configuration for {{ service_name }}
 *
 * Following Marty framework patterns for service-specific database isolation.
 */

export interface DatabaseConfig {
  serviceName: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  ssl?: boolean;
  poolMin?: number;
  poolMax?: number;
  connectionTimeoutMillis?: number;
  idleTimeoutMillis?: number;
}

export interface ConnectionPoolConfig {
  min: number;
  max: number;
  acquireTimeoutMillis: number;
  idleTimeoutMillis: number;
  reapIntervalMillis: number;
  createRetryIntervalMillis: number;
}

export enum DatabaseType {
  POSTGRESQL = 'postgresql',
  MYSQL = 'mysql',
  SQLITE = 'sqlite'
}

/**
 * Get database configuration for the service.
 * Follows Marty's per-service database isolation pattern.
 */
export function getDatabaseConfig(): DatabaseConfig {
  const serviceName = process.env.SERVICE_NAME || '{{ service_name }}';

  // Use service-specific database name following Marty patterns
  const database = process.env.DATABASE_NAME || `${serviceName.replace(/-/g, '_')}_db`;

  return {
    serviceName,
    host: process.env.DATABASE_HOST || 'localhost',
    port: parseInt(process.env.DATABASE_PORT || '5432'),
    database,
    username: process.env.DATABASE_USER || 'postgres',
    password: process.env.DATABASE_PASSWORD || 'password',
    ssl: process.env.DATABASE_SSL === 'true',
    poolMin: parseInt(process.env.DATABASE_POOL_MIN || '2'),
    poolMax: parseInt(process.env.DATABASE_POOL_MAX || '10'),
    connectionTimeoutMillis: parseInt(process.env.DATABASE_CONNECTION_TIMEOUT || '10000'),
    idleTimeoutMillis: parseInt(process.env.DATABASE_IDLE_TIMEOUT || '30000')
  };
}

/**
 * Validate database configuration
 */
export function validateDatabaseConfig(config: DatabaseConfig): void {
  if (!config.serviceName) {
    throw new Error('Service name is required for database configuration');
  }

  if (!config.host) {
    throw new Error('Database host is required');
  }

  if (!config.database) {
    throw new Error('Database name is required');
  }

  if (!config.username) {
    throw new Error('Database username is required');
  }

  // Ensure service-specific database naming
  if (!config.database.includes(config.serviceName.replace(/-/g, '_'))) {
    console.warn(`Database name "${config.database}" does not follow service-specific naming convention for service "${config.serviceName}"`);
  }
}
