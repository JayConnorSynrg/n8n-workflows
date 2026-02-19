// Federation API Gateway - JWT Authentication Middleware
// Version: 1.0.0

import jwt from 'jsonwebtoken';
import { Request, Response, NextFunction } from 'express';
import { JWTPayload, AuthenticatedRequest, TokenGenerationOptions } from './types';

// =============================================================================
// JWT AUTHENTICATION MIDDLEWARE
// =============================================================================

/**
 * Middleware to validate JWT tokens and extract user information
 * Enforces department-scoped authentication
 */
export async function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;

  // Check for Authorization header
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({
      error: 'No authorization token provided',
      message: 'Please provide a valid JWT token in the Authorization header'
    });
    return;
  }

  const token = authHeader.slice(7); // Remove 'Bearer ' prefix

  try {
    // Verify JWT token
    const payload = jwt.verify(
      token,
      process.env.JWT_SECRET || ''
    ) as JWTPayload;

    // Check token expiration (redundant but explicit)
    if (payload.exp < Date.now() / 1000) {
      res.status(401).json({
        error: 'Token expired',
        message: 'Your authentication token has expired. Please login again.'
      });
      return;
    }

    // Validate required fields
    if (!payload.userId || !payload.department || !payload.role) {
      res.status(401).json({
        error: 'Invalid token',
        message: 'Token is missing required fields'
      });
      return;
    }

    // Attach user info to request
    const authenticatedReq = req as AuthenticatedRequest;
    authenticatedReq.user = {
      id: payload.userId,
      department: payload.department,
      role: payload.role,
      permissions: payload.permissions || []
    };
    authenticatedReq.department_id = payload.department;

    next();
  } catch (error) {
    if (error instanceof jwt.TokenExpiredError) {
      res.status(401).json({
        error: 'Token expired',
        message: 'Your authentication token has expired. Please login again.'
      });
      return;
    }

    if (error instanceof jwt.JsonWebTokenError) {
      res.status(401).json({
        error: 'Invalid token',
        message: 'The provided token is invalid or malformed'
      });
      return;
    }

    res.status(500).json({
      error: 'Authentication error',
      message: 'An error occurred while validating your token'
    });
  }
}

// =============================================================================
// TOKEN GENERATION
// =============================================================================

/**
 * Generate a JWT token for a user
 * @param options - Token generation options
 * @returns Signed JWT token
 */
export function generateToken(options: TokenGenerationOptions): string {
  const {
    userId,
    department,
    role,
    permissions,
    expiresIn = 86400 // 24 hours default
  } = options;

  // Validate JWT_SECRET
  const jwtSecret = process.env.JWT_SECRET;
  if (!jwtSecret) {
    throw new Error('JWT_SECRET environment variable is not set');
  }

  if (jwtSecret.length < 32) {
    throw new Error('JWT_SECRET must be at least 32 characters');
  }

  const now = Math.floor(Date.now() / 1000);

  const payload: JWTPayload = {
    userId,
    department,
    role,
    permissions,
    iat: now,
    exp: now + expiresIn
  };

  return jwt.sign(payload, jwtSecret, {
    algorithm: 'HS256'
  });
}

// =============================================================================
// ROLE-BASED ACCESS CONTROL
// =============================================================================

/**
 * Middleware to enforce admin-only access
 */
export function requireAdmin(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authenticatedReq = req as AuthenticatedRequest;

  if (!authenticatedReq.user) {
    res.status(401).json({
      error: 'Unauthorized',
      message: 'Authentication required'
    });
    return;
  }

  if (authenticatedReq.user.role !== 'admin') {
    res.status(403).json({
      error: 'Forbidden',
      message: 'Admin access required'
    });
    return;
  }

  next();
}

/**
 * Middleware to enforce specific permission
 */
export function requirePermission(permission: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const authenticatedReq = req as AuthenticatedRequest;

    if (!authenticatedReq.user) {
      res.status(401).json({
        error: 'Unauthorized',
        message: 'Authentication required'
      });
      return;
    }

    if (!authenticatedReq.user.permissions.includes(permission)) {
      res.status(403).json({
        error: 'Forbidden',
        message: `Permission '${permission}' required`
      });
      return;
    }

    next();
  };
}

// =============================================================================
// TOKEN VALIDATION (UTILITY)
// =============================================================================

/**
 * Validate a JWT token without Express middleware
 * Useful for testing or non-HTTP contexts
 */
export function validateToken(token: string): JWTPayload | null {
  try {
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new Error('JWT_SECRET not set');
    }

    const payload = jwt.verify(token, jwtSecret) as JWTPayload;

    // Check expiration
    if (payload.exp < Date.now() / 1000) {
      return null;
    }

    return payload;
  } catch (error) {
    return null;
  }
}

// =============================================================================
// TOKEN REFRESH
// =============================================================================

/**
 * Refresh an existing token (extend expiration)
 */
export function refreshToken(token: string, expiresIn: number = 86400): string | null {
  const payload = validateToken(token);

  if (!payload) {
    return null;
  }

  // Generate new token with same claims but new expiration
  return generateToken({
    userId: payload.userId,
    department: payload.department,
    role: payload.role,
    permissions: payload.permissions,
    expiresIn
  });
}
