/**
 * N8N API Client
 * Version: 1.0.0
 *
 * Wrapper for n8n Cloud REST API
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  N8nWorkflow,
  N8nWorkflowListItem,
  N8nCredential,
  N8nClientConfig,
  N8nListResponse,
  DeploymentError
} from './types';

export class N8nClient {
  private client: AxiosInstance;
  private baseUrl: string;
  private apiKey: string;

  constructor(config: N8nClientConfig) {
    this.baseUrl = config.baseUrl;
    this.apiKey = config.apiKey;

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: config.timeout || 30000,
      headers: {
        'X-N8N-API-KEY': this.apiKey,
        'Content-Type': 'application/json'
      }
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      response => response,
      error => this.handleError(error)
    );
  }

  /**
   * Create a new workflow
   */
  async createWorkflow(workflow: N8nWorkflow): Promise<N8nWorkflow> {
    try {
      const response = await this.client.post('/api/v1/workflows', workflow);
      return response.data;
    } catch (error) {
      throw new DeploymentError(
        `Failed to create workflow: ${error.message}`,
        workflow.name,
        error
      );
    }
  }

  /**
   * Get workflow by ID
   */
  async getWorkflow(workflowId: string): Promise<N8nWorkflow> {
    try {
      const response = await this.client.get(`/api/v1/workflows/${workflowId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get workflow ${workflowId}: ${error.message}`);
    }
  }

  /**
   * Update existing workflow
   */
  async updateWorkflow(workflowId: string, workflow: Partial<N8nWorkflow>): Promise<N8nWorkflow> {
    try {
      const response = await this.client.patch(`/api/v1/workflows/${workflowId}`, workflow);
      return response.data;
    } catch (error) {
      throw new DeploymentError(
        `Failed to update workflow: ${error.message}`,
        workflowId,
        error
      );
    }
  }

  /**
   * Activate a workflow
   */
  async activateWorkflow(workflowId: string): Promise<void> {
    try {
      await this.client.patch(`/api/v1/workflows/${workflowId}`, {
        active: true
      });
    } catch (error) {
      throw new Error(`Failed to activate workflow ${workflowId}: ${error.message}`);
    }
  }

  /**
   * Deactivate a workflow
   */
  async deactivateWorkflow(workflowId: string): Promise<void> {
    try {
      await this.client.patch(`/api/v1/workflows/${workflowId}`, {
        active: false
      });
    } catch (error) {
      throw new Error(`Failed to deactivate workflow ${workflowId}: ${error.message}`);
    }
  }

  /**
   * Delete a workflow
   */
  async deleteWorkflow(workflowId: string): Promise<void> {
    try {
      await this.client.delete(`/api/v1/workflows/${workflowId}`);
    } catch (error) {
      throw new Error(`Failed to delete workflow ${workflowId}: ${error.message}`);
    }
  }

  /**
   * List workflows with pagination
   */
  async listWorkflows(options?: {
    limit?: number;
    cursor?: string;
    active?: boolean;
    tags?: string[];
  }): Promise<N8nListResponse<N8nWorkflowListItem>> {
    try {
      const params: any = {
        limit: options?.limit || 100
      };

      if (options?.cursor) params.cursor = options.cursor;
      if (options?.active !== undefined) params.active = options.active;
      if (options?.tags) params.tags = options.tags.join(',');

      const response = await this.client.get('/api/v1/workflows', { params });
      return {
        data: response.data.data,
        nextCursor: response.data.nextCursor
      };
    } catch (error) {
      throw new Error(`Failed to list workflows: ${error.message}`);
    }
  }

  /**
   * Get all workflows (handles pagination automatically)
   */
  async getAllWorkflows(options?: {
    active?: boolean;
    tags?: string[];
  }): Promise<N8nWorkflowListItem[]> {
    const allWorkflows: N8nWorkflowListItem[] = [];
    let cursor: string | undefined;

    do {
      const response = await this.listWorkflows({ ...options, cursor });
      allWorkflows.push(...response.data);
      cursor = response.nextCursor;
    } while (cursor);

    return allWorkflows;
  }

  /**
   * Get credential by ID
   */
  async getCredential(credentialId: string): Promise<N8nCredential> {
    try {
      const response = await this.client.get(`/api/v1/credentials/${credentialId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get credential ${credentialId}: ${error.message}`);
    }
  }

  /**
   * List credentials
   */
  async listCredentials(): Promise<N8nCredential[]> {
    try {
      const response = await this.client.get('/api/v1/credentials');
      return response.data.data;
    } catch (error) {
      throw new Error(`Failed to list credentials: ${error.message}`);
    }
  }

  /**
   * Check if credential exists
   */
  async credentialExists(credentialId: string): Promise<boolean> {
    try {
      await this.getCredential(credentialId);
      return true;
    } catch (error) {
      if (error.message.includes('404')) {
        return false;
      }
      throw error;
    }
  }

  /**
   * Execute a workflow (for testing)
   */
  async executeWorkflow(workflowId: string, data?: any): Promise<any> {
    try {
      const response = await this.client.post(`/api/v1/workflows/${workflowId}/execute`, {
        data
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to execute workflow ${workflowId}: ${error.message}`);
    }
  }

  /**
   * Get workflow execution status
   */
  async getExecution(executionId: string): Promise<any> {
    try {
      const response = await this.client.get(`/api/v1/executions/${executionId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get execution ${executionId}: ${error.message}`);
    }
  }

  /**
   * Batch create workflows (with error handling)
   */
  async createWorkflowsBatch(
    workflows: N8nWorkflow[],
    options?: {
      activateAfterCreation?: boolean;
      stopOnError?: boolean;
    }
  ): Promise<{
    created: Array<{ templateId: string; workflowId: string; workflow: N8nWorkflow }>;
    failed: Array<{ templateId: string; error: string }>;
  }> {
    const created: Array<{ templateId: string; workflowId: string; workflow: N8nWorkflow }> = [];
    const failed: Array<{ templateId: string; error: string }> = [];

    for (const workflow of workflows) {
      try {
        const createdWorkflow = await this.createWorkflow(workflow);

        created.push({
          templateId: workflow.name,
          workflowId: createdWorkflow.id!,
          workflow: createdWorkflow
        });

        // Activate if requested
        if (options?.activateAfterCreation && createdWorkflow.id) {
          await this.activateWorkflow(createdWorkflow.id);
        }
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        failed.push({
          templateId: workflow.name,
          error: errorMsg
        });

        if (options?.stopOnError) {
          break;
        }
      }
    }

    return { created, failed };
  }

  /**
   * Validate credentials exist before deployment
   */
  async validateCredentials(credentialIds: string[]): Promise<{
    valid: boolean;
    missing: string[];
  }> {
    const missing: string[] = [];

    for (const credId of credentialIds) {
      const exists = await this.credentialExists(credId);
      if (!exists) {
        missing.push(credId);
      }
    }

    return {
      valid: missing.length === 0,
      missing
    };
  }

  /**
   * Handle API errors
   */
  private handleError(error: AxiosError): Promise<never> {
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const data = error.response.data as any;

      if (status === 401) {
        throw new Error('Invalid n8n API key. Check N8N_API_KEY environment variable.');
      }

      if (status === 404) {
        throw new Error(`Resource not found: ${error.config?.url}`);
      }

      if (status === 429) {
        throw new Error('n8n API rate limit exceeded. Please retry later.');
      }

      const message = data?.message || data?.error || error.message;
      throw new Error(`n8n API error (${status}): ${message}`);
    }

    if (error.request) {
      // Request made but no response
      throw new Error(`n8n API request failed: ${error.message}. Check n8n base URL.`);
    }

    // Other errors
    throw error;
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/api/v1/workflows', { params: { limit: 1 } });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get API version/info
   */
  async getApiInfo(): Promise<any> {
    try {
      const response = await this.client.get('/api/v1/');
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get n8n API info: ${error.message}`);
    }
  }
}

/**
 * Factory function for creating n8n client
 */
export function createN8nClient(config: N8nClientConfig): N8nClient {
  return new N8nClient(config);
}

/**
 * Create n8n client from environment variables
 */
export function createN8nClientFromEnv(): N8nClient {
  const baseUrl = process.env.N8N_BASE_URL;
  const apiKey = process.env.N8N_API_KEY;

  if (!baseUrl || !apiKey) {
    throw new Error('Missing required environment variables: N8N_BASE_URL and N8N_API_KEY');
  }

  return new N8nClient({
    baseUrl,
    apiKey
  });
}
