/**
 * N8N Workflow Template Validator
 * Version: 1.0.0
 *
 * Validates injected workflows before deployment to n8n.
 */

import {
  N8nWorkflow,
  ValidationResult,
  ValidationError,
  ValidationWarning,
  TemplateVariables
} from './types';

export class TemplateValidator {
  /**
   * Validate an injected workflow
   */
  validateInjection(workflow: N8nWorkflow): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // 1. Check for unreplaced template variables
    const unreplacedVars = this.findUnreplacedVariables(workflow);
    unreplacedVars.forEach(varInfo => {
      errors.push({
        type: 'unreplaced_variable',
        message: `Unreplaced template variable: ${varInfo.variable}`,
        nodeId: varInfo.nodeId,
        nodeName: varInfo.nodeName,
        field: varInfo.field
      });
    });

    // 2. Validate credentials
    const credentialErrors = this.validateCredentials(workflow);
    errors.push(...credentialErrors);

    // 3. Validate webhooks
    const webhookErrors = this.validateWebhooks(workflow);
    errors.push(...webhookErrors);

    // 4. Validate connections
    const connectionErrors = this.validateConnections(workflow);
    errors.push(...connectionErrors);

    // 5. Check for error handling (warnings)
    const errorHandlingWarnings = this.checkErrorHandling(workflow);
    warnings.push(...errorHandlingWarnings);

    // 6. Check for deprecated typeVersions (warnings)
    const versionWarnings = this.checkTypeVersions(workflow);
    warnings.push(...versionWarnings);

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions: this.generateSuggestions(errors, warnings)
    };
  }

  /**
   * Find unreplaced template variables ({{VAR_NAME}})
   */
  private findUnreplacedVariables(workflow: N8nWorkflow): Array<{
    variable: string;
    nodeId?: string;
    nodeName?: string;
    field?: string;
  }> {
    const variableRegex = /\{\{([A-Z_][A-Z0-9_]*)\}\}/g;
    const unreplaced: Array<{
      variable: string;
      nodeId?: string;
      nodeName?: string;
      field?: string;
    }> = [];

    const checkString = (str: string, nodeId?: string, nodeName?: string, field?: string) => {
      const matches = str.matchAll(variableRegex);
      for (const match of matches) {
        unreplaced.push({
          variable: match[0],
          nodeId,
          nodeName,
          field
        });
      }
    };

    const checkObject = (obj: any, nodeId?: string, nodeName?: string, field?: string) => {
      if (typeof obj === 'string') {
        checkString(obj, nodeId, nodeName, field);
      } else if (Array.isArray(obj)) {
        obj.forEach(item => checkObject(item, nodeId, nodeName, field));
      } else if (obj && typeof obj === 'object') {
        Object.entries(obj).forEach(([key, value]) => {
          checkObject(value, nodeId, nodeName, key);
        });
      }
    };

    // Check workflow name
    checkString(workflow.name);

    // Check nodes
    workflow.nodes.forEach(node => {
      checkString(node.name, node.id, node.name, 'name');
      checkString(node.id, node.id, node.name, 'id');
      if (node.webhookId) checkString(node.webhookId, node.id, node.name, 'webhookId');
      if (node.notes) checkString(node.notes, node.id, node.name, 'notes');
      checkObject(node.parameters, node.id, node.name, 'parameters');
      if (node.credentials) {
        checkObject(node.credentials, node.id, node.name, 'credentials');
      }
    });

    // Check connections
    checkObject(workflow.connections);

    // Check tags
    if (workflow.tags) {
      workflow.tags.forEach(tag => checkString(tag.name));
    }

    return unreplaced;
  }

  /**
   * Validate credentials are valid n8n credential IDs (not empty, not template vars)
   */
  private validateCredentials(workflow: N8nWorkflow): ValidationError[] {
    const errors: ValidationError[] = [];

    workflow.nodes.forEach(node => {
      if (!node.credentials) return;

      Object.entries(node.credentials).forEach(([credType, credRef]) => {
        // Check if credential ID is empty or placeholder
        if (!credRef.id || credRef.id.trim() === '') {
          errors.push({
            type: 'invalid_credential',
            message: `Empty credential ID for type: ${credType}`,
            nodeId: node.id,
            nodeName: node.name,
            field: `credentials.${credType}.id`
          });
        }

        // Check if credential ID looks like a placeholder
        if (credRef.id.startsWith('TODO') || credRef.id.startsWith('PLACEHOLDER')) {
          errors.push({
            type: 'invalid_credential',
            message: `Placeholder credential ID for type: ${credType}: ${credRef.id}`,
            nodeId: node.id,
            nodeName: node.name,
            field: `credentials.${credType}.id`
          });
        }
      });
    });

    return errors;
  }

  /**
   * Validate webhooks have valid paths (no template variables, no empty paths)
   */
  private validateWebhooks(workflow: N8nWorkflow): ValidationError[] {
    const errors: ValidationError[] = [];

    workflow.nodes
      .filter(node => node.type === 'n8n-nodes-base.webhook')
      .forEach(node => {
        const path = node.parameters.path;

        if (!path || path.trim() === '') {
          errors.push({
            type: 'invalid_webhook',
            message: 'Webhook path is empty',
            nodeId: node.id,
            nodeName: node.name,
            field: 'parameters.path'
          });
        }

        // Check for unreplaced variables
        if (path && path.includes('{{')) {
          errors.push({
            type: 'invalid_webhook',
            message: `Webhook path contains unreplaced variables: ${path}`,
            nodeId: node.id,
            nodeName: node.name,
            field: 'parameters.path'
          });
        }
      });

    return errors;
  }

  /**
   * Validate connections are properly formed
   */
  private validateConnections(workflow: N8nWorkflow): ValidationError[] {
    const errors: ValidationError[] = [];
    const nodeNames = new Set(workflow.nodes.map(n => n.name));

    Object.entries(workflow.connections).forEach(([sourceNode, outputs]) => {
      // Check source node exists
      if (!nodeNames.has(sourceNode)) {
        errors.push({
          type: 'invalid_connection',
          message: `Connection source node not found: ${sourceNode}`,
          field: `connections.${sourceNode}`
        });
      }

      // Check target nodes exist
      outputs.main?.forEach((outputConnections, outputIndex) => {
        outputConnections.forEach((conn, connIndex) => {
          if (!nodeNames.has(conn.node)) {
            errors.push({
              type: 'invalid_connection',
              message: `Connection target node not found: ${conn.node}`,
              field: `connections.${sourceNode}.main[${outputIndex}][${connIndex}].node`
            });
          }

          // Check connection type is 'main'
          if (conn.type !== 'main') {
            errors.push({
              type: 'invalid_connection',
              message: `Invalid connection type: ${conn.type} (must be 'main')`,
              field: `connections.${sourceNode}.main[${outputIndex}][${connIndex}].type`
            });
          }

          // Check index is a number
          if (typeof conn.index !== 'number') {
            errors.push({
              type: 'invalid_connection',
              message: `Connection index must be a number, got: ${typeof conn.index}`,
              field: `connections.${sourceNode}.main[${outputIndex}][${connIndex}].index`
            });
          }
        });
      });
    });

    return errors;
  }

  /**
   * Check for missing error handling (warnings, not errors)
   */
  private checkErrorHandling(workflow: N8nWorkflow): ValidationWarning[] {
    const warnings: ValidationWarning[] = [];

    const externalApiNodes = workflow.nodes.filter(node =>
      node.type.includes('openai') ||
      node.type.includes('google') ||
      node.type.includes('http')
    );

    externalApiNodes.forEach(node => {
      if (!node.onError) {
        warnings.push({
          type: 'missing_error_handling',
          message: 'External API node missing error handling (onError property)',
          nodeId: node.id,
          nodeName: node.name
        });
      }

      if (!node.retryOnFail && node.type.includes('openai')) {
        warnings.push({
          type: 'missing_error_handling',
          message: 'OpenAI node missing retry configuration (retryOnFail)',
          nodeId: node.id,
          nodeName: node.name
        });
      }
    });

    return warnings;
  }

  /**
   * Check for deprecated typeVersions (warnings)
   */
  private checkTypeVersions(workflow: N8nWorkflow): ValidationWarning[] {
    const warnings: ValidationWarning[] = [];

    // Known latest typeVersions (as of 2026-02-06)
    const latestVersions: Record<string, number> = {
      'n8n-nodes-base.webhook': 2,
      'n8n-nodes-base.postgres': 2.4,
      'n8n-nodes-base.httpRequest': 4.2,
      '@n8n/n8n-nodes-langchain.openAi': 1.6
    };

    workflow.nodes.forEach(node => {
      const latestVersion = latestVersions[node.type];
      if (latestVersion && node.typeVersion < latestVersion) {
        warnings.push({
          type: 'deprecated_type_version',
          message: `Node using older typeVersion ${node.typeVersion}, latest is ${latestVersion}`,
          nodeId: node.id,
          nodeName: node.name
        });
      }
    });

    return warnings;
  }

  /**
   * Generate helpful suggestions based on errors/warnings
   */
  private generateSuggestions(
    errors: ValidationError[],
    warnings: ValidationWarning[]
  ): string[] {
    const suggestions: string[] = [];

    // Unreplaced variables
    const unreplacedVarErrors = errors.filter(e => e.type === 'unreplaced_variable');
    if (unreplacedVarErrors.length > 0) {
      const vars = [...new Set(unreplacedVarErrors.map(e => e.field || 'unknown'))];
      suggestions.push(
        `Add missing template variables to TemplateVariables: ${vars.join(', ')}`
      );
    }

    // Invalid credentials
    const credErrors = errors.filter(e => e.type === 'invalid_credential');
    if (credErrors.length > 0) {
      suggestions.push(
        'Ensure all credentials exist in n8n before deployment. Use n8n credential IDs, not names.'
      );
    }

    // Missing error handling
    const errorHandlingWarnings = warnings.filter(w => w.type === 'missing_error_handling');
    if (errorHandlingWarnings.length > 0) {
      suggestions.push(
        'Add error handling to external API nodes: set onError: "continueRegularOutput" and retryOnFail: true'
      );
    }

    // Deprecated typeVersions
    const versionWarnings = warnings.filter(w => w.type === 'deprecated_type_version');
    if (versionWarnings.length > 0) {
      suggestions.push(
        'Update node typeVersions to latest. Use mcp__n8n-mcp__get_node to find current versions.'
      );
    }

    return suggestions;
  }

  /**
   * Quick validation for deployment readiness
   */
  isDeploymentReady(workflow: N8nWorkflow): boolean {
    const result = this.validateInjection(workflow);
    return result.valid;
  }

  /**
   * Extract credential IDs from workflow
   */
  extractCredentialIds(workflow: N8nWorkflow): Set<string> {
    const credentialIds = new Set<string>();

    workflow.nodes.forEach(node => {
      if (!node.credentials) return;

      Object.values(node.credentials).forEach(credRef => {
        if (credRef.id && credRef.id.trim() !== '') {
          credentialIds.add(credRef.id);
        }
      });
    });

    return credentialIds;
  }

  /**
   * Extract webhook paths from workflow
   */
  extractWebhookPaths(workflow: N8nWorkflow): Array<{
    path: string;
    method: string;
    nodeId: string;
    nodeName: string;
  }> {
    return workflow.nodes
      .filter(node => node.type === 'n8n-nodes-base.webhook')
      .map(node => ({
        path: node.parameters.path || '',
        method: node.parameters.httpMethod || 'POST',
        nodeId: node.id,
        nodeName: node.name
      }));
  }
}

/**
 * Utility function for quick validation
 */
export function validateWorkflow(workflow: N8nWorkflow): ValidationResult {
  const validator = new TemplateValidator();
  return validator.validateInjection(workflow);
}

/**
 * Utility function to check if workflow is deployment-ready
 */
export function isWorkflowValid(workflow: N8nWorkflow): boolean {
  const validator = new TemplateValidator();
  return validator.isDeploymentReady(workflow);
}
