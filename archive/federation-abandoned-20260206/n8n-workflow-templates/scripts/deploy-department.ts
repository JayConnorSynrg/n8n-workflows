/**
 * Deploy Workflows to Department CLI
 * Version: 1.0.0
 *
 * Usage:
 *   npm run deploy-department -- --department hr --name "Human Resources" --credentials ./config/hr-credentials.json
 *   npm run dry-run -- --department hr --name "Human Resources" --credentials ./config/hr-credentials.json
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { createN8nClientFromEnv } from '../src/n8n-client';
import { createDeploymentAPI } from '../src/deploy-api';
import { createTemplateVariables } from '../src/injector';
import { DeploymentConfig } from '../src/types';

interface CredentialsConfig {
  postgres: string;
  googleDrive: string;
  gmail: string;
  openai: string;
  googleSheets?: string;
  googleDocs?: string;
}

interface DepartmentDeploymentConfig {
  department: string;
  departmentName: string;
  credentials: CredentialsConfig;
  templates?: string[];         // If not provided, will deploy all core templates
  n8nWebhookBase?: string;      // If not provided, will use N8N_WEBHOOK_BASE env var
  postgresSchema?: string;      // If not provided, will use {department}_tenant
  voiceAgentUrl?: string;
  voiceAgentApiKey?: string;
}

async function loadCredentialsConfig(credentialsPath: string): Promise<CredentialsConfig> {
  const content = await fs.readFile(credentialsPath, 'utf-8');
  return JSON.parse(content);
}

async function deployDepartment(
  config: DepartmentDeploymentConfig,
  dryRun: boolean = false
): Promise<void> {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Federation Platform - Department Deployment`);
  console.log(`${'='.repeat(60)}\n`);

  console.log(`Department: ${config.departmentName} (${config.department})`);
  console.log(`Mode: ${dryRun ? 'DRY RUN (validation only)' : 'PRODUCTION DEPLOYMENT'}`);
  console.log('');

  // Create n8n client
  const n8nClient = createN8nClientFromEnv();

  // Create deployment API
  const deploymentAPI = createDeploymentAPI(n8nClient);

  // Determine templates to deploy
  const templates = config.templates || [
    'google-drive-repository',
    'agent-context-access',
    'file-download-email',
    'send-gmail',
    'vector-db-add',
    'vector-db-query',
    'manage-contacts'
  ];

  console.log(`Templates to deploy: ${templates.length}`);
  templates.forEach((t, i) => console.log(`  ${i + 1}. ${t}`));
  console.log('');

  // Create template variables
  const n8nWebhookBase = config.n8nWebhookBase || process.env.N8N_WEBHOOK_BASE || 'https://jayconnorexe.app.n8n.cloud/webhook';
  const postgresSchema = config.postgresSchema || `${config.department}_tenant`;

  const variables = createTemplateVariables({
    departmentId: config.department,
    departmentName: config.departmentName,
    credentials: config.credentials,
    n8nWebhookBase,
    postgresSchema,
    voiceAgentUrl: config.voiceAgentUrl,
    voiceAgentApiKey: config.voiceAgentApiKey
  });

  // Create deployment config
  const deploymentConfig: DeploymentConfig = {
    department: config.department,
    departmentName: config.departmentName,
    templates,
    variables,
    n8nApiKey: process.env.N8N_API_KEY!,
    n8nBaseUrl: process.env.N8N_BASE_URL!
  };

  if (dryRun) {
    console.log('Running validation checks...\n');

    const result = await deploymentAPI.dryRun(deploymentConfig);

    if (result.valid) {
      console.log('✓ Validation PASSED\n');
      console.log(`All ${templates.length} templates are valid and ready for deployment.`);
    } else {
      console.error('✗ Validation FAILED\n');
      console.error(`Errors found: ${result.errors.length}\n`);

      result.errors.forEach((error, i) => {
        console.error(`${i + 1}. [${error.templateId}] ${error.error}`);
        console.error(`   Phase: ${error.phase}`);
      });

      if (result.warnings.length > 0) {
        console.warn(`\nWarnings: ${result.warnings.length}\n`);
        result.warnings.forEach((warning, i) => {
          console.warn(`${i + 1}. ${warning}`);
        });
      }

      process.exit(1);
    }

    if (result.warnings.length > 0) {
      console.warn(`\nWarnings: ${result.warnings.length}\n`);
      result.warnings.forEach((warning, i) => {
        console.warn(`${i + 1}. ${warning}`);
      });
    }
  } else {
    console.log('Deploying workflows to n8n...\n');

    const result = await deploymentAPI.deployWorkflows(deploymentConfig);

    console.log('');
    console.log(`${'='.repeat(60)}`);
    console.log(`Deployment ${result.success ? 'COMPLETED' : 'FAILED'}`);
    console.log(`${'='.repeat(60)}\n`);

    console.log(`Deployed: ${result.deployedCount}/${templates.length} workflows`);
    console.log('');

    if (result.workflows.length > 0) {
      console.log('Deployed Workflows:\n');
      result.workflows.forEach((workflow, i) => {
        console.log(`${i + 1}. ${workflow.name}`);
        console.log(`   ID: ${workflow.workflowId}`);
        console.log(`   Active: ${workflow.active}`);
        if (workflow.webhookUrls && workflow.webhookUrls.length > 0) {
          console.log(`   Webhooks:`);
          workflow.webhookUrls.forEach(url => console.log(`     - ${url}`));
        }
        console.log('');
      });
    }

    if (result.errors && result.errors.length > 0) {
      console.error('Deployment Errors:\n');
      result.errors.forEach((error, i) => {
        console.error(`${i + 1}. [${error.templateId}] ${error.error}`);
        console.error(`   Phase: ${error.phase}`);
      });
      console.error('');

      process.exit(1);
    }

    // Ask if user wants to activate workflows
    if (result.workflows.length > 0) {
      const workflowIds = result.workflows.map(w => w.workflowId);

      console.log('\nWorkflows deployed successfully.');
      console.log('To activate workflows, run:');
      console.log(`  npm run activate-workflows -- ${workflowIds.join(' ')}`);
    }
  }

  console.log('\n✓ Done!\n');
}

/**
 * CLI Entry Point
 */
async function main() {
  const args = process.argv.slice(2);

  const department = args.find(arg => arg.startsWith('--department='))?.split('=')[1];
  const departmentName = args.find(arg => arg.startsWith('--name='))?.split('=')[1];
  const credentialsPath = args.find(arg => arg.startsWith('--credentials='))?.split('=')[1];
  const templatesArg = args.find(arg => arg.startsWith('--templates='))?.split('=')[1];
  const dryRun = args.includes('--dry-run');

  if (!department || !departmentName || !credentialsPath) {
    console.error('Usage: npm run deploy-department -- --department=<id> --name="<name>" --credentials=<path> [--templates=<comma-separated>] [--dry-run]');
    console.error('\nExample:');
    console.error('  npm run deploy-department -- --department=hr --name="Human Resources" --credentials=./config/hr-credentials.json');
    console.error('  npm run dry-run -- --department=hr --name="Human Resources" --credentials=./config/hr-credentials.json');
    process.exit(1);
  }

  try {
    // Load credentials
    const credentials = await loadCredentialsConfig(credentialsPath);

    // Parse templates if provided
    const templates = templatesArg?.split(',').map(t => t.trim());

    // Deploy
    await deployDepartment(
      {
        department,
        departmentName,
        credentials,
        templates
      },
      dryRun
    );
  } catch (error) {
    console.error('\n✗ Deployment failed:', error.message);
    console.error('');
    console.error('Stack trace:', error.stack);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

export { deployDepartment };
