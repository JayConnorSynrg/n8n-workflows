/**
 * Convert Existing N8N Workflows to Templates
 * Version: 1.0.0
 *
 * Usage:
 *   npm run convert-workflow -- --workflow-id IamjzfFxjHviJvJg --category core
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { N8nClient, createN8nClientFromEnv } from '../src/n8n-client';
import {
  N8nWorkflow,
  WorkflowMetadata,
  ConversionOperation,
  TemplateCategory
} from '../src/types';

interface ConversionConfig {
  workflowId: string;
  category: TemplateCategory;
  templateId?: string; // If not provided, will use slugified workflow name
}

class TemplateConverter {
  private n8nClient: N8nClient;

  constructor(n8nClient: N8nClient) {
    this.n8nClient = n8nClient;
  }

  /**
   * Convert a workflow to template
   */
  async convertWorkflow(config: ConversionConfig): Promise<void> {
    console.log(`Converting workflow ${config.workflowId} to template...`);

    // 1. Fetch workflow from n8n
    const workflow = await this.n8nClient.getWorkflow(config.workflowId);
    console.log(`✓ Fetched workflow: ${workflow.name}`);

    // 2. Generate template ID
    const templateId = config.templateId || this.slugify(workflow.name);

    // 3. Templatize workflow
    const { templatedWorkflow, conversions } = this.templatizeWorkflow(workflow);

    // 4. Generate metadata
    const metadata = this.generateMetadata(workflow, templateId, config.category, conversions);

    // 5. Save template to filesystem
    await this.saveTemplate(templateId, config.category, templatedWorkflow, metadata);

    console.log(`✓ Template saved: ${templateId}`);
    console.log(`  Category: ${config.category}`);
    console.log(`  Conversions: ${conversions.length}`);
    console.log(`  Required credentials: ${metadata.requiredCredentials.length}`);
    console.log(`  Webhooks: ${metadata.requiredWebhooks.length}`);
  }

  /**
   * Templatize workflow (replace values with Handlebars variables)
   */
  private templatizeWorkflow(workflow: N8nWorkflow): {
    templatedWorkflow: N8nWorkflow;
    conversions: ConversionOperation[];
  } {
    const conversions: ConversionOperation[] = [];
    const templatedWorkflow: N8nWorkflow = JSON.parse(JSON.stringify(workflow));

    // Remove n8n-specific IDs
    delete templatedWorkflow.id;

    // Templatize workflow name
    const namePattern = /^(.*?)\s*-\s*(Google Drive|Drive|Gmail|Voice|Agent|Database)/i;
    const nameMatch = workflow.name.match(namePattern);
    if (nameMatch) {
      templatedWorkflow.name = `{{DEPARTMENT_NAME}} - ${nameMatch[0].replace(nameMatch[1], '').trim()}`;
    }

    // Templatize each node
    templatedWorkflow.nodes = templatedWorkflow.nodes.map(node => {
      const templatedNode = { ...node };

      // Templatize credentials
      if (templatedNode.credentials) {
        const templatedCredentials: any = {};
        for (const [credType, credRef] of Object.entries(templatedNode.credentials)) {
          templatedCredentials[credType] = {
            id: this.templatizeCredential(credType, credRef.id),
            name: `{{DEPARTMENT_NAME}} ${this.getCredentialDisplayName(credType)}`
          };

          conversions.push({
            type: 'credential_templatized',
            original: credRef.id,
            template: templatedCredentials[credType].id,
            nodeId: node.id
          });
        }
        templatedNode.credentials = templatedCredentials;
      }

      // Templatize webhook paths
      if (templatedNode.type === 'n8n-nodes-base.webhook' && templatedNode.parameters.path) {
        const originalPath = templatedNode.parameters.path;
        const templatedPath = this.templatizeWebhookPath(originalPath);
        templatedNode.parameters.path = templatedPath;

        conversions.push({
          type: 'webhook_templatized',
          original: originalPath,
          template: templatedPath,
          nodeId: node.id
        });
      }

      // Templatize PostgreSQL schema in queries
      if (templatedNode.type === 'n8n-nodes-base.postgres' && templatedNode.parameters.query) {
        const originalQuery = templatedNode.parameters.query;
        const templatedQuery = this.templatizePostgresQuery(originalQuery);
        if (templatedQuery !== originalQuery) {
          templatedNode.parameters.query = templatedQuery;

          conversions.push({
            type: 'schema_templatized',
            original: originalQuery,
            template: templatedQuery,
            nodeId: node.id
          });
        }
      }

      // Templatize HTTP Request URLs (n8n webhook URLs)
      if (templatedNode.type === 'n8n-nodes-base.httpRequest' && templatedNode.parameters.url) {
        const originalUrl = templatedNode.parameters.url;
        const templatedUrl = this.templatizeUrl(originalUrl);
        if (templatedUrl !== originalUrl) {
          templatedNode.parameters.url = templatedUrl;

          conversions.push({
            type: 'url_templatized',
            original: originalUrl,
            template: templatedUrl,
            nodeId: node.id
          });
        }
      }

      return templatedNode;
    });

    return { templatedWorkflow, conversions };
  }

  /**
   * Templatize credential ID
   */
  private templatizeCredential(credType: string, credId: string): string {
    const mapping: Record<string, string> = {
      'postgres': '{{POSTGRES_CREDENTIAL_ID}}',
      'googleDriveOAuth2Api': '{{GOOGLE_DRIVE_CREDENTIAL_ID}}',
      'gmailOAuth2': '{{GMAIL_CREDENTIAL_ID}}',
      'openAiApi': '{{OPENAI_CREDENTIAL_ID}}',
      'googleSheetsOAuth2Api': '{{GOOGLE_SHEETS_CREDENTIAL_ID}}',
      'googleDocsOAuth2Api': '{{GOOGLE_DOCS_CREDENTIAL_ID}}'
    };

    return mapping[credType] || credId;
  }

  /**
   * Get credential display name
   */
  private getCredentialDisplayName(credType: string): string {
    const mapping: Record<string, string> = {
      'postgres': 'PostgreSQL',
      'googleDriveOAuth2Api': 'Google Drive',
      'gmailOAuth2': 'Gmail',
      'openAiApi': 'OpenAI',
      'googleSheetsOAuth2Api': 'Google Sheets',
      'googleDocsOAuth2Api': 'Google Docs'
    };

    return mapping[credType] || credType;
  }

  /**
   * Templatize webhook path
   */
  private templatizeWebhookPath(path: string): string {
    // Remove any leading department-specific prefix
    // E.g., "/hr/drive-repository" -> "/{{DEPARTMENT_ID}}/drive-repository"
    const departmentPattern = /^\/([a-z]+)\//;
    const match = path.match(departmentPattern);
    if (match) {
      return path.replace(match[1], '{{DEPARTMENT_ID}}');
    }
    return path;
  }

  /**
   * Templatize PostgreSQL schema in queries
   */
  private templatizePostgresQuery(query: string): string {
    // Replace schema references: FROM schema_name.table_name -> FROM {{POSTGRES_SCHEMA}}.table_name
    const schemaPattern = /FROM\s+([a-z_]+)\./gi;
    return query.replace(schemaPattern, 'FROM {{POSTGRES_SCHEMA}}.');
  }

  /**
   * Templatize n8n webhook URLs
   */
  private templatizeUrl(url: string): string {
    // Replace n8n webhook base URLs
    const n8nPattern = /https:\/\/[a-z0-9]+\.app\.n8n\.cloud\/webhook/gi;
    return url.replace(n8nPattern, '{{N8N_WEBHOOK_BASE}}');
  }

  /**
   * Generate metadata file
   */
  private generateMetadata(
    workflow: N8nWorkflow,
    templateId: string,
    category: TemplateCategory,
    conversions: ConversionOperation[]
  ): WorkflowMetadata {
    // Extract required credentials
    const credentialTypes = new Set<string>();
    workflow.nodes.forEach(node => {
      if (node.credentials) {
        Object.keys(node.credentials).forEach(credType => credentialTypes.add(credType));
      }
    });

    const requiredCredentials = Array.from(credentialTypes).map(credType => ({
      type: credType,
      namePattern: `{DEPARTMENT}_${this.getCredentialDisplayName(credType).toLowerCase().replace(/\s+/g, '_')}`
    }));

    // Extract webhooks
    const webhookNodes = workflow.nodes.filter(n => n.type === 'n8n-nodes-base.webhook');
    const requiredWebhooks = webhookNodes.map(node => ({
      path: node.parameters.path || '/unknown',
      method: node.parameters.httpMethod || 'POST'
    }));

    // Extract dependencies (Execute Workflow nodes)
    const executeWorkflowNodes = workflow.nodes.filter(
      n => n.type === 'n8n-nodes-base.executeWorkflow'
    );
    const dependencies = executeWorkflowNodes
      .map(n => n.parameters.workflowId)
      .filter(Boolean)
      .map(id => `workflow-${id}`); // Convert to template IDs

    return {
      templateId,
      name: workflow.name,
      category,
      requiredCredentials,
      requiredWebhooks,
      dependencies,
      description: `Converted from workflow ${workflow.id || 'unknown'}`,
      estimatedExecutionTime: '2-5 seconds'
    };
  }

  /**
   * Save template to filesystem
   */
  private async saveTemplate(
    templateId: string,
    category: TemplateCategory,
    workflow: N8nWorkflow,
    metadata: WorkflowMetadata
  ): Promise<void> {
    const workflowsDir = path.join(__dirname, '../workflows', category);
    await fs.mkdir(workflowsDir, { recursive: true });

    const workflowPath = path.join(workflowsDir, `${templateId}.json`);
    const metaPath = path.join(workflowsDir, `${templateId}.meta.json`);

    await fs.writeFile(workflowPath, JSON.stringify(workflow, null, 2));
    await fs.writeFile(metaPath, JSON.stringify(metadata, null, 2));

    console.log(`  Saved: ${workflowPath}`);
    console.log(`  Saved: ${metaPath}`);
  }

  /**
   * Convert workflow name to slug (template ID)
   */
  private slugify(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }
}

/**
 * CLI Entry Point
 */
async function main() {
  const args = process.argv.slice(2);
  const workflowId = args.find(arg => arg.startsWith('--workflow-id='))?.split('=')[1];
  const category = args.find(arg => arg.startsWith('--category='))?.split('=')[1] as TemplateCategory;
  const templateId = args.find(arg => arg.startsWith('--template-id='))?.split('=')[1];

  if (!workflowId || !category) {
    console.error('Usage: npm run convert-workflow -- --workflow-id=<ID> --category=<core|hr|sales-marketing|operations|finance|legal> [--template-id=<ID>]');
    process.exit(1);
  }

  const validCategories: TemplateCategory[] = ['core', 'hr', 'sales-marketing', 'operations', 'finance', 'legal'];
  if (!validCategories.includes(category)) {
    console.error(`Invalid category: ${category}. Must be one of: ${validCategories.join(', ')}`);
    process.exit(1);
  }

  try {
    const n8nClient = createN8nClientFromEnv();
    const converter = new TemplateConverter(n8nClient);

    await converter.convertWorkflow({
      workflowId,
      category,
      templateId
    });

    console.log('\n✓ Conversion complete!');
  } catch (error) {
    console.error('\n✗ Conversion failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

export { TemplateConverter };
