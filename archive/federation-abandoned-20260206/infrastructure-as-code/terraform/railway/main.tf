# Railway Infrastructure for Federation Platform
# Creates department-specific Railway projects with PostgreSQL and Voice Agent services

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
    }
  }
}

# Generate secure PostgreSQL password
resource "random_password" "postgres" {
  length  = 32
  special = true
}

# Generate secure JWT secret for department
resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

# Railway Project
resource "railway_project" "department" {
  name        = "aio-${var.department_id}-${var.environment}"
  description = "AIO Voice Assistant for ${var.department_name} Department"

  tags = {
    department  = var.department_id
    environment = var.environment
    managed_by  = "federation-platform"
    cost_center = var.cost_center
    created_at  = timestamp()
  }
}

# PostgreSQL Service
resource "railway_service" "postgres" {
  project_id = railway_project.department.id
  name       = "postgres-${var.department_id}"

  source = {
    image = "postgres:15-alpine"
  }

  env = {
    POSTGRES_DB       = var.department_id
    POSTGRES_USER     = var.department_id
    POSTGRES_PASSWORD = random_password.postgres.result
  }

  volumes = [
    {
      mount_path = "/var/lib/postgresql/data"
      size_gb    = var.postgres_storage_gb
    }
  ]

  resources = {
    cpu_limit    = var.postgres_cpu
    memory_limit = var.postgres_memory
  }

  restart_policy = {
    type        = "on_failure"
    max_retries = 3
  }

  tags = {
    service_type = "database"
    department   = var.department_id
  }
}

# AIO Voice Agent Service
resource "railway_service" "voice_agent" {
  project_id = railway_project.department.id
  name       = "voice-agent-${var.department_id}"

  source = {
    image = "${var.docker_registry}/aio-federation-template:${var.image_version}"
  }

  env = {
    # Department Configuration
    DEPARTMENT_NAME = var.department_name
    DEPARTMENT_ID   = var.department_id
    DB_SCHEMA       = "${var.department_id}_tenant"

    # Database Connection
    POSTGRES_URL = "postgresql://${var.department_id}:${random_password.postgres.result}@${railway_service.postgres.private_dns}:5432/${var.department_id}"

    # n8n Webhooks
    N8N_WEBHOOK_BASE = var.n8n_webhook_base

    # LiveKit Configuration
    LIVEKIT_URL        = var.livekit_url
    LIVEKIT_API_KEY    = var.livekit_api_key
    LIVEKIT_API_SECRET = var.livekit_api_secret

    # LLM Configuration (Cerebras)
    CEREBRAS_API_KEY    = var.cerebras_api_key
    CEREBRAS_MODEL      = var.cerebras_model
    CEREBRAS_TEMPERATURE = var.cerebras_temperature
    CEREBRAS_MAX_TOKENS = var.cerebras_max_tokens

    # STT Configuration (Deepgram)
    DEEPGRAM_API_KEY = var.deepgram_api_key
    DEEPGRAM_MODEL   = var.deepgram_model

    # TTS Configuration (Cartesia)
    CARTESIA_API_KEY = var.cartesia_api_key
    CARTESIA_MODEL   = var.cartesia_model
    CARTESIA_VOICE   = var.cartesia_voice

    # Enabled Tools
    ENABLED_TOOLS = jsonencode(var.enabled_tools)

    # Logging
    LOG_LEVEL = var.log_level

    # JWT Secret
    JWT_SECRET = random_password.jwt_secret.result
  }

  resources = {
    cpu_limit    = var.voice_agent_cpu
    memory_limit = var.voice_agent_memory

    autoscaling = {
      enabled         = var.autoscaling_enabled
      min_instances   = var.autoscaling_min_instances
      max_instances   = var.autoscaling_max_instances
      cpu_threshold   = var.autoscaling_cpu_threshold
      memory_threshold = var.autoscaling_memory_threshold
    }
  }

  health_check = {
    path     = "/health"
    interval = 30
    timeout  = 10
    retries  = 3
  }

  restart_policy = {
    type        = "on_failure"
    max_retries = 3
  }

  depends_on = [railway_service.postgres]

  tags = {
    service_type = "voice_agent"
    department   = var.department_id
  }
}

# Custom Domain (optional)
resource "railway_custom_domain" "voice_agent" {
  count      = var.custom_domain != "" ? 1 : 0
  service_id = railway_service.voice_agent.id
  domain     = "${var.department_id}.${var.custom_domain}"

  ssl = {
    enabled = true
    auto_renew = true
  }
}

# Environment Variables Secret Reference
# Store sensitive values in Railway's secret manager
resource "railway_variable" "oauth_credentials" {
  for_each = var.oauth_credentials

  service_id = railway_service.voice_agent.id
  name       = each.key
  value      = each.value
  is_secret  = true
}

# Monitoring Configuration
resource "railway_service" "monitoring" {
  count      = var.monitoring_enabled ? 1 : 0
  project_id = railway_project.department.id
  name       = "monitoring-${var.department_id}"

  source = {
    image = "prom/prometheus:latest"
  }

  env = {
    SCRAPE_TARGETS = jsonencode([
      "${railway_service.voice_agent.private_dns}:8080/metrics"
    ])
  }

  resources = {
    cpu_limit    = "500m"
    memory_limit = "512Mi"
  }
}

# Backup Configuration
resource "railway_backup_schedule" "postgres_backup" {
  count      = var.backup_enabled ? 1 : 0
  service_id = railway_service.postgres.id

  schedule = var.backup_schedule # Cron format: "0 2 * * *"
  retention_days = var.backup_retention_days

  backup_location = {
    provider = "s3"
    bucket   = var.backup_s3_bucket
    region   = var.backup_s3_region
  }
}
