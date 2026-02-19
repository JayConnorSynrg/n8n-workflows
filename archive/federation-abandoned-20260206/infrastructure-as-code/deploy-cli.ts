#!/usr/bin/env node
/**
 * Federation Platform - Unified Deployment CLI
 * Automates department provisioning to Railway or VPS
 */

import { RailwayClient } from './railway-client';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================================
// TYPES
// ============================================================================

interface DepartmentConfig {
  departmentId: string;
  departmentName: string;
  environment: 'dev' | 'staging' | 'prod';

  // Docker
  dockerRegistry: string;
  imageVersion: string;

  // n8n
  n8nWebhookBase: string;

  // LiveKit
  livekitUrl: string;
  livekitApiKey: string;
  livekitApiSecret: string;

  // Cerebras
  cerebrasApiKey: string;
  cerebrasModel: string;
  cerebrasTemperature: string;
  cerebrasMaxTokens: string;

  // Deepgram
  deepgramApiKey: string;
  deepgramModel: string;

  // Cartesia
  cartesiaApiKey: string;
  cartesiaModel: string;
  cartesiaVoice: string;

  // Tools
  enabledTools: string[];

  // Resources
  postgresStorage: number;
  voiceAgentCpu: string;
  voiceAgentMemory: string;

  // Optional
  customDomain?: string;
  costCenter?: string;
  oauthCredentials?: Record<string, string>;
}

interface DeploymentResult {
  success: boolean;
  projectId?: string;
  voiceAgentUrl?: string;
  duration: number;
  error?: string;
  output?: string;
}

// ============================================================================
// DEPLOYMENT CLI CLASS
// ============================================================================

class DeploymentCLI {
  private railwayClient: RailwayClient;

  constructor() {
    this.railwayClient = new RailwayClient();
  }

  /**
   * Main deployment entry point
   */
  async deploy(
    config: DepartmentConfig,
    target: 'railway' | 'vps'
  ): Promise<DeploymentResult> {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`🚀 Deploying ${config.departmentName} to ${target.toUpperCase()}`);
    console.log(`${'='.repeat(80)}\n`);

    if (target === 'railway') {
      return await this.deployToRailway(config);
    } else {
      return await this.deployToVPS(config);
    }
  }

  /**
   * Deploy to Railway using GraphQL API
   */
  private async deployToRailway(config: DepartmentConfig): Promise<DeploymentResult> {
    const startTime = Date.now();

    try {
      // Step 1: Create Railway project
      console.log('  [1/6] Creating Railway project...');
      const project = await this.railwayClient.createProject(
        `aio-${config.departmentId}-${config.environment}`,
        `AIO Voice Assistant for ${config.departmentName} Department`,
        {
          department: config.departmentId,
          environment: config.environment,
          managed_by: 'federation-platform',
          cost_center: config.costCenter || ''
        }
      );
      console.log(`       ✓ Project created: ${project.id}`);

      // Step 2: Generate secure passwords
      console.log('  [2/6] Generating secure credentials...');
      const postgresPassword = this.generatePassword(32);
      const jwtSecret = this.generatePassword(64);
      console.log('       ✓ Credentials generated');

      // Step 3: Create PostgreSQL service
      console.log('  [3/6] Creating PostgreSQL service...');
      const postgres = await this.railwayClient.createService(project.id, {
        name: `postgres-${config.departmentId}`,
        image: 'postgres:15-alpine',
        env: {
          POSTGRES_DB: config.departmentId,
          POSTGRES_USER: config.departmentId,
          POSTGRES_PASSWORD: postgresPassword
        },
        resources: {
          cpuLimit: '1000m',
          memoryLimit: '2048Mi'
        }
      });
      console.log(`       ✓ PostgreSQL created: ${postgres.id}`);

      // Wait for PostgreSQL to be ready
      await this.sleep(10000);

      // Step 4: Get PostgreSQL connection details
      const postgresService = await this.railwayClient.getService(postgres.id);
      const privateDns = postgresService.privateDns || `${postgres.id}.railway.internal`;

      // Step 5: Create Voice Agent service
      console.log('  [4/6] Creating Voice Agent service...');
      const voiceAgent = await this.railwayClient.createService(project.id, {
        name: `voice-agent-${config.departmentId}`,
        image: `${config.dockerRegistry}/aio-federation-template:${config.imageVersion}`,
        env: {
          // Department
          DEPARTMENT_NAME: config.departmentName,
          DEPARTMENT_ID: config.departmentId,
          DB_SCHEMA: `${config.departmentId}_tenant`,

          // Database
          POSTGRES_URL: `postgresql://${config.departmentId}:${postgresPassword}@${privateDns}:5432/${config.departmentId}`,

          // n8n
          N8N_WEBHOOK_BASE: config.n8nWebhookBase,

          // LiveKit
          LIVEKIT_URL: config.livekitUrl,
          LIVEKIT_API_KEY: config.livekitApiKey,
          LIVEKIT_API_SECRET: config.livekitApiSecret,

          // Cerebras
          CEREBRAS_API_KEY: config.cerebrasApiKey,
          CEREBRAS_MODEL: config.cerebrasModel,
          CEREBRAS_TEMPERATURE: config.cerebrasTemperature,
          CEREBRAS_MAX_TOKENS: config.cerebrasMaxTokens,

          // Deepgram
          DEEPGRAM_API_KEY: config.deepgramApiKey,
          DEEPGRAM_MODEL: config.deepgramModel,

          // Cartesia
          CARTESIA_API_KEY: config.cartesiaApiKey,
          CARTESIA_MODEL: config.cartesiaModel,
          CARTESIA_VOICE: config.cartesiaVoice,

          // Tools
          ENABLED_TOOLS: JSON.stringify(config.enabledTools),

          // JWT
          JWT_SECRET: jwtSecret,

          // Logging
          LOG_LEVEL: 'INFO'
        },
        resources: {
          cpuLimit: config.voiceAgentCpu,
          memoryLimit: config.voiceAgentMemory
        },
        healthCheck: {
          path: '/health',
          interval: 30,
          timeout: 10
        }
      });
      console.log(`       ✓ Voice Agent created: ${voiceAgent.id}`);

      // Step 6: Deploy services
      console.log('  [5/6] Deploying services...');
      const deployment = await this.railwayClient.deployService(voiceAgent.id);
      console.log(`       ✓ Deployment started: ${deployment.id}`);

      // Wait for deployment to complete
      console.log('  [6/6] Waiting for deployment to complete...');
      const deploymentStatus = await this.railwayClient.waitForDeployment(
        deployment.id,
        300 // 5 minute timeout
      );

      // Get final service details
      const finalService = await this.railwayClient.getService(voiceAgent.id);

      const duration = (Date.now() - startTime) / 1000;
      console.log(`\n✅ Deployment completed in ${duration.toFixed(1)}s`);
      console.log(`   Voice Agent URL: ${finalService.publicUrl || 'Pending...'}`);

      return {
        success: true,
        projectId: project.id,
        voiceAgentUrl: finalService.publicUrl,
        duration
      };

    } catch (error) {
      const duration = (Date.now() - startTime) / 1000;
      console.error(`\n❌ Deployment failed after ${duration.toFixed(1)}s`);
      console.error(`   Error: ${error instanceof Error ? error.message : String(error)}`);

      return {
        success: false,
        duration,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Deploy to VPS using Ansible
   */
  private async deployToVPS(config: DepartmentConfig): Promise<DeploymentResult> {
    const startTime = Date.now();

    try {
      console.log('  Running Ansible playbook...');

      const ansibleDir = path.join(__dirname, 'ansible');
      const inventoryFile = `inventories/${config.environment}.yml`;

      // Build Ansible command
      const ansibleCmd = [
        'ansible-playbook',
        '-i', inventoryFile,
        '-e', `department_id=${config.departmentId}`,
        '-e', `department_name="${config.departmentName}"`,
        '-e', `docker_registry=${config.dockerRegistry}`,
        '-e', `image_version=${config.imageVersion}`,
        '-e', `n8n_webhook_base=${config.n8nWebhookBase}`,
        '-e', `livekit_url=${config.livekitUrl}`,
        '-e', `livekit_api_key=${config.livekitApiKey}`,
        '-e', `livekit_api_secret=${config.livekitApiSecret}`,
        '-e', `cerebras_api_key=${config.cerebrasApiKey}`,
        '-e', `cerebras_model=${config.cerebrasModel}`,
        '-e', `deepgram_api_key=${config.deepgramApiKey}`,
        '-e', `cartesia_api_key=${config.cartesiaApiKey}`,
        '-e', `enabled_tools='${JSON.stringify(config.enabledTools)}'`,
        'aio-vps.yml'
      ].join(' ');

      // Execute Ansible
      const output = execSync(ansibleCmd, {
        cwd: ansibleDir,
        encoding: 'utf-8',
        stdio: 'inherit'
      });

      const duration = (Date.now() - startTime) / 1000;
      console.log(`\n✅ VPS deployment completed in ${duration.toFixed(1)}s`);

      return {
        success: true,
        duration,
        output: String(output)
      };

    } catch (error) {
      const duration = (Date.now() - startTime) / 1000;
      console.error(`\n❌ VPS deployment failed after ${duration.toFixed(1)}s`);
      console.error(`   Error: ${error instanceof Error ? error.message : String(error)}`);

      return {
        success: false,
        duration,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * List existing deployments
   */
  async listDeployments(environment: string): Promise<void> {
    console.log(`\n📋 Deployments (${environment}):\n`);

    try {
      // Search for projects matching pattern
      const projectPattern = `aio-*-${environment}`;
      console.log(`Searching for projects matching: ${projectPattern}`);

      // Note: Railway API doesn't support filtering, so we'd need to list all
      console.log('(Railway API integration pending - use Railway dashboard)');

    } catch (error) {
      console.error('Error listing deployments:', error);
    }
  }

  /**
   * Delete a deployment
   */
  async deleteDeployment(projectId: string): Promise<void> {
    console.log(`\n🗑️  Deleting deployment: ${projectId}\n`);

    try {
      await this.railwayClient.deleteProject(projectId);
      console.log('✅ Deployment deleted successfully');

    } catch (error) {
      console.error('❌ Error deleting deployment:', error);
      throw error;
    }
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  private generatePassword(length: number): string {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let password = '';
    for (let i = 0; i < length; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  const cli = new DeploymentCLI();

  if (command === 'deploy') {
    // Parse deployment configuration
    const target = args[1] as 'railway' | 'vps';
    const configFile = args[2];

    if (!target || !configFile) {
      console.error('Usage: deploy-cli deploy <railway|vps> <config.json>');
      process.exit(1);
    }

    const config: DepartmentConfig = JSON.parse(
      fs.readFileSync(configFile, 'utf-8')
    );

    const result = await cli.deploy(config, target);
    process.exit(result.success ? 0 : 1);

  } else if (command === 'list') {
    const environment = args[1] || 'prod';
    await cli.listDeployments(environment);

  } else if (command === 'delete') {
    const projectId = args[1];

    if (!projectId) {
      console.error('Usage: deploy-cli delete <project-id>');
      process.exit(1);
    }

    await cli.deleteDeployment(projectId);

  } else {
    console.log(`
Federation Platform - Deployment CLI

Usage:
  deploy-cli deploy <railway|vps> <config.json>    Deploy department
  deploy-cli list [environment]                    List deployments
  deploy-cli delete <project-id>                   Delete deployment

Examples:
  deploy-cli deploy railway hr-config.json
  deploy-cli deploy vps sales-config.json
  deploy-cli list prod
  deploy-cli delete abc123
    `);
  }
}

if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { DeploymentCLI, DepartmentConfig, DeploymentResult };
