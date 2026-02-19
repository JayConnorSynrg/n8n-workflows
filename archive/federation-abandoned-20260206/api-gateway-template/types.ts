// Federation API Gateway - Type Definitions
// Version: 1.0.0

import { Request, Response, NextFunction } from 'express';

// =============================================================================
// REQUEST EXTENSIONS
// =============================================================================

export interface AuthenticatedRequest extends Request {
  user: JWTUser;
  department_id: string;
}

export interface JWTUser {
  id: string;
  department: string;
  role: 'user' | 'admin';
  permissions: string[];
}

// =============================================================================
// JWT TOKEN
// =============================================================================

export interface JWTPayload {
  userId: string;
  department: string;
  role: 'user' | 'admin';
  permissions: string[];
  exp: number;
  iat: number;
}

export interface TokenGenerationOptions {
  userId: string;
  department: string;
  role: 'user' | 'admin';
  permissions: string[];
  expiresIn?: number; // seconds, default 86400 (24 hours)
}

// =============================================================================
// CROSS-DEPARTMENT QUERY
// =============================================================================

export interface CrossDeptQueryRequest {
  targetDepartment: string;
  query: string;
  reason: string;
  resourceType?: string;
}

export interface CrossDeptQueryParams {
  source: string;
  target: string;
  query: string;
  reason: string;
  userId: string;
  resourceType?: string;
}

export interface CrossDeptQueryResult {
  allowed: boolean;
  auditLogId: string;
  results: any[];
  count: number;
  executionTimeMs: number;
}

// =============================================================================
// PERMISSIONS
// =============================================================================

export interface PermissionCheck {
  allowed: boolean;
  reason?: string;
}

export interface CrossDeptPermission {
  id: string;
  source_department_id: string;
  target_department_id: string;
  permission_type: 'read' | 'search' | 'aggregate';
  resource_type: string;
  enabled: boolean;
  granted_by: string;
  granted_at: Date;
  expires_at?: Date;
}

// =============================================================================
// AUDIT LOGGING
// =============================================================================

export interface AuditLogEntry {
  id: string;
  timestamp: Date;
  sourceDepartment: string;
  targetDepartment: string;
  userId: string;
  operation: 'query' | 'access';
  query: string;
  reason: string;
  allowed: boolean;
  resultCount?: number;
  executionTimeMs: number;
  ipAddress: string;
  userAgent?: string;
}

export interface AuditLogFilter {
  department?: string;
  startDate?: Date;
  endDate?: Date;
  userId?: string;
  allowed?: boolean;
  limit?: number;
}

// =============================================================================
// RATE LIMITING
// =============================================================================

export interface RateLimitConfig {
  windowMs: number;
  max: number;
  keyGenerator: (req: Request) => string;
  message: string | object;
}

// =============================================================================
// QUERY VALIDATION
// =============================================================================

export interface QueryValidationResult {
  valid: boolean;
  error?: string;
}

export interface QueryExecutionResult {
  rows: any[];
  rowCount: number;
  duration: number;
}

// =============================================================================
// ERROR RESPONSES
// =============================================================================

export interface ErrorResponse {
  error: string;
  message?: string;
  code?: string;
  details?: any;
}

export interface SuccessResponse<T = any> {
  success: true;
  data: T;
  meta?: {
    timestamp: string;
    requestId?: string;
  };
}

// =============================================================================
// HEALTH CHECK
// =============================================================================

export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  services: {
    database: 'connected' | 'disconnected';
    redis: 'connected' | 'disconnected';
  };
}

// =============================================================================
// DATABASE CONNECTION
// =============================================================================

export interface DatabaseConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl?: boolean;
  max?: number;
  idleTimeoutMillis?: number;
  connectionTimeoutMillis?: number;
}

// =============================================================================
// MIDDLEWARE
// =============================================================================

export type AsyncRequestHandler = (
  req: Request,
  res: Response,
  next: NextFunction
) => Promise<void>;

export type ErrorHandler = (
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
) => void;
