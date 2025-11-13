/**
 * Database Repository Base Class for {{ service_name }}
 *
 * Implements Marty framework repository patterns for clean database access.
 */

import { PoolClient } from 'pg';
import { DatabaseManager, DatabaseError } from './manager';
import { logger } from '../config/logger';

export interface RepositoryError extends Error {
  code?: string;
}

export class NotFoundError extends Error implements RepositoryError {
  code = 'NOT_FOUND';

  constructor(resource: string, id: any) {
    super(`${resource} with id ${id} not found`);
    this.name = 'NotFoundError';
  }
}

export class ConflictError extends Error implements RepositoryError {
  code = 'CONFLICT';

  constructor(message: string) {
    super(message);
    this.name = 'ConflictError';
  }
}

export class ValidationError extends Error implements RepositoryError {
  code = 'VALIDATION_ERROR';

  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

/**
 * Base repository class providing common database operations
 */
export abstract class BaseRepository<T = any> {
  protected dbManager: DatabaseManager;
  protected tableName: string;

  constructor(dbManager: DatabaseManager, tableName: string) {
    this.dbManager = dbManager;
    this.tableName = tableName;
  }

  /**
   * Execute a query with error handling
   */
  protected async executeQuery(query: string, params?: any[]): Promise<any> {
    try {
      return await this.dbManager.query(query, params);
    } catch (error) {
      logger.error('Repository query failed', {
        table: this.tableName,
        query,
        params,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Execute operations within a transaction
   */
  protected async withTransaction<R>(callback: (client: PoolClient) => Promise<R>): Promise<R> {
    return this.dbManager.withTransaction(callback);
  }

  /**
   * Find entity by ID
   */
  public async findById(id: any): Promise<T | null> {
    const query = `SELECT * FROM ${this.tableName} WHERE id = $1`;
    const result = await this.executeQuery(query, [id]);

    return result.rows[0] || null;
  }

  /**
   * Find entity by ID or throw NotFoundError
   */
  public async findByIdOrThrow(id: any): Promise<T> {
    const entity = await this.findById(id);
    if (!entity) {
      throw new NotFoundError(this.tableName, id);
    }
    return entity;
  }

  /**
   * Find all entities with optional filtering
   */
  public async findAll(filters?: Record<string, any>, limit?: number, offset?: number): Promise<T[]> {
    let query = `SELECT * FROM ${this.tableName}`;
    const params: any[] = [];

    if (filters && Object.keys(filters).length > 0) {
      const conditions = Object.keys(filters).map((key, index) => {
        params.push(filters[key]);
        return `${key} = $${index + 1}`;
      });
      query += ` WHERE ${conditions.join(' AND ')}`;
    }

    if (limit) {
      params.push(limit);
      query += ` LIMIT $${params.length}`;
    }

    if (offset) {
      params.push(offset);
      query += ` OFFSET $${params.length}`;
    }

    const result = await this.executeQuery(query, params);
    return result.rows;
  }

  /**
   * Count entities with optional filtering
   */
  public async count(filters?: Record<string, any>): Promise<number> {
    let query = `SELECT COUNT(*) as count FROM ${this.tableName}`;
    const params: any[] = [];

    if (filters && Object.keys(filters).length > 0) {
      const conditions = Object.keys(filters).map((key, index) => {
        params.push(filters[key]);
        return `${key} = $${index + 1}`;
      });
      query += ` WHERE ${conditions.join(' AND ')}`;
    }

    const result = await this.executeQuery(query, params);
    return parseInt(result.rows[0].count);
  }

  /**
   * Create a new entity
   */
  public async create(data: Partial<T>): Promise<T> {
    const fields = Object.keys(data);
    const values = Object.values(data);
    const placeholders = values.map((_, index) => `$${index + 1}`);

    const query = `
      INSERT INTO ${this.tableName} (${fields.join(', ')})
      VALUES (${placeholders.join(', ')})
      RETURNING *
    `;

    const result = await this.executeQuery(query, values);
    return result.rows[0];
  }

  /**
   * Update entity by ID
   */
  public async update(id: any, data: Partial<T>): Promise<T> {
    const fields = Object.keys(data);
    const values = Object.values(data);

    const setClause = fields.map((field, index) => `${field} = $${index + 2}`);

    const query = `
      UPDATE ${this.tableName}
      SET ${setClause.join(', ')}, updated_at = NOW()
      WHERE id = $1
      RETURNING *
    `;

    const result = await this.executeQuery(query, [id, ...values]);

    if (result.rows.length === 0) {
      throw new NotFoundError(this.tableName, id);
    }

    return result.rows[0];
  }

  /**
   * Delete entity by ID
   */
  public async delete(id: any): Promise<void> {
    const query = `DELETE FROM ${this.tableName} WHERE id = $1`;
    const result = await this.executeQuery(query, [id]);

    if (result.rowCount === 0) {
      throw new NotFoundError(this.tableName, id);
    }
  }

  /**
   * Soft delete entity by ID (if table has deleted_at column)
   */
  public async softDelete(id: any): Promise<T> {
    const query = `
      UPDATE ${this.tableName}
      SET deleted_at = NOW()
      WHERE id = $1 AND deleted_at IS NULL
      RETURNING *
    `;

    const result = await this.executeQuery(query, [id]);

    if (result.rows.length === 0) {
      throw new NotFoundError(this.tableName, id);
    }

    return result.rows[0];
  }

  /**
   * Check if entity exists by ID
   */
  public async exists(id: any): Promise<boolean> {
    const query = `SELECT 1 FROM ${this.tableName} WHERE id = $1 LIMIT 1`;
    const result = await this.executeQuery(query, [id]);
    return result.rows.length > 0;
  }
}

/**
 * Factory function to create repository instances
 */
export function createRepository<T>(
  repositoryClass: new (dbManager: DatabaseManager, tableName: string) => BaseRepository<T>,
  tableName: string,
  serviceName: string = '{{ service_name }}'
): BaseRepository<T> {
  const dbManager = DatabaseManager.getInstance(serviceName);
  return new repositoryClass(dbManager, tableName);
}
