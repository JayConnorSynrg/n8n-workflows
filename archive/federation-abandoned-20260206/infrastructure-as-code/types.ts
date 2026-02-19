/**
 * TypeScript Type Definitions for Federation Infrastructure as Code
 */

// ============================================================================
// DEPLOYMENT CONFIGURATION
// ============================================================================

export interface DepartmentConfig {
  // Identity
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

  // Cerebras (LLM)
  cerebrasApiKey: string;
  cerebrasModel: 'llama-3.3-70b' | 'llama-3.1-70b' | 'llama-3.1-8b';
  cerebrasTemperature: string;
  cerebrasMaxTokens: string;

  // Deepgram (STT)
  deepgramApiKey: string;
  deepgramModel: string;

  // Cartesia (TTS)
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
  autoscaling?: AutoscalingConfig;
  backup?: BackupConfig;
}

export interface AutoscalingConfig {
  enabled: boolean;
  minInstances: number;
  maxInstances: number;
  cpuThreshold: number;
  memoryThreshold: number;
}

export interface BackupConfig {
  enabled: boolean;
  schedule: string; // Cron format
  retentionDays: number;
  s3Bucket?: string;
  s3Region?: string;
}

// ============================================================================
// DEPLOYMENT RESULTS
// ============================================================================

export interface DeploymentResult {
  success: boolean;
  projectId?: string;
  voiceAgentUrl?: string;
  duration: number;
  error?: string;
  output?: string;
  metadata?: DeploymentMetadata;
}

export interface DeploymentMetadata {
  target: 'railway' | 'vps';
  timestamp: string;
  departmentId: string;
  environment: string;
  version: string;
  resources: ResourceAllocation;
}

export interface ResourceAllocation {
  postgres: {
    cpu: string;
    memory: string;
    storage: string;
  };
  voiceAgent: {
    cpu: string;
    memory: string;
  };
}

// ============================================================================
// RAILWAY API TYPES
// ============================================================================

export interface RailwayProject {
  id: string;
  name: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
  tags?: Record<string, string>;
}

export interface RailwayService {
  id: string;
  name: string;
  projectId: string;
  privateUrl?: string;
  publicUrl?: string;
  privateDns?: string;
  createdAt?: string;
  status?: ServiceStatus;
}

export type ServiceStatus =
  | 'INITIALIZING'
  | 'RUNNING'
  | 'STOPPED'
  | 'CRASHED'
  | 'DEPLOYING';

export interface Deployment {
  id: string;
  status: DeploymentStatus;
  createdAt: string;
  completedAt?: string;
  url?: string;
  error?: string;
}

export type DeploymentStatus =
  | 'QUEUED'
  | 'BUILDING'
  | 'DEPLOYING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CRASHED';

export interface EnvironmentVariable {
  name: string;
  value: string;
  isSecret?: boolean;
}

export interface ServiceConfig {
  name: string;
  image: string;
  env?: Record<string, string>;
  resources?: {
    cpuLimit?: string;
    memoryLimit?: string;
    autoscaling?: {
      enabled: boolean;
      minInstances: number;
      maxInstances: number;
      cpuThreshold: number;
    };
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

// ============================================================================
// ANSIBLE TYPES
// ============================================================================

export interface AnsiblePlaybookResult {
  success: boolean;
  output: string;
  duration: number;
  stats: {
    ok: number;
    changed: number;
    unreachable: number;
    failed: number;
    skipped: number;
    rescued: number;
    ignored: number;
  };
}

export interface VPSHost {
  hostname: string;
  ipAddress: string;
  sshPort: number;
  sshUser: string;
  departments: string[];
}

export interface VPSInventory {
  environment: 'dev' | 'staging' | 'prod';
  hosts: VPSHost[];
  globalVars: Record<string, string>;
}

// ============================================================================
// TERRAFORM TYPES
// ============================================================================

export interface TerraformState {
  version: number;
  terraform_version: string;
  serial: number;
  lineage: string;
  outputs: Record<string, TerraformOutput>;
  resources: TerraformResource[];
}

export interface TerraformOutput {
  value: any;
  type: string;
  sensitive?: boolean;
}

export interface TerraformResource {
  mode: 'managed' | 'data';
  type: string;
  name: string;
  provider: string;
  instances: Array<{
    schema_version: number;
    attributes: Record<string, any>;
  }>;
}

export interface TerraformPlan {
  format_version: string;
  terraform_version: string;
  variables: Record<string, any>;
  planned_values: {
    root_module: {
      resources: TerraformResource[];
    };
  };
  resource_changes: Array<{
    address: string;
    mode: 'managed' | 'data';
    type: string;
    name: string;
    change: {
      actions: ('create' | 'update' | 'delete' | 'read' | 'no-op')[];
      before: any;
      after: any;
    };
  }>;
}

// ============================================================================
// MONITORING TYPES
// ============================================================================

export interface HealthCheckResult {
  healthy: boolean;
  timestamp: string;
  checks: {
    database: boolean;
    livekit: boolean;
    llm: boolean;
    stt: boolean;
    tts: boolean;
    n8n: boolean;
  };
  latency: {
    database: number;
    health_endpoint: number;
  };
  error?: string;
}

export interface DeploymentMetrics {
  departmentId: string;
  uptime: number; // seconds
  requestCount: number;
  errorCount: number;
  avgLatency: number; // ms
  p95Latency: number; // ms
  p99Latency: number; // ms
  memoryUsage: number; // MB
  cpuUsage: number; // percentage
}

// ============================================================================
// ERROR TYPES
// ============================================================================

export class DeploymentError extends Error {
  constructor(
    message: string,
    public code: DeploymentErrorCode,
    public details?: any
  ) {
    super(message);
    this.name = 'DeploymentError';
  }
}

export enum DeploymentErrorCode {
  INVALID_CONFIG = 'INVALID_CONFIG',
  RAILWAY_API_ERROR = 'RAILWAY_API_ERROR',
  ANSIBLE_ERROR = 'ANSIBLE_ERROR',
  TIMEOUT = 'TIMEOUT',
  HEALTH_CHECK_FAILED = 'HEALTH_CHECK_FAILED',
  INSUFFICIENT_RESOURCES = 'INSUFFICIENT_RESOURCES',
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
}

// ============================================================================
// VALIDATION TYPES
// ============================================================================

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

export interface ValidationWarning {
  field: string;
  message: string;
  severity: 'low' | 'medium' | 'high';
}

// ============================================================================
// CLI TYPES
// ============================================================================

export interface CLIOptions {
  command: 'deploy' | 'list' | 'delete' | 'status' | 'logs';
  target?: 'railway' | 'vps';
  configFile?: string;
  environment?: 'dev' | 'staging' | 'prod';
  departmentId?: string;
  projectId?: string;
  verbose?: boolean;
  dryRun?: boolean;
}

export interface CLIResult {
  success: boolean;
  message: string;
  data?: any;
  error?: Error;
}
