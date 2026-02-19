/**
 * N8N Workflow Templating System - Type Definitions
 * Version: 1.0.0
 */

// ============================================================================
// Template System Types
// ============================================================================

export interface TemplateVariables {
  // Department context
  DEPARTMENT_NAME: string;          // "Legal", "HR", etc.
  DEPARTMENT_ID: string;            // "legal", "hr", etc.

  // Credentials (OAuth, API keys)
  POSTGRES_CREDENTIAL_ID: string;
  GOOGLE_DRIVE_CREDENTIAL_ID: string;
  GMAIL_CREDENTIAL_ID: string;
  OPENAI_CREDENTIAL_ID: string;
  GOOGLE_SHEETS_CREDENTIAL_ID?: string;
  GOOGLE_DOCS_CREDENTIAL_ID?: string;

  // Webhook URLs
  N8N_WEBHOOK_BASE: string;         // "https://legal.mycompany.app.n8n.cloud/webhook"

  // Database
  POSTGRES_SCHEMA: string;          // "legal_schema"

  // Voice agent
  VOICE_AGENT_URL?: string;         // "https://legal-abc123.railway.app"
  VOICE_AGENT_API_KEY?: string;

  // Workflow IDs (for Execute Workflow nodes)
  [key: `WORKFLOW_ID_${string}`]: string;
}

export interface WorkflowTemplate {
  id: string;                       // Template ID (e.g., "google-drive-repository")
  workflow: N8nWorkflow;            // n8n workflow with Handlebars variables
  meta: WorkflowMetadata;           // Metadata describing requirements
}

export interface WorkflowMetadata {
  templateId: string;               // Same as WorkflowTemplate.id
  name: string;                     // Human-readable name
  category: 'core' | 'hr' | 'sales-marketing' | 'operations' | 'finance' | 'legal';
  requiredCredentials: RequiredCredential[];
  requiredWebhooks: WebhookDefinition[];
  dependencies: string[];           // Other template IDs this depends on
  description: string;
  estimatedExecutionTime?: string;  // "2-5 seconds"
  dataRetentionDays?: number;
}

export interface RequiredCredential {
  type: string;                     // n8n credential type (e.g., "postgres", "googleDriveOAuth2Api")
  namePattern: string;              // "{DEPARTMENT}_drive_oauth"
  optional?: boolean;
}

export interface WebhookDefinition {
  path: string;                     // "/drive-repository"
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
}

// ============================================================================
// N8N Workflow Types
// ============================================================================

export interface N8nWorkflow {
  id?: string;
  name: string;
  nodes: N8nNode[];
  connections: N8nConnections;
  settings?: N8nWorkflowSettings;
  staticData?: any;
  tags?: N8nTag[];
  active?: boolean;
}

export interface N8nNode {
  id: string;
  name: string;
  type: string;
  typeVersion: number;
  position: [number, number];
  parameters: Record<string, any>;
  credentials?: Record<string, N8nCredentialReference>;
  disabled?: boolean;
  continueOnFail?: boolean;
  retryOnFail?: boolean;
  maxTries?: number;
  waitBetweenTries?: number;
  notes?: string;
  webhookId?: string;
  onError?: 'continueErrorOutput' | 'continueRegularOutput' | 'stopWorkflow';
}

export interface N8nCredentialReference {
  id: string;
  name: string;
}

export interface N8nConnections {
  [nodeName: string]: {
    main?: N8nConnection[][];
  };
}

export interface N8nConnection {
  node: string;
  type: 'main';
  index: number;
}

export interface N8nWorkflowSettings {
  executionOrder?: 'v0' | 'v1';
  timezone?: string;
  saveDataErrorExecution?: 'all' | 'none';
  saveDataSuccessExecution?: 'all' | 'none';
  saveExecutionProgress?: boolean;
  saveManualExecutions?: boolean;
  errorWorkflow?: string;
  executionTimeout?: number;
}

export interface N8nTag {
  id: string;
  name: string;
  createdAt?: string;
  updatedAt?: string;
}

// ============================================================================
// Deployment Types
// ============================================================================

export interface DeploymentConfig {
  department: string;               // "hr"
  departmentName: string;           // "Human Resources"
  templates: string[];              // Template IDs to deploy
  variables: TemplateVariables;
  n8nApiKey: string;
  n8nBaseUrl: string;               // "https://jayconnorexe.app.n8n.cloud"
}

export interface DeploymentResult {
  department: string;
  deployedCount: number;
  workflows: DeployedWorkflow[];
  success: boolean;
  errors?: DeploymentError[];
}

export interface DeployedWorkflow {
  templateId: string;
  workflowId: string;               // n8n workflow ID
  name: string;
  active: boolean;
  webhookUrls?: string[];
}

export interface DeploymentError {
  templateId: string;
  error: string;
  phase: 'injection' | 'validation' | 'deployment';
}

// ============================================================================
// Validation Types
// ============================================================================

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  suggestions?: string[];
}

export interface ValidationError {
  type: 'unreplaced_variable' | 'invalid_credential' | 'invalid_webhook' | 'missing_dependency' | 'invalid_connection';
  message: string;
  nodeId?: string;
  nodeName?: string;
  field?: string;
}

export interface ValidationWarning {
  type: 'missing_error_handling' | 'deprecated_type_version' | 'performance';
  message: string;
  nodeId?: string;
  nodeName?: string;
}

// ============================================================================
// Dependency Resolution Types
// ============================================================================

export interface WorkflowDependency {
  workflowId: string;
  dependsOn: string[];              // Other workflow IDs
}

export interface DependencyGraph {
  nodes: Map<string, string[]>;     // workflowId -> dependencies
  inDegree: Map<string, number>;    // workflowId -> number of dependencies
}

// ============================================================================
// Template Conversion Types
// ============================================================================

export interface ConversionConfig {
  workflowId: string;               // n8n workflow ID
  category: WorkflowMetadata['category'];
  outputDir: string;                // Where to save template
}

export interface ConversionResult {
  templateId: string;
  workflow: N8nWorkflow;
  metadata: WorkflowMetadata;
  conversions: ConversionOperation[];
}

export interface ConversionOperation {
  type: 'credential_templatized' | 'webhook_templatized' | 'schema_templatized' | 'url_templatized';
  original: string;
  template: string;
  nodeId: string;
}

// ============================================================================
// N8N API Client Types
// ============================================================================

export interface N8nClientConfig {
  baseUrl: string;
  apiKey: string;
  timeout?: number;                 // Request timeout in ms
}

export interface N8nListResponse<T> {
  data: T[];
  nextCursor?: string;
}

export interface N8nWorkflowListItem {
  id: string;
  name: string;
  active: boolean;
  tags: N8nTag[];
  createdAt: string;
  updatedAt: string;
}

export interface N8nCredential {
  id: string;
  name: string;
  type: string;
  createdAt: string;
  updatedAt: string;
}

// ============================================================================
// Utility Types
// ============================================================================

export type TemplateCategory = WorkflowMetadata['category'];

export interface TemplateLibrary {
  core: WorkflowTemplate[];
  hr: WorkflowTemplate[];
  'sales-marketing': WorkflowTemplate[];
  operations: WorkflowTemplate[];
  finance: WorkflowTemplate[];
  legal: WorkflowTemplate[];
}

export interface CredentialMapping {
  [credentialType: string]: string; // credentialType -> credentialId
}

// ============================================================================
// Error Types
// ============================================================================

export class TemplateError extends Error {
  constructor(
    message: string,
    public templateId: string,
    public phase: 'injection' | 'validation' | 'deployment'
  ) {
    super(message);
    this.name = 'TemplateError';
  }
}

export class ValidationError extends Error {
  constructor(
    message: string,
    public errors: ValidationError[]
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

export class DeploymentError extends Error {
  constructor(
    message: string,
    public templateId: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'DeploymentError';
  }
}

export class CircularDependencyError extends Error {
  constructor(
    message: string,
    public cycle: string[]
  ) {
    super(message);
    this.name = 'CircularDependencyError';
  }
}
