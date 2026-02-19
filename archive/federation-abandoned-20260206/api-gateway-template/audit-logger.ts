// Federation API Gateway - Audit Logging
// Version: 1.0.0

import { Pool, QueryResult } from 'pg';
import { Request, Response, NextFunction } from 'express';
import { AuditLogEntry, AuditLogFilter, AuthenticatedRequest } from './types';

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

pool.on('error', (err) => {
  console.error('Unexpected database error:', err);
});

// =============================================================================
// AUDIT LOGGER CLASS
// =============================================================================

export class AuditLogger {
  /**
   * Log an audit entry to the database
   */
  async log(entry: Omit<AuditLogEntry, 'id'>): Promise<string> {
    // Generate audit log ID
    const auditId = `audit_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

    try {
      await pool.query(
        `
        INSERT INTO federation.audit_logs (
          id, timestamp, source_dept, target_dept, user_id,
          operation, query, reason, allowed, result_count,
          execution_time_ms, ip_address, user_agent
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        `,
        [
          auditId,
          entry.timestamp,
          entry.sourceDepartment,
          entry.targetDepartment,
          entry.userId,
          entry.operation,
          entry.query,
          entry.reason,
          entry.allowed,
          entry.resultCount || 0,
          entry.executionTimeMs,
          entry.ipAddress,
          entry.userAgent || null
        ]
      );

      return auditId;
    } catch (error) {
      console.error('Error logging audit entry:', error);
      throw new Error('Failed to log audit entry');
    }
  }

  /**
   * Get a specific audit log entry by ID
   */
  async getLog(auditId: string): Promise<AuditLogEntry | null> {
    try {
      const result = await pool.query(
        `
        SELECT
          id,
          timestamp,
          source_dept as "sourceDepartment",
          target_dept as "targetDepartment",
          user_id as "userId",
          operation,
          query,
          reason,
          allowed,
          result_count as "resultCount",
          execution_time_ms as "executionTimeMs",
          ip_address as "ipAddress",
          user_agent as "userAgent"
        FROM federation.audit_logs
        WHERE id = $1
        `,
        [auditId]
      );

      if (result.rows.length === 0) {
        return null;
      }

      return result.rows[0] as AuditLogEntry;
    } catch (error) {
      console.error('Error retrieving audit log:', error);
      throw new Error('Failed to retrieve audit log');
    }
  }

  /**
   * Get audit logs for a department with filtering
   */
  async getLogsForDepartment(
    department: string,
    options: AuditLogFilter = {}
  ): Promise<AuditLogEntry[]> {
    const {
      startDate,
      endDate,
      userId,
      allowed,
      limit = 1000
    } = options;

    try {
      let query = `
        SELECT
          id,
          timestamp,
          source_dept as "sourceDepartment",
          target_dept as "targetDepartment",
          user_id as "userId",
          operation,
          query,
          reason,
          allowed,
          result_count as "resultCount",
          execution_time_ms as "executionTimeMs",
          ip_address as "ipAddress",
          user_agent as "userAgent"
        FROM federation.audit_logs
        WHERE (source_dept = $1 OR target_dept = $1)
      `;

      const params: any[] = [department];
      let paramIndex = 2;

      if (startDate) {
        query += ` AND timestamp >= $${paramIndex}`;
        params.push(startDate);
        paramIndex++;
      }

      if (endDate) {
        query += ` AND timestamp <= $${paramIndex}`;
        params.push(endDate);
        paramIndex++;
      }

      if (userId) {
        query += ` AND user_id = $${paramIndex}`;
        params.push(userId);
        paramIndex++;
      }

      if (allowed !== undefined) {
        query += ` AND allowed = $${paramIndex}`;
        params.push(allowed);
        paramIndex++;
      }

      query += ` ORDER BY timestamp DESC LIMIT $${paramIndex}`;
      params.push(limit);

      const result = await pool.query(query, params);
      return result.rows as AuditLogEntry[];
    } catch (error) {
      console.error('Error retrieving department audit logs:', error);
      throw new Error('Failed to retrieve audit logs');
    }
  }

  /**
   * Get audit statistics for a department
   */
  async getDepartmentStats(
    department: string,
    startDate: Date,
    endDate: Date
  ): Promise<{
    totalQueries: number;
    successfulQueries: number;
    failedQueries: number;
    averageExecutionTime: number;
    topTargetDepartments: { department: string; count: number }[];
  }> {
    try {
      // Get total and success/failure counts
      const countResult = await pool.query(
        `
        SELECT
          COUNT(*) as total,
          COUNT(*) FILTER (WHERE allowed = true) as successful,
          COUNT(*) FILTER (WHERE allowed = false) as failed,
          AVG(execution_time_ms) as avg_execution_time
        FROM federation.audit_logs
        WHERE source_dept = $1
        AND timestamp BETWEEN $2 AND $3
        `,
        [department, startDate, endDate]
      );

      // Get top target departments
      const topTargetsResult = await pool.query(
        `
        SELECT
          target_dept as department,
          COUNT(*) as count
        FROM federation.audit_logs
        WHERE source_dept = $1
        AND timestamp BETWEEN $2 AND $3
        GROUP BY target_dept
        ORDER BY count DESC
        LIMIT 5
        `,
        [department, startDate, endDate]
      );

      return {
        totalQueries: parseInt(countResult.rows[0].total),
        successfulQueries: parseInt(countResult.rows[0].successful),
        failedQueries: parseInt(countResult.rows[0].failed),
        averageExecutionTime: Math.round(parseFloat(countResult.rows[0].avg_execution_time) || 0),
        topTargetDepartments: topTargetsResult.rows
      };
    } catch (error) {
      console.error('Error retrieving department statistics:', error);
      throw new Error('Failed to retrieve department statistics');
    }
  }

  /**
   * Search audit logs by query content
   */
  async searchLogs(
    searchTerm: string,
    department?: string,
    limit: number = 100
  ): Promise<AuditLogEntry[]> {
    try {
      let query = `
        SELECT
          id,
          timestamp,
          source_dept as "sourceDepartment",
          target_dept as "targetDepartment",
          user_id as "userId",
          operation,
          query,
          reason,
          allowed,
          result_count as "resultCount",
          execution_time_ms as "executionTimeMs",
          ip_address as "ipAddress",
          user_agent as "userAgent"
        FROM federation.audit_logs
        WHERE (query ILIKE $1 OR reason ILIKE $1)
      `;

      const params: any[] = [`%${searchTerm}%`];

      if (department) {
        query += ` AND (source_dept = $2 OR target_dept = $2)`;
        params.push(department);
      }

      query += ` ORDER BY timestamp DESC LIMIT $${params.length + 1}`;
      params.push(limit);

      const result = await pool.query(query, params);
      return result.rows as AuditLogEntry[];
    } catch (error) {
      console.error('Error searching audit logs:', error);
      throw new Error('Failed to search audit logs');
    }
  }
}

// Create singleton instance
export const auditLogger = new AuditLogger();

// =============================================================================
// AUDIT MIDDLEWARE
// =============================================================================

/**
 * Express middleware to automatically log cross-department queries
 */
export function auditMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const startTime = Date.now();
  const authReq = req as AuthenticatedRequest;

  // Capture original end function
  const originalEnd = res.end;

  // Override end function to log after response
  res.end = function(chunk?: any, encoding?: any, callback?: any): Response {
    // Restore original end function
    res.end = originalEnd;

    // Call original end function
    const result = res.end(chunk, encoding, callback);

    // Log audit entry asynchronously (don't block response)
    if (req.path.startsWith('/api/cross-dept/query')) {
      const executionTime = Date.now() - startTime;

      auditLogger.log({
        timestamp: new Date(),
        sourceDepartment: authReq.user?.department || 'unknown',
        targetDepartment: req.body?.targetDepartment || 'unknown',
        userId: authReq.user?.id || 'unknown',
        operation: 'query',
        query: req.body?.query || '',
        reason: req.body?.reason || '',
        allowed: res.statusCode === 200,
        resultCount: (res as any).locals?.resultCount || 0,
        executionTimeMs: executionTime,
        ipAddress: req.ip || req.headers['x-forwarded-for'] as string || 'unknown',
        userAgent: req.headers['user-agent']
      }).catch(error => {
        console.error('Failed to log audit entry:', error);
      });
    }

    return result;
  };

  next();
}

// =============================================================================
// DATABASE SETUP
// =============================================================================

/**
 * Create audit logs table if it doesn't exist
 */
export async function createAuditLogsTable(): Promise<void> {
  try {
    await pool.query(`
      CREATE SCHEMA IF NOT EXISTS federation;

      CREATE TABLE IF NOT EXISTS federation.audit_logs (
        id VARCHAR(50) PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        source_dept VARCHAR(100) NOT NULL,
        target_dept VARCHAR(100) NOT NULL,
        user_id VARCHAR(100) NOT NULL,
        operation VARCHAR(20) NOT NULL,
        query TEXT NOT NULL,
        reason TEXT NOT NULL,
        allowed BOOLEAN NOT NULL,
        result_count INTEGER DEFAULT 0,
        execution_time_ms INTEGER NOT NULL,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_audit_logs_source ON federation.audit_logs(source_dept);
      CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON federation.audit_logs(target_dept);
      CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON federation.audit_logs(timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON federation.audit_logs(user_id);
      CREATE INDEX IF NOT EXISTS idx_audit_logs_allowed ON federation.audit_logs(allowed);
    `);

    console.log('Audit logs table created successfully');
  } catch (error) {
    console.error('Error creating audit logs table:', error);
    throw error;
  }
}

// =============================================================================
// CLEANUP
// =============================================================================

/**
 * Clean up old audit logs (retention policy)
 * Keeps logs for 2 years by default
 */
export async function cleanupOldLogs(retentionDays: number = 730): Promise<number> {
  try {
    const result = await pool.query(
      `
      DELETE FROM federation.audit_logs
      WHERE timestamp < NOW() - INTERVAL '1 day' * $1
      RETURNING id
      `,
      [retentionDays]
    );

    console.log(`Cleaned up ${result.rowCount} old audit logs`);
    return result.rowCount || 0;
  } catch (error) {
    console.error('Error cleaning up old audit logs:', error);
    throw error;
  }
}
