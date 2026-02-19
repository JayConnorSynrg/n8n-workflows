# Terraform Variables for Railway Department Deployment

# ============================================================================
# DEPARTMENT CONFIGURATION
# ============================================================================

variable "department_name" {
  description = "Human-readable department name (e.g., 'Human Resources')"
  type        = string

  validation {
    condition     = length(var.department_name) > 0 && length(var.department_name) <= 100
    error_message = "Department name must be between 1 and 100 characters"
  }
}

variable "department_id" {
  description = "Department identifier slug (lowercase, alphanumeric, hyphens only)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.department_id))
    error_message = "Department ID must be lowercase alphanumeric with hyphens only"
  }
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "cost_center" {
  description = "Cost center code for billing and cost allocation"
  type        = string
  default     = ""
}

# ============================================================================
# DOCKER CONFIGURATION
# ============================================================================

variable "docker_registry" {
  description = "Docker registry URL for AIO agent images"
  type        = string
  default     = "ghcr.io/synrgscaling"
}

variable "image_version" {
  description = "AIO template Docker image version tag"
  type        = string
  default     = "latest"
}

# ============================================================================
# N8N CONFIGURATION
# ============================================================================

variable "n8n_webhook_base" {
  description = "n8n webhook base URL (e.g., https://jayconnorexe.app.n8n.cloud/webhook)"
  type        = string
}

# ============================================================================
# LIVEKIT CONFIGURATION
# ============================================================================

variable "livekit_url" {
  description = "LiveKit WebRTC server URL (wss://...)"
  type        = string
}

variable "livekit_api_key" {
  description = "LiveKit API key"
  type        = string
  sensitive   = true
}

variable "livekit_api_secret" {
  description = "LiveKit API secret"
  type        = string
  sensitive   = true
}

# ============================================================================
# LLM CONFIGURATION (Cerebras)
# ============================================================================

variable "cerebras_api_key" {
  description = "Cerebras LLM API key"
  type        = string
  sensitive   = true
}

variable "cerebras_model" {
  description = "Cerebras LLM model name"
  type        = string
  default     = "llama-3.3-70b"

  validation {
    condition     = contains(["llama-3.3-70b", "llama-3.1-70b", "llama-3.1-8b"], var.cerebras_model)
    error_message = "Cerebras model must be llama-3.3-70b, llama-3.1-70b, or llama-3.1-8b"
  }
}

variable "cerebras_temperature" {
  description = "LLM temperature (0.0-1.0)"
  type        = string
  default     = "0.6"
}

variable "cerebras_max_tokens" {
  description = "Maximum tokens per LLM response"
  type        = string
  default     = "150"
}

# ============================================================================
# STT CONFIGURATION (Deepgram)
# ============================================================================

variable "deepgram_api_key" {
  description = "Deepgram STT API key"
  type        = string
  sensitive   = true
}

variable "deepgram_model" {
  description = "Deepgram STT model name"
  type        = string
  default     = "nova-3"
}

# ============================================================================
# TTS CONFIGURATION (Cartesia)
# ============================================================================

variable "cartesia_api_key" {
  description = "Cartesia TTS API key"
  type        = string
  sensitive   = true
}

variable "cartesia_model" {
  description = "Cartesia TTS model name"
  type        = string
  default     = "sonic-3"
}

variable "cartesia_voice" {
  description = "Cartesia voice ID"
  type        = string
  default     = "a167e0f3-df7e-4d52-a9c3-f949145efdab" # Default professional voice
}

# ============================================================================
# ENABLED TOOLS
# ============================================================================

variable "enabled_tools" {
  description = "List of enabled tools for the voice assistant"
  type        = list(string)
  default     = ["email", "google_drive", "database", "vector_store", "agent_context"]

  validation {
    condition     = length(var.enabled_tools) > 0
    error_message = "At least one tool must be enabled"
  }
}

# ============================================================================
# RESOURCE ALLOCATION - PostgreSQL
# ============================================================================

variable "postgres_cpu" {
  description = "PostgreSQL CPU allocation (millicores)"
  type        = string
  default     = "1000m" # 1 vCPU
}

variable "postgres_memory" {
  description = "PostgreSQL memory allocation"
  type        = string
  default     = "2048Mi" # 2GB
}

variable "postgres_storage_gb" {
  description = "PostgreSQL storage size in GB"
  type        = number
  default     = 10

  validation {
    condition     = var.postgres_storage_gb >= 5 && var.postgres_storage_gb <= 500
    error_message = "PostgreSQL storage must be between 5GB and 500GB"
  }
}

# ============================================================================
# RESOURCE ALLOCATION - Voice Agent
# ============================================================================

variable "voice_agent_cpu" {
  description = "Voice agent CPU allocation (millicores)"
  type        = string
  default     = "2000m" # 2 vCPUs
}

variable "voice_agent_memory" {
  description = "Voice agent memory allocation"
  type        = string
  default     = "4096Mi" # 4GB
}

# ============================================================================
# AUTOSCALING
# ============================================================================

variable "autoscaling_enabled" {
  description = "Enable autoscaling for voice agent"
  type        = bool
  default     = true
}

variable "autoscaling_min_instances" {
  description = "Minimum number of voice agent instances"
  type        = number
  default     = 1
}

variable "autoscaling_max_instances" {
  description = "Maximum number of voice agent instances"
  type        = number
  default     = 3

  validation {
    condition     = var.autoscaling_max_instances >= var.autoscaling_min_instances
    error_message = "Max instances must be >= min instances"
  }
}

variable "autoscaling_cpu_threshold" {
  description = "CPU threshold percentage for scaling up"
  type        = number
  default     = 70

  validation {
    condition     = var.autoscaling_cpu_threshold > 0 && var.autoscaling_cpu_threshold <= 100
    error_message = "CPU threshold must be between 1 and 100"
  }
}

variable "autoscaling_memory_threshold" {
  description = "Memory threshold percentage for scaling up"
  type        = number
  default     = 80

  validation {
    condition     = var.autoscaling_memory_threshold > 0 && var.autoscaling_memory_threshold <= 100
    error_message = "Memory threshold must be between 1 and 100"
  }
}

# ============================================================================
# NETWORKING
# ============================================================================

variable "custom_domain" {
  description = "Custom domain for voice agent (optional, base domain only)"
  type        = string
  default     = ""
}

# ============================================================================
# OAUTH CREDENTIALS
# ============================================================================

variable "oauth_credentials" {
  description = "OAuth credentials for Google Workspace (optional)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

# ============================================================================
# LOGGING
# ============================================================================

variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
  }
}

# ============================================================================
# MONITORING
# ============================================================================

variable "monitoring_enabled" {
  description = "Enable Prometheus monitoring"
  type        = bool
  default     = false
}

# ============================================================================
# BACKUP CONFIGURATION
# ============================================================================

variable "backup_enabled" {
  description = "Enable automated PostgreSQL backups"
  type        = bool
  default     = true
}

variable "backup_schedule" {
  description = "Backup schedule in cron format (default: daily at 2 AM UTC)"
  type        = string
  default     = "0 2 * * *"
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 365
    error_message = "Backup retention must be between 1 and 365 days"
  }
}

variable "backup_s3_bucket" {
  description = "S3 bucket name for backups"
  type        = string
  default     = ""
}

variable "backup_s3_region" {
  description = "S3 bucket region for backups"
  type        = string
  default     = "us-east-1"
}
