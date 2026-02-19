/**
 * REST API Implementation for Provisioning Orchestrator
 *
 * Implements Express.js REST endpoints with validation, auth, and rate limiting
 */

import express, { Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import jwt from 'jsonwebtoken';
import rateLimit from 'express-rate-limit';
import { ProvisioningOrchestrator } from './orchestrator';
import { DepartmentConfig, ProvisioningState } from './types';
import { parseErrorMessage } from './utils';

// Zod schemas for request validation
const ProvisionDepartmentSchema = z.object({
  departmentName: z.string().min(1).max(255),
  departmentId: z.string().regex(/^[a-z0-9_-]+$/, 'Department ID must contain only lowercase letters, numbers, hyphens, and underscores'),
  businessType: z.string().optional(),
  workflows: z.array(z.string()).min(1),
  dataRetention: z.string(),
  region: z.string(),
  resources: z.object({
    cpu: z.string(),
    memory: z.string()
  }).optional(),
  adminEmail: z.string().email(),
  googleWorkspaceDomain: z.string().optional(),
  enabledTools: z.array(z.string()).optional(),
  customConfig: z.record(z.any()).optional()
});

// JWT payload interface
interface JWTPayload {
  departmentId?: string;
  role: 'admin' | 'user';
  email: string;
  exp: number;
}

// Extend Express Request type
declare global {
  namespace Express {
    interface Request {
      departmentId?: string;
      role?: 'admin' | 'user';
      email?: string;
    }
  }
}

export class ProvisioningAPI {
  private app: express.Application;
  private orchestrator: ProvisioningOrchestrator;
  private jwtSecret: string;
  private port: number;

  constructor(jwtSecret: string, port: number = 3000) {
    this.app = express();
    this.orchestrator = new ProvisioningOrchestrator();
    this.jwtSecret = jwtSecret;
    this.port = port;

    this.setupMiddleware();
    this.setupRoutes();
    this.setupErrorHandling();
  }

  /**
   * Setup middleware
   */
  private setupMiddleware(): void {
    // Body parsing
    this.app.use(express.json());
    this.app.use(express.urlencoded({ extended: true }));

    // CORS
    this.app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
      res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
      next();
    });

    // Request logging
    this.app.use((req, res, next) => {
      console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
      next();
    });
  }

  /**
   * Setup routes
   */
  private setupRoutes(): void {
    // Health check
    this.app.get('/health', (req, res) => {
      res.json({ status: 'healthy', timestamp: new Date().toISOString() });
    });

    // Provision department
    this.app.post(
      '/api/provision-department',
      this.authenticate.bind(this),
      this.requireAdmin.bind(this),
      this.provisioningRateLimit(),
      this.provisionDepartment.bind(this)
    );

    // Get provisioning status
    this.app.get(
      '/api/provision-status/:provisioningId',
      this.authenticate.bind(this),
      this.getProvisioningStatus.bind(this)
    );

    // Deprovision department
    this.app.delete(
      '/api/deprovision/:departmentId',
      this.authenticate.bind(this),
      this.requireAdmin.bind(this),
      this.deprovisionDepartment.bind(this)
    );

    // List departments
    this.app.get(
      '/api/departments',
      this.authenticate.bind(this),
      this.listDepartments.bind(this)
    );

    // Get department health
    this.app.get(
      '/api/departments/:departmentId/health',
      this.authenticate.bind(this),
      this.getDepartmentHealth.bind(this)
    );
  }

  /**
   * JWT Authentication middleware
   */
  private authenticate(req: Request, res: Response, next: NextFunction): void {
    const authHeader = req.headers.authorization;

    if (!authHeader) {
      res.status(401).json({ error: 'Missing Authorization header' });
      return;
    }

    const token = authHeader.replace('Bearer ', '');

    try {
      const payload = jwt.verify(token, this.jwtSecret) as JWTPayload;
      req.departmentId = payload.departmentId;
      req.role = payload.role;
      req.email = payload.email;
      next();
    } catch (error) {
      res.status(401).json({ error: 'Invalid token' });
    }
  }

  /**
   * Require admin role middleware
   */
  private requireAdmin(req: Request, res: Response, next: NextFunction): void {
    if (req.role !== 'admin') {
      res.status(403).json({ error: 'Admin access required' });
      return;
    }
    next();
  }

  /**
   * Rate limiting for provisioning endpoint
   */
  private provisioningRateLimit() {
    return rateLimit({
      windowMs: 60 * 60 * 1000, // 1 hour
      max: 10, // 10 requests per hour
      message: 'Too many provisioning requests, please try again later',
      standardHeaders: true,
      legacyHeaders: false
    });
  }

  /**
   * POST /api/provision-department
   */
  private async provisionDepartment(req: Request, res: Response): Promise<void> {
    try {
      // Validate request body
      const validatedData = ProvisionDepartmentSchema.parse(req.body);

      const config: DepartmentConfig = {
        departmentName: validatedData.departmentName,
        departmentId: validatedData.departmentId,
        businessType: validatedData.businessType,
        workflows: validatedData.workflows,
        dataRetention: validatedData.dataRetention,
        region: validatedData.region,
        resources: validatedData.resources,
        adminEmail: validatedData.adminEmail,
        googleWorkspaceDomain: validatedData.googleWorkspaceDomain,
        enabledTools: validatedData.enabledTools,
        customConfig: validatedData.customConfig
      };

      // Start provisioning (async)
      const result = await this.orchestrator.provision(config);

      // Return 202 Accepted
      res.status(202).json({
        provisioningId: result.provisioningId,
        departmentId: result.departmentId,
        status: result.status,
        message: result.status === ProvisioningState.COMPLETED
          ? 'Department provisioning completed'
          : 'Department provisioning failed',
        statusUrl: `/api/provision-status/${result.provisioningId}`,
        deploymentUrl: result.deploymentUrl,
        dashboardUrl: result.dashboardUrl,
        errorMessage: result.errorMessage
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        res.status(400).json({
          error: 'Validation error',
          details: error.errors
        });
        return;
      }

      res.status(500).json({
        error: 'Internal server error',
        message: parseErrorMessage(error)
      });
    }
  }

  /**
   * GET /api/provision-status/:provisioningId
   */
  private async getProvisioningStatus(req: Request, res: Response): Promise<void> {
    try {
      const { provisioningId } = req.params;

      const job = this.orchestrator.getProvisioningStatus(provisioningId);

      if (!job) {
        res.status(404).json({ error: 'Provisioning job not found' });
        return;
      }

      res.json({
        provisioningId: job.id,
        departmentId: job.departmentId,
        status: job.status,
        progress: {
          percentage: this.calculateOverallProgress(job),
          database: job.progress.database,
          railway: job.progress.railway,
          docker: job.progress.docker,
          n8n: job.progress.n8n,
          oauth: job.progress.oauth
        },
        currentStep: job.currentStep,
        startedAt: job.startedAt,
        estimatedCompletion: job.estimatedCompletion,
        completedAt: job.completedAt,
        logs: job.logs,
        errorMessage: job.errorMessage
      });
    } catch (error) {
      res.status(500).json({
        error: 'Internal server error',
        message: parseErrorMessage(error)
      });
    }
  }

  /**
   * DELETE /api/deprovision/:departmentId
   */
  private async deprovisionDepartment(req: Request, res: Response): Promise<void> {
    try {
      const { departmentId } = req.params;

      // TODO: Implement deprovisioning logic
      // For now, return mock response

      res.status(202).json({
        departmentId,
        status: 'DEPROVISIONING',
        message: 'Department deprovisioning initiated',
        cleanupProgress: 0
      });
    } catch (error) {
      res.status(500).json({
        error: 'Internal server error',
        message: parseErrorMessage(error)
      });
    }
  }

  /**
   * GET /api/departments
   */
  private async listDepartments(req: Request, res: Response): Promise<void> {
    try {
      // TODO: Query database for departments
      // For now, return mock data

      res.json({
        departments: [],
        total: 0
      });
    } catch (error) {
      res.status(500).json({
        error: 'Internal server error',
        message: parseErrorMessage(error)
      });
    }
  }

  /**
   * GET /api/departments/:departmentId/health
   */
  private async getDepartmentHealth(req: Request, res: Response): Promise<void> {
    try {
      const { departmentId } = req.params;

      // TODO: Implement actual health checks
      // For now, return mock data

      res.json({
        departmentId,
        healthy: true,
        checks: [
          { name: 'railway_agent', healthy: true, latency: 45 },
          { name: 'database_connectivity', healthy: true, latency: 12 },
          { name: 'n8n_workflows', healthy: true, latency: 23 },
          { name: 'oauth_credentials', healthy: true, latency: 8 }
        ],
        lastCheck: new Date().toISOString()
      });
    } catch (error) {
      res.status(500).json({
        error: 'Internal server error',
        message: parseErrorMessage(error)
      });
    }
  }

  /**
   * Calculate overall progress percentage
   */
  private calculateOverallProgress(job: any): number {
    const components = Object.values(job.progress);
    const completed = components.filter(c => c === 'completed').length;
    const total = components.length;

    return Math.round((completed / total) * 100);
  }

  /**
   * Error handling middleware
   */
  private setupErrorHandling(): void {
    // 404 handler
    this.app.use((req, res) => {
      res.status(404).json({ error: 'Not found' });
    });

    // Global error handler
    this.app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
      console.error('Unhandled error:', err);
      res.status(500).json({
        error: 'Internal server error',
        message: process.env.NODE_ENV === 'development' ? err.message : 'An error occurred'
      });
    });
  }

  /**
   * Start the server
   */
  start(): void {
    this.app.listen(this.port, () => {
      console.log(`Provisioning Orchestrator API listening on port ${this.port}`);
    });
  }

  /**
   * Get Express app instance (for testing)
   */
  getApp(): express.Application {
    return this.app;
  }
}

// Export factory function
export function createAPI(jwtSecret: string, port?: number): ProvisioningAPI {
  return new ProvisioningAPI(jwtSecret, port);
}
