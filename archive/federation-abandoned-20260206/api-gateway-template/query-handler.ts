// Federation API Gateway - Cross-Department Query Handler
// Version: 1.0.0

import { Pool, QueryResult } from 'pg';
import {
  CrossDeptQueryParams,
  CrossDeptQueryResult,
  PermissionCheck,
  QueryValidationResult,
  QueryExecutionResult
} from './types';

// =============================================================================
// DATABASE CONNECTION
// =============================================================================

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : undefined,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
});

// =============================================================================
// CROSS-DEPARTMENT QUERY HANDLER
// =============================================================================

export class CrossDeptQueryHandler {
  /**
   * Execute a cross-department query with permission checks
   */
  async execute(params: CrossDeptQueryParams): Promise<CrossDeptQueryResult> {
    const { source, target, query, reason, userId, resourceType = '*' } = params;

    const startTime = Date.now();

    try {
      // 1. Check if cross-department access is allowed
      const permission = await this.checkPermission(source, target, resourceType);
      if (!permission.allowed) {
        throw new Error(`Cross-department access denied: ${permission.reason}`);
      }

      // 2. Validate query (prevent SQL injection, restrict operations)
      const validation = this.validateQuery(query);
      if (!validation.valid) {
        throw new Error(`Invalid query: ${validation.error}`);
      }

      // 3. Execute query with row-level security
      const result = await this.executeWithRLS(target, query);

      const executionTime = Date.now() - startTime;

      return {
        allowed: true,
        auditLogId: '', // Set by audit logger middleware
        results: result.rows,
        count: result.rowCount,
        executionTimeMs: executionTime
      };
    } catch (error) {
      const executionTime = Date.now() - startTime;

      // Return error result
      return {
        allowed: false,
        auditLogId: '',
        results: [],
        count: 0,
        executionTimeMs: executionTime
      };
    }
  }

  /**
   * Check if source department has permission to access target department
   */
  private async checkPermission(
    source: string,
    target: string,
    resourceType: string = '*'
  ): Promise<PermissionCheck> {
    try {
      const result = await pool.query(
        `
        SELECT
          enabled,
          expires_at
        FROM federation.cross_dept_permissions
        WHERE source_department_id = $1
        AND target_department_id = $2
        AND permission_type = 'read'
        AND (resource_type = $3 OR resource_type = '*')
        AND enabled = true
        ORDER BY
          CASE WHEN resource_type = $3 THEN 1 ELSE 2 END,
          granted_at DESC
        LIMIT 1
        `,
        [source, target, resourceType]
      );

      if (result.rows.length === 0) {
        return {
          allowed: false,
          reason: 'No permission configured for this department pair'
        };
      }

      const permission = result.rows[0];

      // Check if permission has expired
      if (permission.expires_at && new Date(permission.expires_at) < new Date()) {
        return {
          allowed: false,
          reason: 'Permission has expired'
        };
      }

      return { allowed: true };
    } catch (error) {
      console.error('Error checking cross-department permission:', error);
      return {
        allowed: false,
        reason: 'Database error while checking permissions'
      };
    }
  }

  /**
   * Validate query to prevent SQL injection and unsafe operations
   */
  private validateQuery(query: string): QueryValidationResult {
    const trimmedQuery = query.trim();

    // Only allow SELECT queries
    if (!trimmedQuery.toUpperCase().startsWith('SELECT')) {
      return {
        valid: false,
        error: 'Only SELECT queries are allowed'
      };
    }

    // Block dangerous operations
    const blacklist = [
      'DELETE',
      'DROP',
      'TRUNCATE',
      'ALTER',
      'GRANT',
      'REVOKE',
      'INSERT',
      'UPDATE',
      'CREATE',
      'REPLACE',
      'EXEC',
      'EXECUTE',
      'CALL',
      'SET',
      'COMMIT',
      'ROLLBACK',
      'SAVEPOINT',
      'DECLARE'
    ];

    const upperQuery = trimmedQuery.toUpperCase();

    for (const keyword of blacklist) {
      // Use word boundary regex to avoid false positives (e.g., "DELETED" column name)
      const regex = new RegExp(`\\b${keyword}\\b`, 'i');
      if (regex.test(upperQuery)) {
        return {
          valid: false,
          error: `Operation '${keyword}' is not allowed in cross-department queries`
        };
      }
    }

    // Limit query complexity
    if (trimmedQuery.length > 5000) {
      return {
        valid: false,
        error: 'Query exceeds maximum length of 5000 characters'
      };
    }

    // Check for multiple statements (prevent SQL injection)
    if (trimmedQuery.includes(';') && !trimmedQuery.endsWith(';')) {
      return {
        valid: false,
        error: 'Multiple SQL statements are not allowed'
      };
    }

    // Block comments (prevent comment-based injection)
    if (trimmedQuery.includes('--') || trimmedQuery.includes('/*')) {
      return {
        valid: false,
        error: 'SQL comments are not allowed'
      };
    }

    // Validate no schema hopping attempts
    const schemaHoppingPatterns = [
      /information_schema/i,
      /pg_catalog/i,
      /pg_/i,
      /\bpublic\./i
    ];

    for (const pattern of schemaHoppingPatterns) {
      if (pattern.test(trimmedQuery)) {
        return {
          valid: false,
          error: 'Accessing system schemas is not allowed'
        };
      }
    }

    return { valid: true };
  }

  /**
   * Execute query with Row-Level Security enforced
   */
  private async executeWithRLS(
    targetDept: string,
    query: string
  ): Promise<QueryExecutionResult> {
    const client = await pool.connect();

    try {
      const startTime = Date.now();

      // Set PostgreSQL role to cross-department query user
      // This role has SELECT permissions on all tenant schemas but RLS is enforced
      await client.query('SET ROLE cross_dept_query_user');

      // Set search path to target department schema
      const schemaName = `${targetDept}_tenant`;
      await client.query(`SET search_path TO ${client.escapeIdentifier(schemaName)}, public`);

      // Set session variable for RLS policies (source department)
      await client.query(`SET app.source_department = '${targetDept}'`);

      // Execute query (RLS policies will apply)
      const result = await client.query(query);

      const duration = Date.now() - startTime;

      return {
        rows: result.rows,
        rowCount: result.rowCount || 0,
        duration
      };
    } catch (error) {
      console.error('Error executing cross-department query:', error);
      throw new Error(`Query execution failed: ${(error as Error).message}`);
    } finally {
      // Reset role to default
      await client.query('RESET ROLE').catch(() => {});
      client.release();
    }
  }

  /**
   * Get list of tables accessible in a department schema
   */
  async getAccessibleTables(department: string): Promise<string[]> {
    try {
      const schemaName = `${department}_tenant`;

      const result = await pool.query(
        `
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        `,
        [schemaName]
      );

      return result.rows.map(row => row.table_name);
    } catch (error) {
      console.error('Error getting accessible tables:', error);
      return [];
    }
  }

  /**
   * Get schema information for a table
   */
  async getTableSchema(
    department: string,
    tableName: string
  ): Promise<Array<{ column: string; type: string; nullable: boolean }>> {
    try {
      const schemaName = `${department}_tenant`;

      const result = await pool.query(
        `
        SELECT
          column_name as column,
          data_type as type,
          is_nullable = 'YES' as nullable
        FROM information_schema.columns
        WHERE table_schema = $1
        AND table_name = $2
        ORDER BY ordinal_position
        `,
        [schemaName, tableName]
      );

      return result.rows;
    } catch (error) {
      console.error('Error getting table schema:', error);
      return [];
    }
  }

  /**
   * Test connection to database
   */
  async testConnection(): Promise<boolean> {
    try {
      await pool.query('SELECT 1');
      return true;
    } catch (error) {
      console.error('Database connection test failed:', error);
      return false;
    }
  }
}

// Create singleton instance
export const crossDeptQueryHandler = new CrossDeptQueryHandler();

// =============================================================================
// PERMISSION MANAGEMENT
// =============================================================================

/**
 * Grant cross-department permission
 */
export async function grantCrossDeptPermission(options: {
  sourceDepartment: string;
  targetDepartment: string;
  permissionType: 'read' | 'search' | 'aggregate';
  resourceType: string;
  grantedBy: string;
  expiresAt?: Date;
}): Promise<boolean> {
  try {
    await pool.query(
      `
      INSERT INTO federation.cross_dept_permissions (
        source_department_id,
        target_department_id,
        permission_type,
        resource_type,
        granted_by,
        expires_at,
        enabled
      )
      VALUES ($1, $2, $3, $4, $5, $6, true)
      ON CONFLICT (source_department_id, target_department_id, permission_type, resource_type)
      DO UPDATE SET
        enabled = true,
        granted_by = EXCLUDED.granted_by,
        expires_at = EXCLUDED.expires_at,
        granted_at = NOW()
      `,
      [
        options.sourceDepartment,
        options.targetDepartment,
        options.permissionType,
        options.resourceType,
        options.grantedBy,
        options.expiresAt || null
      ]
    );

    console.log(`Permission granted: ${options.sourceDepartment} -> ${options.targetDepartment} (${options.resourceType})`);
    return true;
  } catch (error) {
    console.error('Error granting cross-department permission:', error);
    return false;
  }
}

/**
 * Revoke cross-department permission
 */
export async function revokeCrossDeptPermission(options: {
  sourceDepartment: string;
  targetDepartment: string;
  permissionType: 'read' | 'search' | 'aggregate';
  resourceType: string;
}): Promise<boolean> {
  try {
    await pool.query(
      `
      UPDATE federation.cross_dept_permissions
      SET enabled = false
      WHERE source_department_id = $1
      AND target_department_id = $2
      AND permission_type = $3
      AND resource_type = $4
      `,
      [
        options.sourceDepartment,
        options.targetDepartment,
        options.permissionType,
        options.resourceType
      ]
    );

    console.log(`Permission revoked: ${options.sourceDepartment} -> ${options.targetDepartment} (${options.resourceType})`);
    return true;
  } catch (error) {
    console.error('Error revoking cross-department permission:', error);
    return false;
  }
}

/**
 * List all permissions for a department
 */
export async function listDepartmentPermissions(
  department: string
): Promise<Array<{
  target: string;
  permissionType: string;
  resourceType: string;
  grantedBy: string;
  grantedAt: Date;
  expiresAt?: Date;
}>> {
  try {
    const result = await pool.query(
      `
      SELECT
        target_department_id as target,
        permission_type as "permissionType",
        resource_type as "resourceType",
        granted_by as "grantedBy",
        granted_at as "grantedAt",
        expires_at as "expiresAt"
      FROM federation.cross_dept_permissions
      WHERE source_department_id = $1
      AND enabled = true
      ORDER BY granted_at DESC
      `,
      [department]
    );

    return result.rows;
  } catch (error) {
    console.error('Error listing department permissions:', error);
    return [];
  }
}
