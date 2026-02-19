/**
 * Core Provisioning Orchestrator
 *
 * Coordinates all provisioning steps with error handling and rollback
 */

import { v4 as uuidv4 } from 'uuid';
import {
  DepartmentConfig,
  ProvisioningJob,
  ProvisioningResult,
  ProvisioningState,
  ComponentState,
  DatabaseResult,
  OAuthResult,
  ContainerResult,
  WorkflowResult,
  GatewayResult,
  RollbackContext
} from './types';
import { ProvisioningStateMachine } from './state-machine';
import {
  generateProvisioningId,
  generateTenantSchema,
  generateRailwayProjectName,
  formatLog,
  parseErrorMessage,
  isTransientError,
  retryWithBackoff,
  validateConfiguration
} from './utils';

export class ProvisioningOrchestrator {
  private stateMachine: ProvisioningStateMachine;
  private jobs: Map<string, ProvisioningJob> = new Map();

  constructor() {
    this.stateMachine = new ProvisioningStateMachine();
  }

  /**
   * Main provisioning entry point
   */
  async provision(config: DepartmentConfig): Promise<ProvisioningResult> {
    const provisioningId = generateProvisioningId();
    const startTime = new Date();

    // Create initial provisioning job
    const job: ProvisioningJob = {
      id: provisioningId,
      departmentId: config.departmentId,
      status: ProvisioningState.PENDING,
      progress: {
        database: ComponentState.PENDING,
        railway: ComponentState.PENDING,
        docker: ComponentState.PENDING,
        n8n: ComponentState.PENDING,
        oauth: ComponentState.PENDING
      },
      currentStep: 'Initializing',
      startedAt: startTime,
      estimatedCompletion: new Date(startTime.getTime() + 5 * 60 * 1000), // 5 minutes
      logs: [formatLog(`Provisioning started for department: ${config.departmentName}`)]
    };

    this.jobs.set(provisioningId, job);

    try {
      // Step 1: Validate configuration
      await this.validateConfig(provisioningId, config);

      // Step 2: Create database schema
      const dbResult = await this.createDatabaseSchema(provisioningId, config);

      // Step 3: Create OAuth credentials
      const oauthResult = await this.createOAuthCredentials(provisioningId, config);

      // Step 4: Deploy Docker container
      const containerResult = await this.deployContainer(provisioningId, config, dbResult, oauthResult);

      // Step 5: Deploy n8n workflows
      const workflowResult = await this.deployWorkflows(provisioningId, config, containerResult);

      // Step 6: Configure API Gateway
      const gatewayResult = await this.configureGateway(provisioningId, config, containerResult);

      // Step 7: Validate deployment
      await this.validateDeployment(provisioningId, config, [
        dbResult,
        oauthResult,
        containerResult,
        workflowResult,
        gatewayResult
      ]);

      // Mark as completed
      const completedJob = this.updateJobState(provisioningId, ProvisioningState.COMPLETED);
      completedJob.completedAt = new Date();

      return {
        provisioningId,
        departmentId: config.departmentId,
        status: ProvisioningState.COMPLETED,
        deploymentUrl: containerResult.deploymentUrl,
        dashboardUrl: `https://federation.synrg.io/dashboard/${config.departmentId}`
      };
    } catch (error) {
      const errorMessage = parseErrorMessage(error);
      this.addLog(provisioningId, formatLog(`Provisioning failed: ${errorMessage}`, 'error'));

      // Trigger rollback
      await this.rollback(provisioningId, errorMessage);

      return {
        provisioningId,
        departmentId: config.departmentId,
        status: ProvisioningState.FAILED,
        errorMessage
      };
    }
  }

  /**
   * Step 1: Validate configuration
   */
  private async validateConfig(provisioningId: string, config: DepartmentConfig): Promise<void> {
    this.updateJobState(provisioningId, ProvisioningState.VALIDATING);
    this.addLog(provisioningId, formatLog('Validating configuration'));

    const stepStart = new Date();

    try {
      // Configuration validation
      const validation = validateConfiguration(config);
      if (!validation.valid) {
        throw new Error(`Configuration validation failed: ${validation.errors.join(', ')}`);
      }

      // Check for duplicate department ID (mock - would query database)
      await this.checkDepartmentIdUnique(config.departmentId);

      // Validate tool names
      const enabledTools = config.enabledTools || ['email', 'google_drive', 'database'];
      for (const tool of enabledTools) {
        if (!this.isValidTool(tool)) {
          throw new Error(`Invalid tool specified: ${tool}`);
        }
      }

      // Check timeout
      if (this.stateMachine.hasStepTimedOut(stepStart)) {
        throw new Error('Validation step timed out');
      }

      this.addLog(provisioningId, formatLog('Configuration validated successfully'));
    } catch (error) {
      this.addLog(provisioningId, formatLog(`Validation failed: ${parseErrorMessage(error)}`, 'error'));
      throw error;
    }
  }

  /**
   * Step 2: Create database schema
   */
  private async createDatabaseSchema(
    provisioningId: string,
    config: DepartmentConfig
  ): Promise<DatabaseResult> {
    this.updateJobState(provisioningId, ProvisioningState.CREATING_DATABASE);
    this.updateComponentProgress(provisioningId, 'database', ComponentState.IN_PROGRESS);
    this.addLog(provisioningId, formatLog('Creating database schema'));

    try {
      const tenantSchema = generateTenantSchema(config.departmentId);

      // Call Database Schema Generator (mocked for now)
      const result = await retryWithBackoff(async () => {
        return await this.callDatabaseSchemaGenerator(config, tenantSchema);
      }, 3);

      this.updateComponentProgress(provisioningId, 'database', ComponentState.COMPLETED);
      this.addLog(provisioningId, formatLog(`Database schema created: ${tenantSchema}`));

      return {
        tenantSchema,
        success: true
      };
    } catch (error) {
      this.updateComponentProgress(provisioningId, 'database', ComponentState.FAILED);
      this.addLog(provisioningId, formatLog(`Database creation failed: ${parseErrorMessage(error)}`, 'error'));

      return {
        tenantSchema: '',
        success: false,
        error: parseErrorMessage(error)
      };
    }
  }

  /**
   * Step 3: Create OAuth credentials
   */
  private async createOAuthCredentials(
    provisioningId: string,
    config: DepartmentConfig
  ): Promise<OAuthResult> {
    this.updateJobState(provisioningId, ProvisioningState.CREATING_OAUTH);
    this.updateComponentProgress(provisioningId, 'oauth', ComponentState.IN_PROGRESS);
    this.addLog(provisioningId, formatLog('Creating OAuth credentials'));

    try {
      // Call OAuth Manager (mocked for now)
      const result = await retryWithBackoff(async () => {
        return await this.callOAuthManager(config);
      }, 3);

      this.updateComponentProgress(provisioningId, 'oauth', ComponentState.COMPLETED);
      this.addLog(provisioningId, formatLog(`OAuth credentials created: ${result.clientId}`));

      return {
        ...result,
        success: true
      };
    } catch (error) {
      this.updateComponentProgress(provisioningId, 'oauth', ComponentState.FAILED);
      this.addLog(provisioningId, formatLog(`OAuth creation failed: ${parseErrorMessage(error)}`, 'error'));

      return {
        clientId: '',
        credentialId: '',
        success: false,
        error: parseErrorMessage(error)
      };
    }
  }

  /**
   * Step 4: Deploy Docker container
   */
  private async deployContainer(
    provisioningId: string,
    config: DepartmentConfig,
    dbResult: DatabaseResult,
    oauthResult: OAuthResult
  ): Promise<ContainerResult> {
    this.updateJobState(provisioningId, ProvisioningState.DEPLOYING_CONTAINER);
    this.updateComponentProgress(provisioningId, 'railway', ComponentState.IN_PROGRESS);
    this.updateComponentProgress(provisioningId, 'docker', ComponentState.IN_PROGRESS);
    this.addLog(provisioningId, formatLog('Deploying container to Railway'));

    try {
      const projectName = generateRailwayProjectName(config.departmentId);

      // Call IaC Agent (mocked for now)
      const result = await retryWithBackoff(async () => {
        return await this.callIaCAgent(config, dbResult, oauthResult);
      }, 3);

      this.updateComponentProgress(provisioningId, 'railway', ComponentState.COMPLETED);
      this.updateComponentProgress(provisioningId, 'docker', ComponentState.COMPLETED);
      this.addLog(provisioningId, formatLog(`Container deployed: ${result.deploymentUrl}`));

      return {
        ...result,
        success: true
      };
    } catch (error) {
      this.updateComponentProgress(provisioningId, 'railway', ComponentState.FAILED);
      this.updateComponentProgress(provisioningId, 'docker', ComponentState.FAILED);
      this.addLog(provisioningId, formatLog(`Container deployment failed: ${parseErrorMessage(error)}`, 'error'));

      return {
        projectId: '',
        deploymentUrl: '',
        serviceId: '',
        success: false,
        error: parseErrorMessage(error)
      };
    }
  }

  /**
   * Step 5: Deploy n8n workflows
   */
  private async deployWorkflows(
    provisioningId: string,
    config: DepartmentConfig,
    containerResult: ContainerResult
  ): Promise<WorkflowResult> {
    this.updateJobState(provisioningId, ProvisioningState.DEPLOYING_WORKFLOWS);
    this.updateComponentProgress(provisioningId, 'n8n', ComponentState.IN_PROGRESS);
    this.addLog(provisioningId, formatLog('Deploying n8n workflows'));

    try {
      // Call n8n Template Agent (mocked for now)
      const result = await retryWithBackoff(async () => {
        return await this.callN8nTemplateAgent(config, containerResult);
      }, 3);

      this.updateComponentProgress(provisioningId, 'n8n', ComponentState.COMPLETED);
      this.addLog(provisioningId, formatLog(`Workflows deployed: ${Object.keys(result.workflowIds).length} workflows`));

      return {
        ...result,
        success: true
      };
    } catch (error) {
      this.updateComponentProgress(provisioningId, 'n8n', ComponentState.FAILED);
      this.addLog(provisioningId, formatLog(`Workflow deployment failed: ${parseErrorMessage(error)}`, 'error'));

      return {
        workflowIds: {},
        webhookUrls: {},
        success: false,
        error: parseErrorMessage(error)
      };
    }
  }

  /**
   * Step 6: Configure API Gateway
   */
  private async configureGateway(
    provisioningId: string,
    config: DepartmentConfig,
    containerResult: ContainerResult
  ): Promise<GatewayResult> {
    this.updateJobState(provisioningId, ProvisioningState.CONFIGURING_GATEWAY);
    this.addLog(provisioningId, formatLog('Configuring API gateway'));

    try {
      // Call API Gateway Agent (mocked for now)
      const result = await retryWithBackoff(async () => {
        return await this.callApiGatewayAgent(config, containerResult);
      }, 3);

      this.addLog(provisioningId, formatLog('API gateway configured'));

      return {
        routeConfigured: true,
        success: true
      };
    } catch (error) {
      this.addLog(provisioningId, formatLog(`Gateway configuration failed: ${parseErrorMessage(error)}`, 'error'));

      return {
        routeConfigured: false,
        success: false,
        error: parseErrorMessage(error)
      };
    }
  }

  /**
   * Step 7: Validate deployment
   */
  private async validateDeployment(
    provisioningId: string,
    config: DepartmentConfig,
    results: any[]
  ): Promise<void> {
    this.updateJobState(provisioningId, ProvisioningState.VALIDATING_DEPLOYMENT);
    this.addLog(provisioningId, formatLog('Validating deployment'));

    // Check if any component failed
    const failed = results.some(r => r && !r.success);
    if (failed) {
      throw new Error('One or more components failed deployment');
    }

    // Run health checks (mocked for now)
    const healthChecks = await this.runHealthChecks(config);
    const allHealthy = healthChecks.every(check => check.healthy);

    if (!allHealthy) {
      const failedChecks = healthChecks.filter(c => !c.healthy).map(c => c.name);
      throw new Error(`Health checks failed: ${failedChecks.join(', ')}`);
    }

    this.addLog(provisioningId, formatLog('Deployment validated successfully'));
  }

  /**
   * Rollback on failure
   */
  async rollback(provisioningId: string, error: string): Promise<void> {
    this.addLog(provisioningId, formatLog('Starting rollback', 'warn'));

    const job = this.jobs.get(provisioningId);
    if (!job) {
      throw new Error(`Provisioning job not found: ${provisioningId}`);
    }

    this.updateJobState(provisioningId, ProvisioningState.ROLLING_BACK);

    const rollbackSequence = this.stateMachine.getRollbackSequence(job.status);

    for (const state of rollbackSequence) {
      try {
        await this.rollbackStep(provisioningId, state);
      } catch (rollbackError) {
        this.addLog(
          provisioningId,
          formatLog(`Rollback step failed for ${state}: ${parseErrorMessage(rollbackError)}`, 'error')
        );
      }
    }

    this.updateJobState(provisioningId, ProvisioningState.FAILED);
    const finalJob = this.jobs.get(provisioningId);
    if (finalJob) {
      finalJob.errorMessage = error;
    }

    this.addLog(provisioningId, formatLog('Rollback completed', 'warn'));
  }

  /**
   * Rollback individual step
   */
  private async rollbackStep(provisioningId: string, state: ProvisioningState): Promise<void> {
    this.addLog(provisioningId, formatLog(`Rolling back: ${state}`));

    switch (state) {
      case ProvisioningState.CREATING_DATABASE:
        await this.rollbackDatabase(provisioningId);
        break;
      case ProvisioningState.CREATING_OAUTH:
        await this.rollbackOAuth(provisioningId);
        break;
      case ProvisioningState.DEPLOYING_CONTAINER:
        await this.rollbackContainer(provisioningId);
        break;
      case ProvisioningState.DEPLOYING_WORKFLOWS:
        await this.rollbackWorkflows(provisioningId);
        break;
      case ProvisioningState.CONFIGURING_GATEWAY:
        await this.rollbackGateway(provisioningId);
        break;
    }
  }

  /**
   * Get provisioning status
   */
  getProvisioningStatus(provisioningId: string): ProvisioningJob | undefined {
    return this.jobs.get(provisioningId);
  }

  /**
   * Update job state
   */
  private updateJobState(provisioningId: string, newState: ProvisioningState): ProvisioningJob {
    const job = this.jobs.get(provisioningId);
    if (!job) {
      throw new Error(`Provisioning job not found: ${provisioningId}`);
    }

    const updatedJob = this.stateMachine.transition(job, newState);
    this.jobs.set(provisioningId, updatedJob);

    return updatedJob;
  }

  /**
   * Update component progress
   */
  private updateComponentProgress(
    provisioningId: string,
    component: keyof ProvisioningJob['progress'],
    state: ComponentState
  ): void {
    const job = this.jobs.get(provisioningId);
    if (job) {
      job.progress[component] = state;
    }
  }

  /**
   * Add log entry
   */
  private addLog(provisioningId: string, message: string): void {
    const job = this.jobs.get(provisioningId);
    if (job) {
      job.logs.push(message);
    }
  }

  // Mock component calls (to be replaced with actual implementations)
  private async checkDepartmentIdUnique(departmentId: string): Promise<void> {
    // Mock: would query database
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  private isValidTool(toolName: string): boolean {
    const validTools = ['email', 'google_drive', 'database', 'vector_store', 'agent_context', 'file_download_email'];
    return validTools.includes(toolName);
  }

  private async callDatabaseSchemaGenerator(config: DepartmentConfig, tenantSchema: string): Promise<void> {
    // Mock: would call actual Database Schema Generator
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  private async callOAuthManager(config: DepartmentConfig): Promise<{ clientId: string; credentialId: string }> {
    // Mock: would call actual OAuth Manager
    await new Promise(resolve => setTimeout(resolve, 500));
    return {
      clientId: `client_${uuidv4()}`,
      credentialId: `cred_${uuidv4()}`
    };
  }

  private async callIaCAgent(
    config: DepartmentConfig,
    dbResult: DatabaseResult,
    oauthResult: OAuthResult
  ): Promise<{ projectId: string; deploymentUrl: string; serviceId: string }> {
    // Mock: would call actual IaC Agent
    await new Promise(resolve => setTimeout(resolve, 1000));
    return {
      projectId: `proj_${uuidv4()}`,
      deploymentUrl: `https://aio-${config.departmentId}.railway.app`,
      serviceId: `svc_${uuidv4()}`
    };
  }

  private async callN8nTemplateAgent(
    config: DepartmentConfig,
    containerResult: ContainerResult
  ): Promise<{ workflowIds: Record<string, string>; webhookUrls: Record<string, string> }> {
    // Mock: would call actual n8n Template Agent
    await new Promise(resolve => setTimeout(resolve, 800));
    return {
      workflowIds: {
        email: `wf_${uuidv4()}`,
        google_drive: `wf_${uuidv4()}`
      },
      webhookUrls: {
        email: `https://n8n.cloud/webhook/${config.departmentId}/email`,
        google_drive: `https://n8n.cloud/webhook/${config.departmentId}/drive`
      }
    };
  }

  private async callApiGatewayAgent(config: DepartmentConfig, containerResult: ContainerResult): Promise<void> {
    // Mock: would call actual API Gateway Agent
    await new Promise(resolve => setTimeout(resolve, 300));
  }

  private async runHealthChecks(config: DepartmentConfig): Promise<any[]> {
    // Mock: would run actual health checks
    await new Promise(resolve => setTimeout(resolve, 500));
    return [
      { name: 'database', healthy: true },
      { name: 'railway', healthy: true },
      { name: 'n8n', healthy: true }
    ];
  }

  // Rollback methods (mocked)
  private async rollbackDatabase(provisioningId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 300));
  }

  private async rollbackOAuth(provisioningId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 300));
  }

  private async rollbackContainer(provisioningId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  private async rollbackWorkflows(provisioningId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 400));
  }

  private async rollbackGateway(provisioningId: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 200));
  }
}
