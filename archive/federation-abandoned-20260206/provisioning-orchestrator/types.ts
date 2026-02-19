/**
 * Core type definitions for the Federation Provisioning Orchestrator
 */

export enum ProvisioningState {
  PENDING = 'pending',
  VALIDATING = 'validating',
  CREATING_DATABASE = 'creating_database',
  CREATING_OAUTH = 'creating_oauth',
  DEPLOYING_CONTAINER = 'deploying_container',
  DEPLOYING_WORKFLOWS = 'deploying_workflows',
  CONFIGURING_GATEWAY = 'configuring_gateway',
  VALIDATING_DEPLOYMENT = 'validating_deployment',
  COMPLETED = 'completed',
  FAILED = 'failed',
  ROLLING_BACK = 'rolling_back'
}

export enum ComponentState {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export interface DepartmentConfig {
  departmentName: string;
  departmentId: string;
  businessType?: string;
  workflows: string[];
  dataRetention: string;
  region: string;
  resources?: {
    cpu: string;
    memory: string;
  };
  adminEmail: string;
  googleWorkspaceDomain?: string;
  enabledTools?: string[];
  customConfig?: Record<string, any>;
}

export interface ProvisioningProgress {
  database: ComponentState;
  railway: ComponentState;
  docker: ComponentState;
  n8n: ComponentState;
  oauth: ComponentState;
}

export interface ProvisioningJob {
  id: string;
  departmentId: string;
  status: ProvisioningState;
  progress: ProvisioningProgress;
  currentStep: string;
  startedAt: Date;
  estimatedCompletion: Date;
  completedAt?: Date;
  logs: string[];
  errorMessage?: string;
  rollbackSteps?: string[];
}

export interface ProvisioningResult {
  provisioningId: string;
  departmentId: string;
  status: ProvisioningState;
  deploymentUrl?: string;
  dashboardUrl?: string;
  errorMessage?: string;
}

export interface DatabaseResult {
  tenantSchema: string;
  success: boolean;
  error?: string;
}

export interface OAuthResult {
  clientId: string;
  credentialId: string;
  success: boolean;
  error?: string;
}

export interface ContainerResult {
  projectId: string;
  deploymentUrl: string;
  serviceId: string;
  success: boolean;
  error?: string;
}

export interface WorkflowResult {
  workflowIds: Record<string, string>;
  webhookUrls: Record<string, string>;
  success: boolean;
  error?: string;
}

export interface GatewayResult {
  routeConfigured: boolean;
  success: boolean;
  error?: string;
}

export interface HealthCheck {
  name: string;
  healthy: boolean;
  latency?: number;
  error?: string;
}

export interface Department {
  id: string;
  departmentId: string;
  departmentName: string;
  status: 'PROVISIONING' | 'ACTIVE' | 'DEPROVISIONING' | 'FAILED' | 'DEPROVISIONED';
  tenantSchema: string;
  railwayProjectId?: string;
  railwayDeploymentUrl?: string;
  n8nWorkflowIds?: Record<string, string>;
  enabledTools?: string[];
  adminEmail: string;
  config?: DepartmentConfig;
  createdAt: Date;
  updatedAt: Date;
  deprovisionedAt?: Date;
}

export interface StateTransition {
  from: ProvisioningState;
  to: ProvisioningState;
  timestamp: Date;
  reason?: string;
}

export interface RollbackContext {
  provisioningId: string;
  completedSteps: string[];
  failedStep: string;
  error: string;
}
