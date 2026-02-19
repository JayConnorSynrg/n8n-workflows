// Federation API Gateway - Rate Limiting
// Version: 1.0.0

import rateLimit, { RateLimitRequestHandler } from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';
import Redis from 'ioredis';
import { Request } from 'express';
import { AuthenticatedRequest } from './types';

// =============================================================================
// REDIS CLIENT
// =============================================================================

const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';

export const redis = new Redis(redisUrl, {
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  retryStrategy: (times: number) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  }
});

redis.on('error', (error) => {
  console.error('Redis connection error:', error);
});

redis.on('connect', () => {
  console.log('Redis connected successfully');
});

// =============================================================================
// GENERAL RATE LIMITER
// =============================================================================

/**
 * General rate limiter for all API endpoints
 * Limit: 100 requests per 15 minutes per department
 */
export const rateLimiter: RateLimitRequestHandler = rateLimit({
  store: new RedisStore({
    client: redis,
    prefix: 'rl:general:',
  }),

  // Key function: rate limit per department
  keyGenerator: (req: Request) => {
    const authReq = req as AuthenticatedRequest;
    return `dept:${authReq.user?.department || 'anonymous'}`;
  },

  // 100 requests per 15 minutes per department
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000'), // 15 minutes
  max: parseInt(process.env.RATE_LIMIT_MAX || '100'),

  // Custom message
  message: {
    error: 'Rate limit exceeded',
    message: 'Your department has exceeded the rate limit. Please try again later.',
    retryAfter: 'Check Retry-After header'
  },

  // Standardize headers
  standardHeaders: true, // Return rate limit info in `RateLimit-*` headers
  legacyHeaders: false, // Disable the `X-RateLimit-*` headers

  // Skip failed requests (don't count towards limit)
  skipFailedRequests: false,

  // Skip successful requests
  skipSuccessfulRequests: false,
});

// =============================================================================
// CROSS-DEPARTMENT RATE LIMITER
// =============================================================================

/**
 * Stricter rate limiter for cross-department queries
 * Limit: 10 cross-department queries per hour per department pair
 */
export const crossDeptRateLimiter: RateLimitRequestHandler = rateLimit({
  store: new RedisStore({
    client: redis,
    prefix: 'rl:cross:',
  }),

  // Key function: rate limit per source-target department pair
  keyGenerator: (req: Request) => {
    const authReq = req as AuthenticatedRequest;
    const targetDepartment = req.body?.targetDepartment || 'unknown';
    const sourceDepartment = authReq.user?.department || 'anonymous';
    return `${sourceDepartment}:${targetDepartment}`;
  },

  // 10 cross-department queries per hour
  windowMs: parseInt(process.env.CROSS_DEPT_RATE_LIMIT_WINDOW_MS || '3600000'), // 1 hour
  max: parseInt(process.env.CROSS_DEPT_RATE_LIMIT_MAX || '10'),

  // Custom message
  message: {
    error: 'Cross-department query limit exceeded',
    message: 'Maximum 10 queries per hour per department pair',
    info: 'Contact your administrator to request a limit increase'
  },

  standardHeaders: true,
  legacyHeaders: false,
});

// =============================================================================
// AUTH RATE LIMITER
// =============================================================================

/**
 * Rate limiter for authentication endpoints
 * Prevents brute force attacks
 * Limit: 5 attempts per 15 minutes per IP
 */
export const authRateLimiter: RateLimitRequestHandler = rateLimit({
  store: new RedisStore({
    client: redis,
    prefix: 'rl:auth:',
  }),

  // Key function: rate limit per IP address
  keyGenerator: (req: Request) => {
    // Get IP address (handle proxies)
    const ip = req.ip ||
               req.headers['x-forwarded-for'] as string ||
               req.headers['x-real-ip'] as string ||
               'unknown';
    return `ip:${ip}`;
  },

  // 5 attempts per 15 minutes per IP
  windowMs: 15 * 60 * 1000,
  max: 5,

  message: {
    error: 'Too many authentication attempts',
    message: 'You have made too many failed login attempts. Please try again later.'
  },

  standardHeaders: true,
  legacyHeaders: false,

  // Only count failed requests
  skipSuccessfulRequests: true,
});

// =============================================================================
// CUSTOM RATE LIMITER FACTORY
// =============================================================================

/**
 * Create a custom rate limiter with specific configuration
 */
export function createRateLimiter(options: {
  prefix: string;
  windowMs: number;
  max: number;
  keyGenerator: (req: Request) => string;
  message?: string | object;
}): RateLimitRequestHandler {
  return rateLimit({
    store: new RedisStore({
      client: redis,
      prefix: `rl:${options.prefix}:`,
    }),
    keyGenerator: options.keyGenerator,
    windowMs: options.windowMs,
    max: options.max,
    message: options.message || {
      error: 'Rate limit exceeded',
      message: 'Too many requests'
    },
    standardHeaders: true,
    legacyHeaders: false,
  });
}

// =============================================================================
// RATE LIMIT UTILITIES
// =============================================================================

/**
 * Get current rate limit status for a key
 */
export async function getRateLimitStatus(
  prefix: string,
  key: string
): Promise<{ current: number; limit: number; resetTime: number } | null> {
  try {
    const redisKey = `rl:${prefix}:${key}`;
    const current = await redis.get(redisKey);
    const ttl = await redis.ttl(redisKey);

    if (!current) {
      return null;
    }

    return {
      current: parseInt(current),
      limit: 100, // Would need to be dynamic based on prefix
      resetTime: Date.now() + (ttl * 1000)
    };
  } catch (error) {
    console.error('Error getting rate limit status:', error);
    return null;
  }
}

/**
 * Reset rate limit for a specific key
 * Used for administrative purposes or after resolving false positives
 */
export async function resetRateLimit(
  prefix: string,
  key: string
): Promise<boolean> {
  try {
    const redisKey = `rl:${prefix}:${key}`;
    await redis.del(redisKey);
    console.log(`Rate limit reset for ${redisKey}`);
    return true;
  } catch (error) {
    console.error('Error resetting rate limit:', error);
    return false;
  }
}

/**
 * Get all rate limit keys for a prefix (useful for monitoring)
 */
export async function listRateLimitKeys(prefix: string): Promise<string[]> {
  try {
    const pattern = `rl:${prefix}:*`;
    const keys = await redis.keys(pattern);
    return keys;
  } catch (error) {
    console.error('Error listing rate limit keys:', error);
    return [];
  }
}

// =============================================================================
// HEALTH CHECK
// =============================================================================

/**
 * Check if Redis is connected and healthy
 */
export async function checkRedisHealth(): Promise<boolean> {
  try {
    await redis.ping();
    return true;
  } catch (error) {
    console.error('Redis health check failed:', error);
    return false;
  }
}
