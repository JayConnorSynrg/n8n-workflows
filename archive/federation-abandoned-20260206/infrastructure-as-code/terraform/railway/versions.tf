# Terraform Provider Versions

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

  # Backend configuration for state management
  # Uncomment and configure based on your state storage preference

  # backend "s3" {
  #   bucket         = "federation-terraform-state"
  #   key            = "railway/departments/${var.department_id}/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }

  # backend "gcs" {
  #   bucket = "federation-terraform-state"
  #   prefix = "railway/departments/${var.department_id}"
  # }

  # backend "azurerm" {
  #   resource_group_name  = "federation-terraform"
  #   storage_account_name = "federationtfstate"
  #   container_name       = "tfstate"
  #   key                  = "railway/departments/${var.department_id}.tfstate"
  # }
}

# Railway provider configuration
provider "railway" {
  # Authentication via RAILWAY_API_TOKEN environment variable
  # Set via: export RAILWAY_API_TOKEN="your_token_here"
}

# Random provider configuration
provider "random" {}
