/**
 * N8N Workflow Deployment API
 * Version: 1.0.0
 *
 * Orchestrates template injection, validation, and deployment to n8n.
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { WorkflowInjector } from './injector';
import { DependencyResolver } from './dependency-resolver';
import { TemplateValidator } from './template-validator';
import { N8nClient } from './n8n-client';
import {
  WorkflowTemplate,
  DeploymentConfig,
  DeploymentResult,
  DeployedWorkflow,
  DeploymentError,
  N8nWorkflow,
  TemplateVariables,
  WorkflowDependency
} from './types';

export class N8nDeploymentAPI {
  private injector: WorkflowInjector;
  private resolver: DependencyResolver;
  private validator: TemplateValidator;
  private n8nClient: N8nClient;

  constructor(n8nClient: N8nClient) {
    this.injector = new WorkflowInjector();
    this.resolver = new DependencyResolver();
    this.validator = new TemplateValidator();
    this.n8nClient = n8nClient;
  }

  /**
   * Deploy workflows to a department
   */
  async deployWorkflows(config: DeploymentConfig): Promise<DeploymentResult> {
    const deployedWorkflows: DeployedWorkflow[] = [];
    const errors: DeploymentError[] = [];

    try {
      // 1. Load workflow templates
      console.log(`[${config.department}] Loading ${config.templates.length} workflow templates...`);
      const templates = await this.loadTemplates(config.templates);

      // 2. Resolve dependencies (import order)
      console.log(`[${config.department}] Resolving workflow dependencies...`);
      const dependencies = this.resolver.extractDependenciesFromTemplates(templates);
      const importOrder = this.resolver.resolveDependencies(dependencies);
      console.log(`[${config.department}] Import order: ${importOrder.join(' -> ')}`);

      // 3. Validate credentials exist in n8n
      console.log(`[${config.department}] Validating credentials...`);
      await this.validateCredentials(config.variables);

      // 4. Deploy workflows in dependency order
      const variables = { ...config.variables };

      for (const templateId of importOrder) {
        const template = templates.find(t => t.id === templateId);
        if (!template) {
          console.warn(`[${config.department}] Template not found: ${templateId}, skipping...`);
          continue;
        }

        try {
          console.log(`[${config.department}] Deploying: ${template.meta.name}...`);

          // Inject parameters
          const injectedWorkflow = await this.injector.injectParameters(
            template.workflow,
            variables
          );

          // Validate
          const validation = this.validator.validateInjection(injectedWorkflow);
          if (!validation.valid) {
            throw new Error(
              `Validation failed:\n${validation.errors.map(e => `  - ${e.message}`).join('\n')}`
            );
          }

          if (validation.warnings.length > 0) {
            console.warn(
              `[${config.department}] Warnings for ${template.meta.name}:\n${validation.warnings.map(w => `  - ${w.message}`).join('\n')}`
            );
          }

          // Deploy to n8n
          const deployed = await this.n8nClient.createWorkflow(injectedWorkflow);

          // Extract webhook URLs
          const webhookUrls = this.extractWebhookUrls(deployed, config.variables.N8N_WEBHOOK_BASE);

          deployedWorkflows.push({
            templateId: template.id,
            workflowId: deployed.id!,
            name: deployed.name,
            active: deployed.active || false,
            webhookUrls
          });

          // Update variables with deployed workflow ID (for Execute Workflow nodes)
          variables[`WORKFLOW_ID_${templateId.toUpperCase().replace(/-/g, '_')}`] = deployed.id!;

          console.log(`[${config.department}] ✓ Deployed: ${template.meta.name} (ID: ${deployed.id})`);
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error);
          errors.push({
            templateId,
            error: errorMsg,
            phase: 'deployment'
          });
          console.error(`[${config.department}] ✗ Failed: ${template.meta.name}: ${errorMsg}`);
        }
      }

      return {
        department: config.department,
        deployedCount: deployedWorkflows.length,
        workflows: deployedWorkflows,
        success: errors.length === 0,
        errors: errors.length > 0 ? errors : undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`[${config.department}] Deployment failed: ${errorMsg}`);

      return {
        department: config.department,
        deployedCount: deployedWorkflows.length,
        workflows: deployedWorkflows,
        success: false,
        errors: [
          {
            templateId: 'deployment',
            error: errorMsg,
            phase: 'deployment'
          }
        ]
      };
    }
  }

  /**
   * Load workflow templates from filesystem
   */
  private async loadTemplates(templateIds: string[]): Promise<WorkflowTemplate[]> {
    const templates: WorkflowTemplate[] = [];

    for (const templateId of templateIds) {
      const template = await this.loadTemplate(templateId);
      templates.push(template);
    }

    return templates;
  }

  /**
   * Load a single workflow template
   */
  async loadTemplate(templateId: string): Promise<WorkflowTemplate> {
    const workflowsDir = path.join(__dirname, '../workflows');

    // Search all category directories for template
    const categories = ['core', 'hr', 'sales-marketing', 'operations', 'finance', 'legal'];

    for (const category of categories) {
      const workflowPath = path.join(workflowsDir, category, `${templateId}.json`);
      const metaPath = path.join(workflowsDir, category, `${templateId}.meta.json`);

      try {
        const workflowContent = await fs.readFile(workflowPath, 'utf-8');
        const metaContent = await fs.readFile(metaPath, 'utf-8');

        const workflow = JSON.parse(workflowContent) as N8nWorkflow;
        const meta = JSON.parse(metaContent);

        return { id: templateId, workflow, meta };
      } catch (error) {
        // Template not in this category, continue searching
        continue;
      }
    }

    throw new Error(`Template not found: ${templateId}`);
  }

  /**
   * Validate credentials exist in n8n
   */
  private async validateCredentials(variables: TemplateVariables): Promise<void> {
    const credentialIds = [
      variables.POSTGRES_CREDENTIAL_ID,
      variables.GOOGLE_DRIVE_CREDENTIAL_ID,
      variables.GMAIL_CREDENTIAL_ID,
      variables.OPENAI_CREDENTIAL_ID,
      variables.GOOGLE_SHEETS_CREDENTIAL_ID,
      variables.GOOGLE_DOCS_CREDENTIAL_ID
    ].filter(Boolean) as string[];

    const validation = await this.n8nClient.validateCredentials(credentialIds);

    if (!validation.valid) {
      throw new Error(
        `Missing credentials in n8n:\n${validation.missing.map(id => `  - ${id}`).join('\n')}`
      );
    }
  }

  /**
   * Extract webhook URLs from deployed workflow
   */
  private extractWebhookUrls(workflow: N8nWorkflow, webhookBase: string): string[] {
    const webhookPaths = this.validator.extractWebhookPaths(workflow);

    return webhookPaths.map(webhook => {
      const path = webhook.path.startsWith('/') ? webhook.path : `/${webhook.path}`;
      return `${webhookBase}${path}`;
    });
  }

  /**
   * Activate all deployed workflows
   */
  async activateWorkflows(workflowIds: string[]): Promise<void> {
    for (const workflowId of workflowIds) {
      await this.n8nClient.activateWorkflow(workflowId);
      console.log(`✓ Activated workflow: ${workflowId}`);
    }
  }

  /**
   * Deactivate all workflows for a department
   */
  async deactivateWorkflows(workflowIds: string[]): Promise<void> {
    for (const workflowId of workflowIds) {
      await this.n8nClient.deactivateWorkflow(workflowId);
      console.log(`✓ Deactivated workflow: ${workflowId}`);
    }
  }

  /**
   * Delete all workflows for a department (cleanup)
   */
  async deleteWorkflows(workflowIds: string[]): Promise<void> {
    for (const workflowId of workflowIds) {
      await this.n8nClient.deleteWorkflow(workflowId);
      console.log(`✓ Deleted workflow: ${workflowId}`);
    }
  }

  /**
   * Dry run deployment (validation only, no actual deployment)
   */
  async dryRun(config: DeploymentConfig): Promise<{
    valid: boolean;
    errors: DeploymentError[];
    warnings: string[];
  }> {
    const errors: DeploymentError[] = [];
    const warnings: string[] = [];

    try {
      // Load templates
      const templates = await this.loadTemplates(config.templates);

      // Resolve dependencies
      const dependencies = this.resolver.extractDependenciesFromTemplates(templates);
      this.resolver.resolveDependencies(dependencies);

      // Inject and validate each template
      for (const template of templates) {
        try {
          const injected = await this.injector.injectParameters(
            template.workflow,
            config.variables
          );

          const validation = this.validator.validateInjection(injected);
          if (!validation.valid) {
            errors.push({
              templateId: template.id,
              error: validation.errors.map(e => e.message).join(', '),
              phase: 'validation'
            });
          }

          if (validation.warnings.length > 0) {
            warnings.push(
              ...validation.warnings.map(w => `${template.id}: ${w.message}`)
            );
          }
        } catch (error) {
          errors.push({
            templateId: template.id,
            error: error.message,
            phase: 'injection'
          });
        }
      }

      return {
        valid: errors.length === 0,
        errors,
        warnings
      };
    } catch (error) {
      return {
        valid: false,
        errors: [
          {
            templateId: 'dry-run',
            error: error.message,
            phase: 'validation'
          }
        ],
        warnings
      };
    }
  }
}

/**
 * Factory function
 */
export function createDeploymentAPI(n8nClient: N8nClient): N8nDeploymentAPI {
  return new N8nDeploymentAPI(n8nClient);
}
