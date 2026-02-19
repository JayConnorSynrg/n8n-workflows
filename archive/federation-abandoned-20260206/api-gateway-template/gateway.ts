// Federation API Gateway - Main Express Application
// Version: 1.0.0

import express, { Request, Response, NextFunction } from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import { authMiddleware, generateToken } from './auth-middleware';
import { rateLimiter, crossDeptRateLimiter, checkRedisHealth } from './rate-limiter';
import { auditMiddleware, auditLogger, createAuditLogsTable } from './audit-logger';
import { crossDeptQueryHandler, grantCrossDeptPermission, revokeCrossDeptPermission, listDepartmentPermissions } from './query-handler';
import { AuthenticatedRequest, CrossDeptQueryRequest, HealthCheckResponse } from './types';

// =============================================================================
// EXPRESS APP SETUP
// =============================================================================

const app = express();

// Trust proxy (for accurate IP addresses behind load balancers)
app.set('trust proxy', 1);

// Security middleware
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
    }
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true
  }
}));

// CORS configuration
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || '*',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Compression
app.use(compression());

// Body parsing
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));

// Request logging
app.use((req: Request, res: Response, next: NextFunction) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`${req.method} ${req.path} - ${res.statusCode} (${duration}ms)`);
  });
  next();
});

// =============================================================================
// PUBLIC ROUTES (NO AUTH)
// =============================================================================

/**
 * Health check endpoint
 */
app.get('/health', async (req: Request, res: Response) => {
  const redisHealthy = await checkRedisHealth();
  const dbHealthy = await crossDeptQueryHandler.testConnection();

  const status = redisHealthy && dbHealthy ? 'healthy' : 'degraded';

  const response: HealthCheckResponse = {
    status,
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version || '1.0.0',
    services: {
      database: dbHealthy ? 'connected' : 'disconnected',
      redis: redisHealthy ? 'connected' : 'disconnected'
    }
  };

  res.status(status === 'healthy' ? 200 : 503).json(response);
});

/**
 * Root endpoint
 */
app.get('/', (req: Request, res: Response) => {
  res.json({
    name: 'Federation API Gateway',
    version: '1.0.0',
    description: 'Secure cross-department query gateway with JWT authentication, rate limiting, and audit logging',
    endpoints: {
      health: '/health',
      crossDeptQuery: 'POST /api/cross-dept/query',
      auditLog: 'GET /api/cross-dept/audit-log/:logId',
      auditLogs: 'GET /api/cross-dept/audit-logs',
      permissions: 'GET /api/cross-dept/permissions',
      grantPermission: 'POST /api/cross-dept/permissions/grant',
      revokePermission: 'POST /api/cross-dept/permissions/revoke'
    }
  });
});

// =============================================================================
// AUTHENTICATED ROUTES
// =============================================================================

// Apply authentication to all /api routes
app.use('/api', authMiddleware);

// Apply general rate limiting to all /api routes
app.use('/api', rateLimiter);

// Apply audit logging to all /api routes
app.use('/api', auditMiddleware);

/**
 * Cross-department query endpoint
 * Executes a read-only query against another department's schema
 */
app.post('/api/cross-dept/query', crossDeptRateLimiter, async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;
    const { targetDepartment, query, reason, resourceType }: CrossDeptQueryRequest = req.body;

    // Validate request body
    if (!targetDepartment || !query || !reason) {
      res.status(400).json({
        error: 'Bad request',
        message: 'Missing required fields: targetDepartment, query, reason'
      });
      return;
    }

    // Prevent self-queries (should use direct connection)
    if (targetDepartment === authReq.user.department) {
      res.status(400).json({
        error: 'Bad request',
        message: 'Cannot query your own department through cross-dept gateway. Use direct connection.'
      });
      return;
    }

    // Execute query with permission checks
    const result = await crossDeptQueryHandler.execute({
      source: authReq.user.department,
      target: targetDepartment,
      query,
      reason,
      userId: authReq.user.id,
      resourceType
    });

    if (!result.allowed) {
      res.status(403).json({
        error: 'Forbidden',
        message: 'Cross-department access denied',
        details: 'Check permissions or contact administrator'
      });
      return;
    }

    // Store result count for audit logging
    res.locals.resultCount = result.count;

    res.json({
      success: true,
      data: {
        results: result.results,
        count: result.count,
        executionTimeMs: result.executionTimeMs,
        targetDepartment
      },
      meta: {
        timestamp: new Date().toISOString()
      }
    });
  } catch (error) {
    console.error('Error executing cross-department query:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: (error as Error).message
    });
  }
});

/**
 * Get audit log by ID
 */
app.get('/api/cross-dept/audit-log/:logId', async (req: Request, res: Response) => {
  try {
    const { logId } = req.params;
    const authReq = req as AuthenticatedRequest;

    const log = await auditLogger.getLog(logId);

    if (!log) {
      res.status(404).json({
        error: 'Not found',
        message: 'Audit log not found'
      });
      return;
    }

    // Only allow viewing logs for own department (unless admin)
    if (
      authReq.user.role !== 'admin' &&
      log.sourceDepartment !== authReq.user.department &&
      log.targetDepartment !== authReq.user.department
    ) {
      res.status(403).json({
        error: 'Forbidden',
        message: 'You can only view audit logs for your department'
      });
      return;
    }

    res.json({
      success: true,
      data: log
    });
  } catch (error) {
    console.error('Error retrieving audit log:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to retrieve audit log'
    });
  }
});

/**
 * Get audit logs for department
 */
app.get('/api/cross-dept/audit-logs', async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;
    const {
      startDate,
      endDate,
      userId,
      allowed,
      limit
    } = req.query;

    const logs = await auditLogger.getLogsForDepartment(
      authReq.user.department,
      {
        startDate: startDate ? new Date(startDate as string) : undefined,
        endDate: endDate ? new Date(endDate as string) : undefined,
        userId: userId as string,
        allowed: allowed === 'true' ? true : allowed === 'false' ? false : undefined,
        limit: limit ? parseInt(limit as string) : 1000
      }
    );

    res.json({
      success: true,
      data: logs,
      meta: {
        count: logs.length,
        department: authReq.user.department
      }
    });
  } catch (error) {
    console.error('Error retrieving audit logs:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to retrieve audit logs'
    });
  }
});

/**
 * Get department statistics
 */
app.get('/api/cross-dept/stats', async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;
    const { startDate, endDate } = req.query;

    const start = startDate ? new Date(startDate as string) : new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const end = endDate ? new Date(endDate as string) : new Date();

    const stats = await auditLogger.getDepartmentStats(
      authReq.user.department,
      start,
      end
    );

    res.json({
      success: true,
      data: stats,
      meta: {
        department: authReq.user.department,
        startDate: start.toISOString(),
        endDate: end.toISOString()
      }
    });
  } catch (error) {
    console.error('Error retrieving department statistics:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to retrieve statistics'
    });
  }
});

/**
 * List permissions for department
 */
app.get('/api/cross-dept/permissions', async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;

    const permissions = await listDepartmentPermissions(authReq.user.department);

    res.json({
      success: true,
      data: permissions,
      meta: {
        count: permissions.length,
        department: authReq.user.department
      }
    });
  } catch (error) {
    console.error('Error listing permissions:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to list permissions'
    });
  }
});

/**
 * Grant cross-department permission (admin only)
 */
app.post('/api/cross-dept/permissions/grant', async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;

    // Admin only
    if (authReq.user.role !== 'admin') {
      res.status(403).json({
        error: 'Forbidden',
        message: 'Admin access required'
      });
      return;
    }

    const {
      sourceDepartment,
      targetDepartment,
      permissionType,
      resourceType,
      expiresAt
    } = req.body;

    if (!sourceDepartment || !targetDepartment || !permissionType || !resourceType) {
      res.status(400).json({
        error: 'Bad request',
        message: 'Missing required fields'
      });
      return;
    }

    const success = await grantCrossDeptPermission({
      sourceDepartment,
      targetDepartment,
      permissionType,
      resourceType,
      grantedBy: authReq.user.id,
      expiresAt: expiresAt ? new Date(expiresAt) : undefined
    });

    if (success) {
      res.json({
        success: true,
        message: 'Permission granted successfully'
      });
    } else {
      res.status(500).json({
        error: 'Internal server error',
        message: 'Failed to grant permission'
      });
    }
  } catch (error) {
    console.error('Error granting permission:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to grant permission'
    });
  }
});

/**
 * Revoke cross-department permission (admin only)
 */
app.post('/api/cross-dept/permissions/revoke', async (req: Request, res: Response) => {
  try {
    const authReq = req as AuthenticatedRequest;

    // Admin only
    if (authReq.user.role !== 'admin') {
      res.status(403).json({
        error: 'Forbidden',
        message: 'Admin access required'
      });
      return;
    }

    const {
      sourceDepartment,
      targetDepartment,
      permissionType,
      resourceType
    } = req.body;

    if (!sourceDepartment || !targetDepartment || !permissionType || !resourceType) {
      res.status(400).json({
        error: 'Bad request',
        message: 'Missing required fields'
      });
      return;
    }

    const success = await revokeCrossDeptPermission({
      sourceDepartment,
      targetDepartment,
      permissionType,
      resourceType
    });

    if (success) {
      res.json({
        success: true,
        message: 'Permission revoked successfully'
      });
    } else {
      res.status(500).json({
        error: 'Internal server error',
        message: 'Failed to revoke permission'
      });
    }
  } catch (error) {
    console.error('Error revoking permission:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to revoke permission'
    });
  }
});

/**
 * Get accessible tables in target department
 */
app.get('/api/cross-dept/tables/:department', async (req: Request, res: Response) => {
  try {
    const { department } = req.params;
    const tables = await crossDeptQueryHandler.getAccessibleTables(department);

    res.json({
      success: true,
      data: tables,
      meta: {
        count: tables.length,
        department
      }
    });
  } catch (error) {
    console.error('Error getting accessible tables:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to get accessible tables'
    });
  }
});

/**
 * Get table schema
 */
app.get('/api/cross-dept/schema/:department/:table', async (req: Request, res: Response) => {
  try {
    const { department, table } = req.params;
    const schema = await crossDeptQueryHandler.getTableSchema(department, table);

    res.json({
      success: true,
      data: schema,
      meta: {
        department,
        table
      }
    });
  } catch (error) {
    console.error('Error getting table schema:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to get table schema'
    });
  }
});

// =============================================================================
// ERROR HANDLING
// =============================================================================

/**
 * 404 handler
 */
app.use((req: Request, res: Response) => {
  res.status(404).json({
    error: 'Not found',
    message: 'The requested endpoint does not exist'
  });
});

/**
 * Global error handler
 */
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'An unexpected error occurred'
  });
});

// =============================================================================
// SERVER STARTUP
// =============================================================================

const PORT = parseInt(process.env.PORT || '3000');

async function startServer() {
  try {
    // Create audit logs table if it doesn't exist
    await createAuditLogsTable();
    console.log('Database tables initialized');

    // Test Redis connection
    const redisHealthy = await checkRedisHealth();
    if (!redisHealthy) {
      console.warn('WARNING: Redis is not connected. Rate limiting may not work properly.');
    }

    // Test database connection
    const dbHealthy = await crossDeptQueryHandler.testConnection();
    if (!dbHealthy) {
      throw new Error('Database connection failed');
    }

    app.listen(PORT, () => {
      console.log(`
╔═══════════════════════════════════════════════════════════╗
║         Federation API Gateway                            ║
║         Version: 1.0.0                                    ║
╠═══════════════════════════════════════════════════════════╣
║  Status: Running                                          ║
║  Port: ${PORT.toString().padEnd(51)}║
║  Environment: ${(process.env.NODE_ENV || 'development').padEnd(44)}║
╠═══════════════════════════════════════════════════════════╣
║  Features:                                                ║
║    ✓ JWT Authentication                                   ║
║    ✓ Rate Limiting (Redis)                                ║
║    ✓ Audit Logging (PostgreSQL)                           ║
║    ✓ Cross-Department Query Engine                        ║
║    ✓ Permission Management                                ║
╚═══════════════════════════════════════════════════════════╝
      `);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Start server if this file is executed directly
if (require.main === module) {
  startServer();
}

export default app;
