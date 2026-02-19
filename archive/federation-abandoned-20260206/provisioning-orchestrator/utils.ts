/**
 * Utility functions for the provisioning orchestrator
 */

import { v4 as uuidv4 } from 'uuid';
import { DepartmentConfig } from './types';

/**
 * Generate a unique provisioning ID
 */
export function generateProvisioningId(): string {
  return uuidv4();
}

/**
 * Generate a tenant schema name from department ID
 */
export function generateTenantSchema(departmentId: string): string {
  return `${departmentId}_tenant`.toLowerCase().replace(/[^a-z0-9_]/g, '_');
}

/**
 * Validate department ID format
 */
export function isValidDepartmentId(departmentId: string): boolean {
  return /^[a-z0-9_-]+$/.test(departmentId);
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Sanitize department name for use in external systems
 */
export function sanitizeDepartmentName(name: string): string {
  return name.replace(/[^a-zA-Z0-9\s-]/g, '').trim();
}

/**
 * Generate Railway project name
 */
export function generateRailwayProjectName(departmentId: string): string {
  return `aio-${departmentId}-prod`;
}

/**
 * Generate n8n workflow name
 */
export function generateWorkflowName(departmentName: string, toolName: string): string {
  return `${departmentName} - ${toolName}`;
}

/**
 * Calculate timeout for operation
 */
export function calculateTimeout(baseTimeoutMs: number, retryCount: number): number {
  return baseTimeoutMs * (1 + retryCount * 0.5);
}

/**
 * Sleep utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry with exponential backoff
 */
export async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelayMs: number = 1000
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      if (attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt - 1);
        console.log(`Attempt ${attempt} failed. Retrying in ${delay}ms...`);
        await sleep(delay);
      }
    }
  }

  throw lastError || new Error('Operation failed after retries');
}

/**
 * Validate configuration completeness
 */
export function validateConfiguration(config: DepartmentConfig): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!config.departmentId) {
    errors.push('Department ID is required');
  } else if (!isValidDepartmentId(config.departmentId)) {
    errors.push('Department ID must contain only lowercase letters, numbers, hyphens, and underscores');
  }

  if (!config.departmentName || config.departmentName.trim().length === 0) {
    errors.push('Department name is required');
  }

  if (!config.adminEmail) {
    errors.push('Admin email is required');
  } else if (!isValidEmail(config.adminEmail)) {
    errors.push('Admin email format is invalid');
  }

  if (!config.workflows || config.workflows.length === 0) {
    errors.push('At least one workflow must be specified');
  }

  if (!config.dataRetention) {
    errors.push('Data retention policy is required');
  }

  if (!config.region) {
    errors.push('Region is required');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Format log message with timestamp
 */
export function formatLog(message: string, level: 'info' | 'warn' | 'error' = 'info'): string {
  const timestamp = new Date().toISOString();
  return `[${timestamp}] [${level.toUpperCase()}] ${message}`;
}

/**
 * Parse error message safely
 */
export function parseErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message);
  }

  return 'Unknown error occurred';
}

/**
 * Check if error is transient (retryable)
 */
export function isTransientError(error: unknown): boolean {
  const transientPatterns = [
    /timeout/i,
    /connection/i,
    /network/i,
    /ECONNREFUSED/i,
    /ETIMEDOUT/i,
    /rate limit/i
  ];

  const errorMessage = parseErrorMessage(error);
  return transientPatterns.some(pattern => pattern.test(errorMessage));
}

/**
 * Merge environment variables with defaults
 */
export function mergeEnvironmentVariables(
  base: Record<string, string>,
  overrides: Record<string, string>
): Record<string, string> {
  return {
    ...base,
    ...overrides
  };
}

/**
 * Generate dashboard URL
 */
export function generateDashboardUrl(departmentId: string, baseUrl: string = 'https://federation.synrg.io'): string {
  return `${baseUrl}/dashboard/${departmentId}`;
}

/**
 * Validate tool name
 */
export function isValidToolName(toolName: string): boolean {
  const validTools = [
    'email',
    'google_drive',
    'database',
    'vector_store',
    'agent_context',
    'file_download_email'
  ];

  return validTools.includes(toolName);
}

/**
 * Get default enabled tools if not specified
 */
export function getDefaultEnabledTools(): string[] {
  return ['email', 'google_drive', 'database'];
}
