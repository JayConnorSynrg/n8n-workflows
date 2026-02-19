/**
 * Railway GraphQL API Client
 * Programmatic interface for Railway project and service management
 */

interface RailwayProject {
  id: string;
  name: string;
  description?: string;
}

interface RailwayService {
  id: string;
  name: string;
  projectId: string;
  privateUrl?: string;
  publicUrl?: string;
  privateDns?: string;
}

interface Deployment {
  id: string;
  status: 'QUEUED' | 'BUILDING' | 'DEPLOYING' | 'SUCCESS' | 'FAILED' | 'CRASHED';
  createdAt: string;
  url?: string;
}

interface DeploymentStatus {
  id: string;
  status: string;
  url?: string;
  error?: string;
  logs?: string[];
}

interface EnvironmentVariable {
  name: string;
  value: string;
}

interface ServiceConfig {
  name: string;
  image: string;
  env?: Record<string, string>;
  resources?: {
    cpuLimit?: string;
    memoryLimit?: string;
  };
  volumes?: Array<{
    mountPath: string;
    sizeGb: number;
  }>;
  healthCheck?: {
    path: string;
    interval?: number;
    timeout?: number;
  };
}

export class RailwayClient {
  private apiKey: string;
  private baseUrl = 'https://backboard.railway.app/graphql';

  constructor(apiKey?: string) {
    this.apiKey = apiKey || process.env.RAILWAY_API_TOKEN || '';
    if (!this.apiKey) {
      throw new Error('Railway API key not provided. Set RAILWAY_API_TOKEN environment variable.');
    }
  }

  /**
   * Create a new Railway project
   */
  async createProject(
    name: string,
    description?: string,
    tags?: Record<string, string>
  ): Promise<RailwayProject> {
    const mutation = `
      mutation CreateProject($input: ProjectCreateInput!) {
        projectCreate(input: $input) {
          id
          name
          description
        }
      }
    `;

    const variables = {
      input: {
        name,
        description,
        ...(tags && { tags })
      }
    };

    const result = await this.graphql(mutation, variables);
    return result.projectCreate;
  }

  /**
   * Delete a Railway project
   */
  async deleteProject(projectId: string): Promise<boolean> {
    const mutation = `
      mutation DeleteProject($id: String!) {
        projectDelete(id: $id)
      }
    `;

    const result = await this.graphql(mutation, { id: projectId });
    return result.projectDelete;
  }

  /**
   * Create a service within a project
   */
  async createService(
    projectId: string,
    config: ServiceConfig
  ): Promise<RailwayService> {
    const mutation = `
      mutation CreateService($input: ServiceCreateInput!) {
        serviceCreate(input: $input) {
          id
          name
          projectId
        }
      }
    `;

    const variables = {
      input: {
        projectId,
        name: config.name,
        source: {
          image: config.image
        },
        ...(config.resources && { resources: config.resources }),
        ...(config.volumes && { volumes: config.volumes }),
        ...(config.healthCheck && { healthCheck: config.healthCheck })
      }
    };

    const service = await this.graphql(mutation, variables);

    // Set environment variables if provided
    if (config.env) {
      await this.setEnvironmentVariables(service.serviceCreate.id, config.env);
    }

    return service.serviceCreate;
  }

  /**
   * Delete a service
   */
  async deleteService(serviceId: string): Promise<boolean> {
    const mutation = `
      mutation DeleteService($id: String!) {
        serviceDelete(id: $id)
      }
    `;

    const result = await this.graphql(mutation, { id: serviceId });
    return result.serviceDelete;
  }

  /**
   * Set environment variables for a service
   */
  async setEnvironmentVariables(
    serviceId: string,
    env: Record<string, string>
  ): Promise<void> {
    const promises = Object.entries(env).map(([key, value]) => {
      const mutation = `
        mutation SetVariable($input: VariableUpsertInput!) {
          variableUpsert(input: $input) {
            id
            name
            value
          }
        }
      `;

      return this.graphql(mutation, {
        input: {
          serviceId,
          name: key,
          value
        }
      });
    });

    await Promise.all(promises);
  }

  /**
   * Get environment variables for a service
   */
  async getEnvironmentVariables(serviceId: string): Promise<EnvironmentVariable[]> {
    const query = `
      query GetVariables($serviceId: String!) {
        variables(serviceId: $serviceId) {
          edges {
            node {
              name
              value
            }
          }
        }
      }
    `;

    const result = await this.graphql(query, { serviceId });
    return result.variables.edges.map((edge: any) => edge.node);
  }

  /**
   * Deploy a service
   */
  async deployService(serviceId: string): Promise<Deployment> {
    const mutation = `
      mutation Deploy($serviceId: String!) {
        serviceDeploy(serviceId: $serviceId) {
          id
          status
          createdAt
        }
      }
    `;

    const result = await this.graphql(mutation, { serviceId });
    return result.serviceDeploy;
  }

  /**
   * Get deployment status
   */
  async getDeploymentStatus(deploymentId: string): Promise<DeploymentStatus> {
    const query = `
      query GetDeployment($id: String!) {
        deployment(id: $id) {
          id
          status
          url
          staticUrl
        }
      }
    `;

    const result = await this.graphql(query, { id: deploymentId });
    return result.deployment;
  }

  /**
   * Get service details
   */
  async getService(serviceId: string): Promise<RailwayService> {
    const query = `
      query GetService($id: String!) {
        service(id: $id) {
          id
          name
          projectId
          domains {
            domain
            serviceId
          }
        }
      }
    `;

    const result = await this.graphql(query, { id: serviceId });
    const service = result.service;

    // Extract URLs from domains
    if (service.domains && service.domains.length > 0) {
      service.publicUrl = `https://${service.domains[0].domain}`;
    }

    return service;
  }

  /**
   * Get all services in a project
   */
  async getProjectServices(projectId: string): Promise<RailwayService[]> {
    const query = `
      query GetProject($id: String!) {
        project(id: $id) {
          services {
            edges {
              node {
                id
                name
              }
            }
          }
        }
      }
    `;

    const result = await this.graphql(query, { id: projectId });
    return result.project.services.edges.map((edge: any) => edge.node);
  }

  /**
   * Wait for deployment to complete
   */
  async waitForDeployment(
    deploymentId: string,
    timeoutSeconds: number = 300
  ): Promise<DeploymentStatus> {
    const startTime = Date.now();
    const pollInterval = 10000; // 10 seconds

    while (true) {
      const status = await this.getDeploymentStatus(deploymentId);

      // Terminal states
      if (status.status === 'SUCCESS') {
        return status;
      }

      if (status.status === 'FAILED' || status.status === 'CRASHED') {
        throw new Error(`Deployment failed: ${status.status}`);
      }

      // Check timeout
      const elapsed = (Date.now() - startTime) / 1000;
      if (elapsed > timeoutSeconds) {
        throw new Error(`Deployment timeout after ${timeoutSeconds}s`);
      }

      // Wait before next poll
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
  }

  /**
   * Set custom domain for service
   */
  async setCustomDomain(serviceId: string, domain: string): Promise<void> {
    const mutation = `
      mutation CreateDomain($input: CustomDomainCreateInput!) {
        customDomainCreate(input: $input) {
          id
          domain
        }
      }
    `;

    await this.graphql(mutation, {
      input: {
        serviceId,
        domain
      }
    });
  }

  /**
   * Get project by name
   */
  async getProjectByName(name: string): Promise<RailwayProject | null> {
    const query = `
      query GetProjects {
        projects {
          edges {
            node {
              id
              name
              description
            }
          }
        }
      }
    `;

    const result = await this.graphql(query, {});
    const projects = result.projects.edges.map((edge: any) => edge.node);
    return projects.find((p: RailwayProject) => p.name === name) || null;
  }

  /**
   * Execute GraphQL query/mutation
   */
  private async graphql(query: string, variables: any): Promise<any> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`
      },
      body: JSON.stringify({ query, variables })
    });

    if (!response.ok) {
      throw new Error(`Railway API HTTP error: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();

    if (result.errors) {
      const errorMessages = result.errors.map((e: any) => e.message).join(', ');
      throw new Error(`Railway API GraphQL error: ${errorMessages}`);
    }

    return result.data;
  }

  /**
   * Health check - verify API connectivity
   */
  async healthCheck(): Promise<boolean> {
    try {
      const query = `
        query Me {
          me {
            id
            email
          }
        }
      `;

      await this.graphql(query, {});
      return true;
    } catch (error) {
      return false;
    }
  }
}

// Export types for external use
export type {
  RailwayProject,
  RailwayService,
  Deployment,
  DeploymentStatus,
  EnvironmentVariable,
  ServiceConfig
};
