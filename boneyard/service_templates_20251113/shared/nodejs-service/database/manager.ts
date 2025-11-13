/**
 * Database Manager for {{ service_name }}
 *
 * Implements Marty framework database patterns:
 * - Service-specific database isolation
 * - Connection pooling
 * - Health checks
 * - Transaction management
 * - Graceful shutdown
 */

import { Pool, PoolClient, PoolConfig } from 'pg';
import { logger } from '../config/logger';
import { DatabaseConfig, getDatabaseConfig, validateDatabaseConfig } from './config';

export class DatabaseError extends Error {
  constructor(message: string, public cause?: Error) {
    super(message);
    this.name = 'DatabaseError';
  }
}

export class ConnectionError extends DatabaseError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'ConnectionError';
  }
}

export class DatabaseManager {
  private static instances: Map<string, DatabaseManager> = new Map();

  private pool: Pool | null = null;
  private config: DatabaseConfig;
  private initialized = false;

  private constructor(config: DatabaseConfig) {
    this.config = config;
  }

  /**
   * Get singleton instance for service
   */
  public static getInstance(serviceName: string): DatabaseManager {
    if (!DatabaseManager.instances.has(serviceName)) {
      const config = getDatabaseConfig();
      config.serviceName = serviceName;

      validateDatabaseConfig(config);

      DatabaseManager.instances.set(serviceName, new DatabaseManager(config));
    }

    return DatabaseManager.instances.get(serviceName)!;
  }

  /**
   * Initialize database connection
   */
  public async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    try {
      const poolConfig: PoolConfig = {
        host: this.config.host,
        port: this.config.port,
        database: this.config.database,
        user: this.config.username,
        password: this.config.password,
        ssl: this.config.ssl ? { rejectUnauthorized: false } : false,
        min: this.config.poolMin || 2,
        max: this.config.poolMax || 10,
        connectionTimeoutMillis: this.config.connectionTimeoutMillis || 10000,
        idleTimeoutMillis: this.config.idleTimeoutMillis || 30000,
      };

      this.pool = new Pool(poolConfig);

      // Test connection
      const client = await this.pool.connect();
      await client.query('SELECT 1');
      client.release();

      this.initialized = true;

      logger.info('Database manager initialized', {
        service: this.config.serviceName,
        database: this.config.database,
        host: this.config.host,
        port: this.config.port
      });

    } catch (error) {
      const errorMessage = `Failed to initialize database for service ${this.config.serviceName}`;
      logger.error(errorMessage, { error: error.message });
      throw new ConnectionError(errorMessage, error as Error);
    }
  }

  /**
   * Get database connection from pool
   */
  public async getConnection(): Promise<PoolClient> {
    if (!this.pool || !this.initialized) {
      throw new DatabaseError('Database not initialized');
    }

    try {
      return await this.pool.connect();
    } catch (error) {
      logger.error('Failed to get database connection', { error: error.message });
      throw new ConnectionError('Failed to get database connection', error as Error);
    }
  }

  /**
   * Execute query with automatic connection management
   */
  public async query(text: string, params?: any[]): Promise<any> {
    const client = await this.getConnection();

    try {
      logger.debug('Executing database query', { query: text, params });
      const result = await client.query(text, params);
      return result;
    } catch (error) {
      logger.error('Database query failed', {
        query: text,
        params,
        error: error.message
      });
      throw new DatabaseError(`Query failed: ${error.message}`, error as Error);
    } finally {
      client.release();
    }
  }

  /**
   * Execute queries within a transaction
   */
  public async withTransaction<T>(callback: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.getConnection();

    try {
      await client.query('BEGIN');
      logger.debug('Started database transaction');

      const result = await callback(client);

      await client.query('COMMIT');
      logger.debug('Committed database transaction');

      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error('Rolled back database transaction', { error: error.message });
      throw new DatabaseError(`Transaction failed: ${error.message}`, error as Error);
    } finally {
      client.release();
    }
  }

  /**
   * Perform health check
   */
  public async healthCheck(): Promise<{ status: string; details?: any }> {
    try {
      if (!this.pool || !this.initialized) {
        return { status: 'unhealthy', details: 'Not initialized' };
      }

      const client = await this.pool.connect();
      try {
        const result = await client.query('SELECT 1 as health_check');

        if (result.rows[0]?.health_check === 1) {
          return {
            status: 'healthy',
            details: {
              totalCount: this.pool.totalCount,
              idleCount: this.pool.idleCount,
              waitingCount: this.pool.waitingCount
            }
          };
        } else {
          return { status: 'unhealthy', details: 'Health check query failed' };
        }
      } finally {
        client.release();
      }
    } catch (error) {
      logger.error('Database health check failed', { error: error.message });
      return {
        status: 'unhealthy',
        details: `Health check failed: ${error.message}`
      };
    }
  }

  /**
   * Get connection pool statistics
   */
  public getPoolStats(): any {
    if (!this.pool) {
      return { status: 'not_initialized' };
    }

    return {
      totalCount: this.pool.totalCount,
      idleCount: this.pool.idleCount,
      waitingCount: this.pool.waitingCount
    };
  }

  /**
   * Close all connections and cleanup
   */
  public async close(): Promise<void> {
    if (this.pool) {
      try {
        await this.pool.end();
        this.pool = null;
        this.initialized = false;

        logger.info('Database manager closed', {
          service: this.config.serviceName
        });
      } catch (error) {
        logger.error('Error closing database manager', { error: error.message });
        throw new DatabaseError(`Failed to close database: ${error.message}`, error as Error);
      }
    }
  }

  /**
   * Static method to close all database managers
   */
  public static async closeAll(): Promise<void> {
    const promises = Array.from(DatabaseManager.instances.values()).map(manager =>
      manager.close()
    );

    await Promise.all(promises);
    DatabaseManager.instances.clear();

    logger.info('All database managers closed');
  }

  public get isInitialized(): boolean {
    return this.initialized;
  }

  public get serviceName(): string {
    return this.config.serviceName;
  }
}
