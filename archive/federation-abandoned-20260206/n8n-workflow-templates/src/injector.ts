/**
 * N8N Workflow Parameter Injection Engine
 * Version: 1.0.0
 *
 * Replaces Handlebars-style template variables with department-specific values.
 */

import Handlebars from 'handlebars';
import { cloneDeep } from 'lodash';
import {
  N8nWorkflow,
  TemplateVariables,
  N8nNode,
  ValidationResult,
  ValidationError as ValidationErrorType,
  TemplateError
} from './types';

export class WorkflowInjector {
  /**
   * Inject department-specific parameters into a workflow template
   */
  async injectParameters(
    templateWorkflow: N8nWorkflow,
    variables: TemplateVariables
  ): Promise<N8nWorkflow> {
    // 1. Deep clone to avoid mutating original template
    const workflow = cloneDeep(templateWorkflow);

    // 2. Replace workflow name
    workflow.name = this.replaceVariables(workflow.name, variables);

    // 3. Process each node
    workflow.nodes = workflow.nodes.map(node =>
      this.injectNodeParameters(node, variables)
    );

    // 4. Update connections (node names may have variables)
    workflow.connections = this.injectConnections(workflow.connections, variables);

    // 5. Update tags
    if (workflow.tags) {
      workflow.tags = workflow.tags.map(tag => ({
        ...tag,
        name: this.replaceVariables(tag.name, variables)
      }));
    }

    return workflow;
  }

  /**
   * Inject parameters into a single node
   */
  private injectNodeParameters(node: N8nNode, variables: TemplateVariables): N8nNode {
    const injectedNode = cloneDeep(node);

    // Replace node name
    injectedNode.name = this.replaceVariables(node.name, variables);

    // Replace node ID (if it contains variables)
    injectedNode.id = this.replaceVariables(node.id, variables);

    // Replace webhook ID (if present)
    if (injectedNode.webhookId) {
      injectedNode.webhookId = this.replaceVariables(injectedNode.webhookId, variables);
    }

    // Replace notes
    if (injectedNode.notes) {
      injectedNode.notes = this.replaceVariables(injectedNode.notes, variables);
    }

    // Recursively replace parameters
    injectedNode.parameters = this.replaceInObject(node.parameters, variables);

    // Replace credentials
    if (injectedNode.credentials) {
      const replacedCredentials: Record<string, any> = {};
      for (const [credType, credRef] of Object.entries(injectedNode.credentials)) {
        replacedCredentials[credType] = {
          id: this.replaceVariables(credRef.id, variables),
          name: this.replaceVariables(credRef.name, variables)
        };
      }
      injectedNode.credentials = replacedCredentials;
    }

    return injectedNode;
  }

  /**
   * Inject parameters into connections object
   */
  private injectConnections(
    connections: N8nWorkflow['connections'],
    variables: TemplateVariables
  ): N8nWorkflow['connections'] {
    const injectedConnections: N8nWorkflow['connections'] = {};

    for (const [sourceNode, outputs] of Object.entries(connections)) {
      const replacedSourceNode = this.replaceVariables(sourceNode, variables);

      if (outputs.main) {
        injectedConnections[replacedSourceNode] = {
          main: outputs.main.map(outputConnections =>
            outputConnections.map(conn => ({
              ...conn,
              node: this.replaceVariables(conn.node, variables)
            }))
          )
        };
      }
    }

    return injectedConnections;
  }

  /**
   * Replace variables in a string using Handlebars
   */
  private replaceVariables(template: string, variables: TemplateVariables): string {
    const compiled = Handlebars.compile(template, { noEscape: true });
    return compiled(variables);
  }

  /**
   * Recursively replace variables in an object
   */
  private replaceInObject(obj: any, variables: TemplateVariables): any {
    if (typeof obj === 'string') {
      return this.replaceVariables(obj, variables);
    }

    if (Array.isArray(obj)) {
      return obj.map(item => this.replaceInObject(item, variables));
    }

    if (obj && typeof obj === 'object') {
      const result: any = {};
      for (const [key, value] of Object.entries(obj)) {
        // Replace both the key and value
        const replacedKey = this.replaceVariables(key, variables);
        result[replacedKey] = this.replaceInObject(value, variables);
      }
      return result;
    }

    return obj;
  }

  /**
   * Extract all template variables from a workflow
   * Useful for determining what variables are needed
   */
  extractVariables(workflow: N8nWorkflow): Set<string> {
    const variableRegex = /\{\{([A-Z_][A-Z0-9_]*)\}\}/g;
    const variables = new Set<string>();

    const extractFromString = (str: string) => {
      const matches = str.matchAll(variableRegex);
      for (const match of matches) {
        variables.add(match[1]);
      }
    };

    const extractFromObject = (obj: any) => {
      if (typeof obj === 'string') {
        extractFromString(obj);
      } else if (Array.isArray(obj)) {
        obj.forEach(extractFromObject);
      } else if (obj && typeof obj === 'object') {
        Object.values(obj).forEach(extractFromObject);
      }
    };

    // Extract from workflow name
    extractFromString(workflow.name);

    // Extract from nodes
    workflow.nodes.forEach(node => {
      extractFromString(node.name);
      extractFromString(node.id);
      if (node.webhookId) extractFromString(node.webhookId);
      if (node.notes) extractFromString(node.notes);
      extractFromObject(node.parameters);
      if (node.credentials) {
        extractFromObject(node.credentials);
      }
    });

    // Extract from connections
    extractFromObject(workflow.connections);

    // Extract from tags
    if (workflow.tags) {
      workflow.tags.forEach(tag => extractFromString(tag.name));
    }

    return variables;
  }

  /**
   * Validate that all required variables are provided
   */
  validateVariables(
    workflow: N8nWorkflow,
    variables: TemplateVariables
  ): ValidationResult {
    const errors: ValidationErrorType[] = [];
    const extractedVars = this.extractVariables(workflow);

    for (const varName of extractedVars) {
      if (!(varName in variables)) {
        errors.push({
          type: 'unreplaced_variable',
          message: `Missing required variable: ${varName}`,
          field: varName
        });
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings: []
    };
  }
}

/**
 * Utility function for quick injection
 */
export async function injectWorkflowParameters(
  workflow: N8nWorkflow,
  variables: TemplateVariables
): Promise<N8nWorkflow> {
  const injector = new WorkflowInjector();

  // Validate variables first
  const validation = injector.validateVariables(workflow, variables);
  if (!validation.valid) {
    throw new TemplateError(
      `Missing required variables: ${validation.errors.map(e => e.message).join(', ')}`,
      workflow.name,
      'injection'
    );
  }

  return injector.injectParameters(workflow, variables);
}

/**
 * Batch inject multiple workflows
 */
export async function injectMultipleWorkflows(
  workflows: Map<string, N8nWorkflow>,
  variables: TemplateVariables
): Promise<Map<string, N8nWorkflow>> {
  const injector = new WorkflowInjector();
  const injected = new Map<string, N8nWorkflow>();

  for (const [templateId, workflow] of workflows) {
    try {
      const injectedWorkflow = await injector.injectParameters(workflow, variables);
      injected.set(templateId, injectedWorkflow);
    } catch (error) {
      throw new TemplateError(
        `Failed to inject parameters for ${templateId}: ${error.message}`,
        templateId,
        'injection'
      );
    }
  }

  return injected;
}

/**
 * Helper to create department-specific variables from config
 */
export function createTemplateVariables(config: {
  departmentId: string;
  departmentName: string;
  credentials: {
    postgres: string;
    googleDrive: string;
    gmail: string;
    openai: string;
    googleSheets?: string;
    googleDocs?: string;
  };
  n8nWebhookBase: string;
  postgresSchema: string;
  voiceAgentUrl?: string;
  voiceAgentApiKey?: string;
  workflowIds?: Record<string, string>;
}): TemplateVariables {
  const variables: TemplateVariables = {
    DEPARTMENT_NAME: config.departmentName,
    DEPARTMENT_ID: config.departmentId,
    POSTGRES_CREDENTIAL_ID: config.credentials.postgres,
    GOOGLE_DRIVE_CREDENTIAL_ID: config.credentials.googleDrive,
    GMAIL_CREDENTIAL_ID: config.credentials.gmail,
    OPENAI_CREDENTIAL_ID: config.credentials.openai,
    N8N_WEBHOOK_BASE: config.n8nWebhookBase,
    POSTGRES_SCHEMA: config.postgresSchema
  };

  if (config.credentials.googleSheets) {
    variables.GOOGLE_SHEETS_CREDENTIAL_ID = config.credentials.googleSheets;
  }

  if (config.credentials.googleDocs) {
    variables.GOOGLE_DOCS_CREDENTIAL_ID = config.credentials.googleDocs;
  }

  if (config.voiceAgentUrl) {
    variables.VOICE_AGENT_URL = config.voiceAgentUrl;
  }

  if (config.voiceAgentApiKey) {
    variables.VOICE_AGENT_API_KEY = config.voiceAgentApiKey;
  }

  // Add workflow IDs for Execute Workflow nodes
  if (config.workflowIds) {
    for (const [key, value] of Object.entries(config.workflowIds)) {
      variables[`WORKFLOW_ID_${key.toUpperCase()}`] = value;
    }
  }

  return variables;
}
