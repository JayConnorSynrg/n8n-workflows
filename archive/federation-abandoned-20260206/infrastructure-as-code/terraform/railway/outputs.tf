# Terraform Outputs for Railway Department Deployment

# ============================================================================
# PROJECT OUTPUTS
# ============================================================================

output "project_id" {
  description = "Railway project ID"
  value       = railway_project.department.id
}

output "project_name" {
  description = "Railway project name"
  value       = railway_project.department.name
}

output "environment" {
  description = "Deployment environment"
  value       = var.environment
}

# ============================================================================
# SERVICE OUTPUTS
# ============================================================================

output "postgres_service_id" {
  description = "PostgreSQL service ID"
  value       = railway_service.postgres.id
}

output "postgres_private_dns" {
  description = "PostgreSQL private DNS name"
  value       = railway_service.postgres.private_dns
}

output "voice_agent_service_id" {
  description = "Voice agent service ID"
  value       = railway_service.voice_agent.id
}

output "voice_agent_url" {
  description = "Voice agent public URL"
  value       = railway_service.voice_agent.public_url
}

output "voice_agent_private_dns" {
  description = "Voice agent private DNS name"
  value       = railway_service.voice_agent.private_dns
}

# ============================================================================
# CUSTOM DOMAIN
# ============================================================================

output "custom_domain" {
  description = "Custom domain for voice agent (if configured)"
  value       = var.custom_domain != "" ? "${var.department_id}.${var.custom_domain}" : null
}

output "custom_domain_validation" {
  description = "DNS validation records for custom domain"
  value       = var.custom_domain != "" ? railway_custom_domain.voice_agent[0].validation_records : null
}

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

output "postgres_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${var.department_id}:${random_password.postgres.result}@${railway_service.postgres.private_dns}:5432/${var.department_id}"
  sensitive   = true
}

output "postgres_password" {
  description = "PostgreSQL password (sensitive)"
  value       = random_password.postgres.result
  sensitive   = true
}

# ============================================================================
# JWT SECRET
# ============================================================================

output "jwt_secret" {
  description = "JWT secret for department (sensitive)"
  value       = random_password.jwt_secret.result
  sensitive   = true
}

# ============================================================================
# DEPLOYMENT STATUS
# ============================================================================

output "deployment_summary" {
  description = "Deployment summary"
  value = {
    department_id   = var.department_id
    department_name = var.department_name
    environment     = var.environment
    project_id      = railway_project.department.id
    voice_agent_url = railway_service.voice_agent.public_url
    enabled_tools   = var.enabled_tools
    autoscaling     = {
      enabled       = var.autoscaling_enabled
      min_instances = var.autoscaling_min_instances
      max_instances = var.autoscaling_max_instances
    }
    backup_enabled  = var.backup_enabled
    monitoring_enabled = var.monitoring_enabled
  }
}

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

output "health_check_url" {
  description = "Health check endpoint URL"
  value       = "${railway_service.voice_agent.public_url}/health"
}

# ============================================================================
# RESOURCE ALLOCATION
# ============================================================================

output "resource_allocation" {
  description = "Resource allocation summary"
  value = {
    postgres = {
      cpu     = var.postgres_cpu
      memory  = var.postgres_memory
      storage = "${var.postgres_storage_gb}GB"
    }
    voice_agent = {
      cpu    = var.voice_agent_cpu
      memory = var.voice_agent_memory
    }
  }
}

# ============================================================================
# ESTIMATED MONTHLY COST
# ============================================================================

output "estimated_monthly_cost" {
  description = "Estimated monthly cost (USD)"
  value = {
    base_cost       = 150 # Base Railway plan
    postgres_cost   = var.postgres_storage_gb > 10 ? (var.postgres_storage_gb - 10) * 0.25 : 0
    autoscaling_cost = var.autoscaling_enabled ? (var.autoscaling_max_instances - 1) * 100 : 0
    total_min       = 150 + (var.postgres_storage_gb > 10 ? (var.postgres_storage_gb - 10) * 0.25 : 0)
    total_max       = 150 + (var.postgres_storage_gb > 10 ? (var.postgres_storage_gb - 10) * 0.25 : 0) + (var.autoscaling_enabled ? (var.autoscaling_max_instances - 1) * 100 : 0)
  }
}

# ============================================================================
# TAGS
# ============================================================================

output "tags" {
  description = "Applied tags"
  value = {
    department  = var.department_id
    environment = var.environment
    managed_by  = "federation-platform"
    cost_center = var.cost_center
  }
}
