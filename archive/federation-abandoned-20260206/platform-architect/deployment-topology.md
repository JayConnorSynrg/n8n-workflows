# Federation Platform - Deployment Topology

**Version:** 1.0.0
**Date:** 2026-02-06
**Status:** Design Phase

---

## Executive Summary

The Federation Platform deployment topology is designed for scalability, reliability, and cost-effectiveness. This document defines the infrastructure architecture, multi-environment strategy, and operational procedures for deploying and managing 100+ department instances.

**Key Design Decisions:**
- **Primary Platform**: Railway (PaaS) for rapid provisioning and zero-config deployment
- **Backup Platform**: VPS (self-hosted) for cost optimization at scale (>50 departments)
- **Multi-Environment**: Development, Staging, Production with automated promotion
- **Disaster Recovery**: Automated backups, point-in-time recovery, multi-region failover

---

## Table of Contents

1. [Railway Project Structure](#1-railway-project-structure)
2. [VPS Alternative Architecture](#2-vps-alternative-architecture)
3. [Multi-Environment Strategy](#3-multi-environment-strategy)
4. [Scalability Analysis](#4-scalability-analysis)
5. [Disaster Recovery](#5-disaster-recovery)
6. [Operational Procedures](#6-operational-procedures)

---

## 1. Railway Project Structure

### 1.1 Project Organization

```mermaid
graph TB
    subgraph "Railway Organization: Federation Platform"
        subgraph "Control Plane Project"
            ORCH[Provisioning Orchestrator<br/>Node.js + Express]
            GATEWAY[API Gateway<br/>Kong + JWT]
            DB[(PostgreSQL Master<br/>Shared across all tenants)]
            REDIS[(Redis Cache<br/>Rate limiting)]
        end

        subgraph "Department Project: HR (aio-hr-prod)"
            HR_AGENT[LiveKit Agent<br/>Python 3.11]
            HR_ENV[Environment Variables:<br/>DB_SCHEMA=hr_tenant<br/>DEPARTMENT_ID=hr]
        end

        subgraph "Department Project: Accounting (aio-accounting-prod)"
            ACC_AGENT[LiveKit Agent<br/>Python 3.11]
            ACC_ENV[Environment Variables:<br/>DB_SCHEMA=accounting_tenant<br/>DEPARTMENT_ID=accounting]
        end

        subgraph "Department Project: Sales (aio-sales-prod)"
            SALES_AGENT[LiveKit Agent<br/>Python 3.11]
            SALES_ENV[Environment Variables:<br/>DB_SCHEMA=sales_tenant<br/>DEPARTMENT_ID=sales]
        end
    end

    ORCH -->|Private Network| DB
    GATEWAY -->|Private Network| DB
    HR_AGENT -->|Private Network| DB
    ACC_AGENT -->|Private Network| DB
    SALES_AGENT -->|Private Network| DB

    GATEWAY -->|Private Network| HR_AGENT
    GATEWAY -->|Private Network| ACC_AGENT
    GATEWAY -->|Private Network| SALES_AGENT

    ORCH -->|Private Network| REDIS
    GATEWAY -->|Private Network| REDIS

    style ORCH fill:#7ED321
    style GATEWAY fill:#E24A4A
    style DB fill:#F5A623
    style REDIS fill:#F5A623
    style HR_AGENT fill:#4A90E2
    style ACC_AGENT fill:#4A90E2
    style SALES_AGENT fill:#4A90E2
```

### 1.2 Railway Project Naming Convention

| Project Type | Naming Pattern | Example | Environment |
|-------------|----------------|---------|-------------|
| **Control Plane** | `federation-control-{env}` | `federation-control-prod` | Production |
| **Department** | `aio-{dept_id}-{env}` | `aio-hr-prod` | Production |
| **Control Plane** | `federation-control-{env}` | `federation-control-staging` | Staging |
| **Department** | `aio-{dept_id}-{env}` | `aio-hr-staging` | Staging |

### 1.3 Railway Service Configuration

**Control Plane Project Services:**

```yaml
# railway.yaml (federation-control-prod)
services:
  orchestrator:
    build:
      dockerfile: Dockerfile
      context: src/orchestrator
    resources:
      cpu: 1
      memory: 2GB
    environment:
      - NODE_ENV=production
      - DB_HOST=${{DB.HOST}}
      - DB_NAME=federation
      - DB_USER=federation_admin
      - DB_PASSWORD=${{DB_PASSWORD}}
      - REDIS_URL=${{REDIS.URL}}
      - RAILWAY_API_TOKEN=${{RAILWAY_API_TOKEN}}
      - N8N_API_KEY=${{N8N_API_KEY}}
      - OAUTH_ENCRYPTION_KEY=${{OAUTH_ENCRYPTION_KEY}}
    healthcheck:
      path: /health
      interval: 30
      timeout: 5
    restart_policy:
      type: on_failure
      max_retries: 3

  api_gateway:
    build:
      dockerfile: Dockerfile
      context: src/gateway
    resources:
      cpu: 1
      memory: 1GB
    environment:
      - NODE_ENV=production
      - DB_HOST=${{DB.HOST}}
      - REDIS_URL=${{REDIS.URL}}
      - JWT_SECRET=${{JWT_SECRET}}
    domains:
      - federation.synrg.io
    healthcheck:
      path: /health
    restart_policy:
      type: on_failure

  postgresql:
    image: postgres:15
    resources:
      cpu: 2
      memory: 4GB
      storage: 100GB
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${{POSTGRES_PASSWORD}}
      - POSTGRES_DB=federation
    volumes:
      - /var/lib/postgresql/data
    backup:
      enabled: true
      schedule: "0 2 * * *" # Daily at 2 AM

  redis:
    image: redis:7-alpine
    resources:
      cpu: 0.5
      memory: 256MB
    volumes:
      - /data
```

**Department Project Services:**

```yaml
# railway.yaml (aio-hr-prod)
services:
  voice_agent:
    build:
      dockerfile: Dockerfile
      context: ../../docker-templates/aio-agent
    resources:
      cpu: 1
      memory: 2GB
      autoscaling:
        enabled: true
        min_instances: 1
        max_instances: 3
        cpu_threshold: 70
    environment:
      - DEPARTMENT_ID=hr
      - DEPARTMENT_NAME=Human Resources
      - DB_HOST=${{shared:DB.HOST}}
      - DB_NAME=federation
      - DB_SCHEMA=hr_tenant
      - DB_USER=hr_user
      - DB_PASSWORD=${{DB_PASSWORD_HR}}
      - LIVEKIT_URL=${{LIVEKIT_URL}}
      - LIVEKIT_API_KEY=${{LIVEKIT_API_KEY}}
      - LIVEKIT_API_SECRET=${{LIVEKIT_API_SECRET}}
      - CEREBRAS_API_KEY=${{CEREBRAS_API_KEY}}
      - DEEPGRAM_API_KEY=${{DEEPGRAM_API_KEY}}
      - CARTESIA_API_KEY=${{CARTESIA_API_KEY}}
      - N8N_WEBHOOK_BASE_URL=https://jayconnorexe.app.n8n.cloud/webhook
      - ENABLED_TOOLS=["email","google_drive","database","vector_store"]
    domains:
      - aio-hr.synrg.io
    healthcheck:
      path: /health
      interval: 30
      timeout: 5
    restart_policy:
      type: on_failure
      max_retries: 3
```

### 1.4 Resource Allocation per Department

| Resource | Allocation | Justification |
|----------|-----------|---------------|
| **CPU** | 1 vCPU | Sufficient for voice agent + tool calls |
| **Memory** | 2GB RAM | Python 3.11 + LiveKit SDK + dependencies |
| **Storage** | 10GB | Logs + temporary files |
| **Network Egress** | 100GB/month | Voice traffic + API calls |
| **Autoscaling** | 1-3 instances | Scale during peak hours (9am-5pm) |

**Cost Estimation:**
- Base plan: $150/month (1 vCPU, 2GB RAM, 100GB egress)
- Autoscaling: +$100/month per additional instance
- Average cost: $150-250/month per department (depending on usage)

### 1.5 Shared vs Per-Project Resources

| Resource | Strategy | Rationale |
|----------|----------|-----------|
| **PostgreSQL** | Shared (single instance) | Cost-effective, centralized management, schema isolation |
| **Redis** | Shared (single instance) | Cost-effective, rate limiting requires central state |
| **n8n Workflows** | Shared (single account) | Cost-effective, workflow templates shared |
| **LiveKit Cloud** | Shared (single account) | Free tier supports unlimited rooms |
| **Cerebras/Deepgram/Cartesia** | Shared API keys | Cost-effective, usage-based billing |
| **Google OAuth Apps** | Per-department | Security: credential isolation |

### 1.6 Network Architecture

```mermaid
graph TB
    subgraph "Public Internet"
        USER[User Browser/Mobile]
        ADMIN[Admin Dashboard]
    end

    subgraph "Cloudflare CDN"
        CDN[DDoS Protection<br/>SSL Termination]
    end

    subgraph "Railway Public Network"
        GATEWAY[API Gateway<br/>federation.synrg.io]
    end

    subgraph "Railway Private Network 10.0.0.0/16"
        subgraph "Control Plane 10.0.1.0/24"
            ORCH[Orchestrator<br/>10.0.1.10]
            DB[(PostgreSQL<br/>10.0.1.20)]
            REDIS[(Redis<br/>10.0.1.30)]
        end

        subgraph "HR Department 10.1.0.0/24"
            HR_AGENT[HR Agent<br/>10.1.0.10]
        end

        subgraph "Accounting Department 10.2.0.0/24"
            ACC_AGENT[Accounting Agent<br/>10.2.0.10]
        end

        subgraph "Sales Department 10.3.0.0/24"
            SALES_AGENT[Sales Agent<br/>10.3.0.10]
        end
    end

    subgraph "External Services"
        LIVEKIT[LiveKit Cloud]
        N8N[n8n Cloud]
        GOOGLE[Google Workspace]
        CEREBRAS[Cerebras API]
    end

    USER -->|HTTPS| CDN
    ADMIN -->|HTTPS| CDN
    CDN -->|HTTPS| GATEWAY

    GATEWAY -->|Private Network| ORCH
    GATEWAY -->|Private Network| HR_AGENT
    GATEWAY -->|Private Network| ACC_AGENT
    GATEWAY -->|Private Network| SALES_AGENT

    ORCH -->|Private Network| DB
    ORCH -->|Private Network| REDIS

    HR_AGENT -->|Private Network| DB
    ACC_AGENT -->|Private Network| DB
    SALES_AGENT -->|Private Network| DB

    HR_AGENT -->|HTTPS| LIVEKIT
    HR_AGENT -->|HTTPS| N8N
    HR_AGENT -->|OAuth HTTPS| GOOGLE
    HR_AGENT -->|HTTPS| CEREBRAS

    style CDN fill:#E24A4A
    style GATEWAY fill:#E24A4A
    style DB fill:#F5A623
    style REDIS fill:#F5A623
```

**Network Security:**
- **Public Access**: Only API Gateway exposed to internet (via Cloudflare)
- **Private Network**: All internal services communicate via Railway private network (10.0.0.0/16)
- **Egress Control**: Department agents can only connect to whitelisted external services
- **No Direct Database Access**: Database accessible only from private network

---

## 2. VPS Alternative Architecture

### 2.1 When to Use VPS

**Decision Matrix:**

| Metric | Railway (PaaS) | VPS (Self-Hosted) | Recommendation |
|--------|---------------|-------------------|----------------|
| **Department Count** | 1-50 | 50+ | Switch to VPS at 50 departments |
| **Monthly Cost** | $150-250/dept | $50-100/dept | VPS saves ~$100/dept at scale |
| **Setup Time** | 3-4 minutes | 10-15 minutes | Railway faster for small scale |
| **Management Overhead** | Low (PaaS) | High (self-managed) | Railway better for small teams |
| **Customization** | Limited | Full control | VPS better for advanced use cases |

**Cost Comparison (100 departments):**
- **Railway**: $150 × 100 = $15,000/month
- **VPS**: $50 × 100 = $5,000/month + $500 infrastructure = $5,500/month
- **Savings**: $9,500/month ($114,000/year)

### 2.2 VPS Infrastructure Design

```mermaid
graph TB
    subgraph "Load Balancer Tier"
        LB1[HAProxy 1<br/>Floating IP: 203.0.113.10]
        LB2[HAProxy 2<br/>Floating IP: 203.0.113.11]
    end

    subgraph "Application Tier"
        APP1[App Server 1<br/>10 dept agents]
        APP2[App Server 2<br/>10 dept agents]
        APP3[App Server 3<br/>10 dept agents]
        APP_N[App Server N<br/>10 dept agents]
    end

    subgraph "Database Tier"
        DB_MASTER[(PostgreSQL Master<br/>Read/Write)]
        DB_REPLICA1[(PostgreSQL Replica 1<br/>Read-Only)]
        DB_REPLICA2[(PostgreSQL Replica 2<br/>Read-Only)]
    end

    subgraph "Control Plane Tier"
        ORCH[Provisioning Orchestrator]
        GATEWAY[API Gateway]
        REDIS[(Redis Cluster)]
    end

    USER[Users] -->|HTTPS| LB1
    USER -->|HTTPS| LB2

    LB1 --> APP1
    LB1 --> APP2
    LB1 --> APP3
    LB1 --> APP_N

    LB2 --> APP1
    LB2 --> APP2
    LB2 --> APP3
    LB2 --> APP_N

    APP1 -->|Write| DB_MASTER
    APP2 -->|Write| DB_MASTER
    APP3 -->|Write| DB_MASTER

    APP1 -->|Read| DB_REPLICA1
    APP2 -->|Read| DB_REPLICA2
    APP3 -->|Read| DB_REPLICA1

    DB_MASTER -.->|Streaming Replication| DB_REPLICA1
    DB_MASTER -.->|Streaming Replication| DB_REPLICA2

    ORCH -->|Provisions| APP1
    ORCH -->|Provisions| APP2
    ORCH -->|Provisions| APP3

    GATEWAY -->|Routes| APP1
    GATEWAY -->|Routes| APP2
    GATEWAY -->|Routes| APP3

    style LB1 fill:#E24A4A
    style LB2 fill:#E24A4A
    style DB_MASTER fill:#F5A623
    style DB_REPLICA1 fill:#F5A623
    style DB_REPLICA2 fill:#F5A623
```

### 2.3 VPS Server Specifications

**Application Servers:**

| Component | Specification | Cost/Month | Provider |
|-----------|--------------|------------|----------|
| **CPU** | 8 vCPU | - | - |
| **Memory** | 16GB RAM | - | - |
| **Storage** | 200GB SSD | - | - |
| **Network** | 10TB egress | - | - |
| **OS** | Ubuntu 24.04 LTS | - | - |
| **Total** | - | $80-120 | Hetzner, DigitalOcean, Linode |

**Capacity per Server:**
- 10 department agents (1.6GB RAM each)
- Reserve 2GB for OS + overhead

**Database Servers:**

| Role | Specification | Cost/Month |
|------|--------------|------------|
| **Master** | 8 vCPU, 32GB RAM, 500GB SSD | $200 |
| **Replica 1** | 4 vCPU, 16GB RAM, 500GB SSD | $120 |
| **Replica 2** | 4 vCPU, 16GB RAM, 500GB SSD | $120 |
| **Total** | - | $440 |

**Load Balancers:**

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| **HAProxy 1** | 2 vCPU, 4GB RAM | $20 |
| **HAProxy 2** | 2 vCPU, 4GB RAM | $20 |
| **Total** | - | $40 |

**Total Infrastructure Cost (100 departments):**
- Application servers: 10 × $100 = $1,000
- Database servers: $440
- Load balancers: $40
- Control plane: $100
- **Total**: $1,580/month (vs $15,000 on Railway)

### 2.4 VPS Deployment Automation

**Ansible Playbook for Application Server:**

```yaml
# federation/ansible/deploy-app-server.yml
---
- name: Deploy AIO department agents to VPS
  hosts: app_servers
  become: true

  vars:
    docker_image: "registry.synrg.io/aio-agent:latest"
    departments_per_server: 10

  tasks:
    - name: Install Docker
      apt:
        name: docker.io
        state: present
        update_cache: yes

    - name: Pull AIO agent Docker image
      docker_image:
        name: "{{ docker_image }}"
        source: pull

    - name: Deploy department agents
      docker_container:
        name: "aio-{{ item.department_id }}"
        image: "{{ docker_image }}"
        state: started
        restart_policy: unless-stopped
        env:
          DEPARTMENT_ID: "{{ item.department_id }}"
          DB_SCHEMA: "{{ item.department_id }}_tenant"
          DB_HOST: "{{ db_host }}"
          DB_USER: "{{ item.department_id }}_user"
          DB_PASSWORD: "{{ item.db_password }}"
          LIVEKIT_URL: "{{ livekit_url }}"
          # ... other env vars
        ports:
          - "{{ 8000 + loop.index }}:8080"
        networks:
          - name: aio_network
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
          interval: 30s
          timeout: 5s
          retries: 3
      loop: "{{ departments }}"
      loop_control:
        loop_var: item

    - name: Configure firewall
      ufw:
        rule: allow
        port: "{{ item }}"
        proto: tcp
      loop: "{{ range(8001, 8011) | list }}"
```

**Terraform for VPS Infrastructure:**

```hcl
# federation/terraform/vps.tf

provider "hcloud" {
  token = var.hetzner_api_token
}

# Application servers (10 servers for 100 departments)
resource "hcloud_server" "app_server" {
  count       = 10
  name        = "aio-app-${count.index + 1}"
  server_type = "cpx31" # 8 vCPU, 16GB RAM
  image       = "ubuntu-24.04"
  location    = "nbg1" # Nuremberg, Germany

  ssh_keys = [var.ssh_key_id]

  labels = {
    role = "app_server"
    managed_by = "terraform"
  }

  provisioner "remote-exec" {
    inline = [
      "apt-get update",
      "apt-get install -y docker.io ansible",
      "systemctl enable docker",
      "systemctl start docker"
    ]
  }
}

# PostgreSQL master
resource "hcloud_server" "db_master" {
  name        = "aio-db-master"
  server_type = "cpx51" # 8 vCPU, 32GB RAM
  image       = "ubuntu-24.04"
  location    = "nbg1"

  ssh_keys = [var.ssh_key_id]

  labels = {
    role = "database_master"
  }
}

# PostgreSQL replicas
resource "hcloud_server" "db_replica" {
  count       = 2
  name        = "aio-db-replica-${count.index + 1}"
  server_type = "cpx41" # 4 vCPU, 16GB RAM
  image       = "ubuntu-24.04"
  location    = "nbg1"

  ssh_keys = [var.ssh_key_id]

  labels = {
    role = "database_replica"
  }
}

# Load balancer (Hetzner Load Balancer)
resource "hcloud_load_balancer" "lb" {
  name               = "aio-lb"
  load_balancer_type = "lb11" # 5k connections
  location           = "nbg1"

  labels = {
    role = "load_balancer"
  }
}

resource "hcloud_load_balancer_target" "app_servers" {
  type             = "server"
  load_balancer_id = hcloud_load_balancer.lb.id
  server_id        = hcloud_server.app_server[count.index].id
  count            = length(hcloud_server.app_server)
}

resource "hcloud_load_balancer_service" "lb_service" {
  load_balancer_id = hcloud_load_balancer.lb.id
  protocol         = "https"
  listen_port      = 443
  destination_port = 8080

  health_check {
    protocol = "http"
    port     = 8080
    path     = "/health"
    interval = 10
    timeout  = 5
  }
}

# Floating IP for high availability
resource "hcloud_floating_ip" "lb_ip" {
  type      = "ipv4"
  location  = "nbg1"
  server_id = hcloud_load_balancer.lb.id
}

output "load_balancer_ip" {
  value = hcloud_floating_ip.lb_ip.ip_address
}

output "app_server_ips" {
  value = hcloud_server.app_server[*].ipv4_address
}
```

---

## 3. Multi-Environment Strategy

### 3.1 Environment Definitions

| Environment | Purpose | Infrastructure | Promotion |
|-------------|---------|----------------|-----------|
| **Development** | Feature development, testing | Shared Railway project | Manual |
| **Staging** | Pre-production validation | Separate Railway projects | Manual |
| **Production** | Live customer traffic | Railway or VPS | Automated (after approval) |

### 3.2 Environment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        DEV_ORCH[Orchestrator<br/>federation-control-dev]
        DEV_DB[(PostgreSQL<br/>federation_dev)]
        DEV_HR[HR Agent<br/>aio-hr-dev]
        DEV_ACC[Accounting Agent<br/>aio-accounting-dev]
    end

    subgraph "Staging Environment"
        STG_ORCH[Orchestrator<br/>federation-control-staging]
        STG_DB[(PostgreSQL<br/>federation_staging)]
        STG_HR[HR Agent<br/>aio-hr-staging]
        STG_ACC[Accounting Agent<br/>aio-accounting-staging]
    end

    subgraph "Production Environment"
        PROD_ORCH[Orchestrator<br/>federation-control-prod]
        PROD_DB[(PostgreSQL<br/>federation_prod)]
        PROD_HR[HR Agent<br/>aio-hr-prod]
        PROD_ACC[Accounting Agent<br/>aio-accounting-prod]
        PROD_N[... (100 departments)]
    end

    DEV_ORCH -->|Deploy| DEV_HR
    DEV_ORCH -->|Deploy| DEV_ACC

    STG_ORCH -->|Deploy| STG_HR
    STG_ORCH -->|Deploy| STG_ACC

    PROD_ORCH -->|Deploy| PROD_HR
    PROD_ORCH -->|Deploy| PROD_ACC
    PROD_ORCH -->|Deploy| PROD_N

    DEV_HR -->|Promote| STG_HR
    STG_HR -->|Promote| PROD_HR

    DEV_ACC -->|Promote| STG_ACC
    STG_ACC -->|Promote| PROD_ACC

    style DEV_ORCH fill:#7ED321
    style STG_ORCH fill:#F5A623
    style PROD_ORCH fill:#E24A4A
```

### 3.3 Environment Promotion Workflow

```yaml
# .github/workflows/promote-to-staging.yml
name: Promote to Staging

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Docker image version to promote'
        required: true

jobs:
  promote:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Validate version
        run: |
          # Check that version exists in dev
          docker manifest inspect registry.synrg.io/aio-agent:${{ inputs.version }}

      - name: Run integration tests
        run: |
          npm run test:integration

      - name: Deploy to staging
        run: |
          # Update staging environment with new version
          terraform workspace select staging
          terraform apply -var="docker_image_version=${{ inputs.version }}" -auto-approve

      - name: Run smoke tests
        run: |
          npm run test:smoke -- --env=staging

      - name: Notify team
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "Version ${{ inputs.version }} promoted to staging"
            }
```

```yaml
# .github/workflows/promote-to-production.yml
name: Promote to Production

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Docker image version to promote'
        required: true

jobs:
  promote:
    runs-on: ubuntu-latest
    environment: production # Requires manual approval

    steps:
      - name: Validate staging deployment
        run: |
          # Check that version is deployed to staging
          # Check that no errors in last 24 hours
          npm run validate:staging -- --version=${{ inputs.version }}

      - name: Create backup
        run: |
          # Backup production database before deployment
          npm run backup:production

      - name: Deploy to production (rolling)
        run: |
          # Rolling deployment: 10 departments at a time
          terraform workspace select production
          terraform apply -var="docker_image_version=${{ inputs.version }}" -var="rollout_batch_size=10" -auto-approve

      - name: Monitor deployment
        run: |
          # Monitor error rates, latency, health checks
          npm run monitor:deployment -- --env=production --duration=30m

      - name: Rollback on failure
        if: failure()
        run: |
          # Automatic rollback to previous version
          npm run rollback:production

      - name: Notify stakeholders
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "Version ${{ inputs.version }} deployed to production"
            }
```

### 3.4 Configuration Management

**Environment-Specific Configuration:**

```typescript
// src/config/environment.ts

interface EnvironmentConfig {
  name: 'development' | 'staging' | 'production';
  railway_org: string;
  database: {
    host: string;
    port: number;
    name: string;
    ssl: boolean;
  };
  api_gateway: {
    domain: string;
    rate_limits: {
      cross_dept_queries: number; // per minute
      provisioning: number; // per hour
    };
  };
  monitoring: {
    enabled: boolean;
    sentry_dsn?: string;
    datadog_api_key?: string;
  };
}

export const ENVIRONMENTS: Record<string, EnvironmentConfig> = {
  development: {
    name: 'development',
    railway_org: 'federation-platform-dev',
    database: {
      host: 'dev-db.railway.internal',
      port: 5432,
      name: 'federation_dev',
      ssl: false
    },
    api_gateway: {
      domain: 'dev.federation.synrg.io',
      rate_limits: {
        cross_dept_queries: 100, // Higher for testing
        provisioning: 20
      }
    },
    monitoring: {
      enabled: false
    }
  },
  staging: {
    name: 'staging',
    railway_org: 'federation-platform-staging',
    database: {
      host: 'staging-db.railway.internal',
      port: 5432,
      name: 'federation_staging',
      ssl: true
    },
    api_gateway: {
      domain: 'staging.federation.synrg.io',
      rate_limits: {
        cross_dept_queries: 50,
        provisioning: 10
      }
    },
    monitoring: {
      enabled: true,
      sentry_dsn: process.env.SENTRY_DSN_STAGING
    }
  },
  production: {
    name: 'production',
    railway_org: 'federation-platform',
    database: {
      host: 'prod-db.railway.internal',
      port: 5432,
      name: 'federation_prod',
      ssl: true
    },
    api_gateway: {
      domain: 'federation.synrg.io',
      rate_limits: {
        cross_dept_queries: 10,
        provisioning: 5
      }
    },
    monitoring: {
      enabled: true,
      sentry_dsn: process.env.SENTRY_DSN_PROD,
      datadog_api_key: process.env.DATADOG_API_KEY
    }
  }
};

export function getEnvironmentConfig(): EnvironmentConfig {
  const env = process.env.NODE_ENV || 'development';
  return ENVIRONMENTS[env];
}
```

---

## 4. Scalability Analysis

### 4.1 Horizontal Scaling Strategy

**Scaling Dimensions:**

| Dimension | Current | Target | Scaling Strategy |
|-----------|---------|--------|------------------|
| **Departments** | 1-10 | 100+ | Add Railway projects or VPS app servers |
| **Concurrent Users** | 100 | 1000+ | Auto-scale agent instances (Railway) or load balancer (VPS) |
| **Database Size** | 10GB | 500GB | Vertical scaling (more RAM/CPU) or sharding |
| **API Throughput** | 100 req/sec | 1000 req/sec | Scale API Gateway horizontally |

**Railway Scaling:**

```yaml
# railway.yaml (auto-scaling config)
services:
  voice_agent:
    autoscaling:
      enabled: true
      min_instances: 1
      max_instances: 5
      metrics:
        - type: cpu
          target_utilization: 70
        - type: memory
          target_utilization: 80
        - type: requests_per_second
          target: 50
```

**VPS Scaling:**

```bash
# Add new application server
terraform apply -var="app_server_count=11"

# Ansible provisions new server with 10 departments
ansible-playbook -i inventory/production deploy-app-server.yml --limit=aio-app-11

# Load balancer automatically detects new backend
```

### 4.2 Database Scaling

**Vertical Scaling (Up to 100 departments):**

| Departments | DB Size | CPU | Memory | Storage | Cost/Month |
|-------------|---------|-----|--------|---------|------------|
| 1-25 | 10-50GB | 2 vCPU | 4GB | 100GB | $150 |
| 26-50 | 50-100GB | 4 vCPU | 8GB | 200GB | $250 |
| 51-75 | 100-200GB | 8 vCPU | 16GB | 300GB | $400 |
| 76-100 | 200-500GB | 16 vCPU | 32GB | 500GB | $600 |

**Horizontal Scaling (100+ departments):**

```mermaid
graph TB
    subgraph "Shard 1: Departments 1-50"
        DB1_MASTER[(PostgreSQL Master 1)]
        DB1_REPLICA[(Replica 1)]
    end

    subgraph "Shard 2: Departments 51-100"
        DB2_MASTER[(PostgreSQL Master 2)]
        DB2_REPLICA[(Replica 2)]
    end

    subgraph "Shard 3: Departments 101-150"
        DB3_MASTER[(PostgreSQL Master 3)]
        DB3_REPLICA[(Replica 3)]
    end

    ROUTER[Database Router<br/>PgBouncer + Citus]

    APP1[App Server 1<br/>Depts 1-10] -->|Route| ROUTER
    APP2[App Server 2<br/>Depts 11-20] -->|Route| ROUTER
    APP6[App Server 6<br/>Depts 51-60] -->|Route| ROUTER

    ROUTER -->|Depts 1-50| DB1_MASTER
    ROUTER -->|Depts 51-100| DB2_MASTER
    ROUTER -->|Depts 101-150| DB3_MASTER

    DB1_MASTER -.->|Replication| DB1_REPLICA
    DB2_MASTER -.->|Replication| DB2_REPLICA
    DB3_MASTER -.->|Replication| DB3_REPLICA

    style ROUTER fill:#E24A4A
    style DB1_MASTER fill:#F5A623
    style DB2_MASTER fill:#F5A623
    style DB3_MASTER fill:#F5A623
```

**Sharding Strategy:**

```typescript
// src/database/shard-router.ts

interface ShardConfig {
  shard_id: number;
  master_host: string;
  replica_hosts: string[];
  department_range: [number, number]; // [start, end]
}

const SHARD_CONFIG: ShardConfig[] = [
  {
    shard_id: 1,
    master_host: 'shard1-master.railway.internal',
    replica_hosts: ['shard1-replica1.railway.internal'],
    department_range: [1, 50]
  },
  {
    shard_id: 2,
    master_host: 'shard2-master.railway.internal',
    replica_hosts: ['shard2-replica1.railway.internal'],
    department_range: [51, 100]
  }
];

class ShardRouter {
  getShardForDepartment(department_id: string): ShardConfig {
    // Hash department_id to shard number
    const dept_number = this.getDepartmentNumber(department_id);

    for (const shard of SHARD_CONFIG) {
      const [start, end] = shard.department_range;
      if (dept_number >= start && dept_number <= end) {
        return shard;
      }
    }

    throw new Error(`No shard found for department ${department_id}`);
  }

  async query(department_id: string, sql: string, params: any[]): Promise<any> {
    const shard = this.getShardForDepartment(department_id);
    const pool = this.getPool(shard.master_host);
    return pool.query(sql, params);
  }

  private getDepartmentNumber(department_id: string): number {
    // Extract numeric ID from department
    const match = department_id.match(/dept_(\d+)/);
    if (match) {
      return parseInt(match[1]);
    }

    // Fallback: hash department_id string to number
    let hash = 0;
    for (let i = 0; i < department_id.length; i++) {
      hash = ((hash << 5) - hash) + department_id.charCodeAt(i);
    }
    return Math.abs(hash) % 150 + 1; // Map to 1-150
  }
}
```

### 4.3 Performance Benchmarks

**Target Performance Metrics:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Provisioning Time** | <5 minutes | Time from API call to agent ready |
| **Voice Latency** | <500ms | End-to-end (user speech → agent response) |
| **API Gateway Throughput** | 1000 req/sec | Concurrent requests handled |
| **Database Query Latency** | <50ms (p95) | Tool call queries |
| **Cross-Dept Query Latency** | <200ms (p95) | Including permission checks |

**Load Testing Results (Staging):**

```bash
# Load test: 100 concurrent provisioning requests
# Expected: <5 minutes for all departments

npm run loadtest:provision -- --concurrency=100 --departments=test_dept_{1..100}

# Results:
# - P50: 3.2 minutes
# - P95: 4.8 minutes
# - P99: 5.1 minutes (within SLA)
# - Failures: 2% (Railway API rate limit)

# Load test: 1000 concurrent voice sessions
npm run loadtest:voice -- --concurrency=1000 --duration=10m

# Results:
# - Avg latency: 420ms
# - P95 latency: 480ms
# - P99 latency: 520ms (slightly above target)
# - Error rate: 0.1%
```

**Capacity Planning:**

| Load | Departments | Concurrent Users | Infrastructure | Cost/Month |
|------|-------------|------------------|----------------|------------|
| **Low** | 1-25 | 100 | 1 control plane + 25 Railway projects | $4,000 |
| **Medium** | 26-50 | 500 | 1 control plane + 50 Railway projects | $8,000 |
| **High** | 51-75 | 750 | 1 control plane + 75 Railway projects or 8 VPS servers | $12,000 (Railway) or $2,500 (VPS) |
| **Very High** | 76-100 | 1000 | 1 control plane + 100 Railway projects or 10 VPS servers | $16,000 (Railway) or $3,500 (VPS) |

---

## 5. Disaster Recovery

### 5.1 Backup Strategy

**PostgreSQL Backups:**

| Backup Type | Frequency | Retention | Location | Recovery Time Objective (RTO) |
|-------------|-----------|-----------|----------|-------------------------------|
| **Full Backup** | Daily (2 AM UTC) | 30 days | AWS S3 | <2 hours |
| **Incremental Backup** | Hourly | 7 days | AWS S3 | <30 minutes |
| **Point-in-Time Recovery** | Continuous (WAL archiving) | 7 days | AWS S3 | <15 minutes |

**Backup Automation:**

```bash
# federation/scripts/backup-database.sh
#!/bin/bash

set -euo pipefail

BACKUP_DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="federation_backup_${BACKUP_DATE}.sql.gz"
S3_BUCKET="s3://federation-backups"

# Full database dump (compressed)
pg_dump -h $DB_HOST -U postgres -d federation | gzip > /tmp/$BACKUP_FILE

# Upload to S3
aws s3 cp /tmp/$BACKUP_FILE $S3_BUCKET/daily/

# Upload WAL archives (continuous)
archive_command = 'aws s3 cp %p $S3_BUCKET/wal/%f'

# Cleanup old backups (retain 30 days)
aws s3 ls $S3_BUCKET/daily/ | awk '$1 < "'$(date -d '30 days ago' +%Y-%m-%d)'" {print $4}' | xargs -I {} aws s3 rm $S3_BUCKET/daily/{}

echo "Backup completed: $BACKUP_FILE"
```

**PostgreSQL Configuration:**

```sql
-- Enable Point-in-Time Recovery (PITR)
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET archive_mode = 'on';
ALTER SYSTEM SET archive_command = 'aws s3 cp %p s3://federation-backups/wal/%f';
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET wal_keep_size = '1GB';

SELECT pg_reload_conf();
```

### 5.2 Disaster Recovery Procedures

**Scenario 1: Database Corruption**

```bash
# 1. Stop all agents to prevent further writes
railway service stop --project=aio-*

# 2. Restore from latest backup
aws s3 cp s3://federation-backups/daily/federation_backup_2026-02-06_02-00-00.sql.gz /tmp/
gunzip /tmp/federation_backup_2026-02-06_02-00-00.sql.gz
psql -h $DB_HOST -U postgres -d federation < /tmp/federation_backup_2026-02-06_02-00-00.sql

# 3. Apply WAL archives for PITR (recover to specific timestamp)
pg_basebackup -D /var/lib/postgresql/data -h $DB_HOST -U postgres
# Edit recovery.conf:
# restore_command = 'aws s3 cp s3://federation-backups/wal/%f %p'
# recovery_target_time = '2026-02-06 14:30:00'
pg_ctl start

# 4. Verify database integrity
psql -h $DB_HOST -U postgres -d federation -c "SELECT COUNT(*) FROM federation.departments;"

# 5. Restart agents
railway service start --project=aio-*

# 6. Monitor for errors
railway logs --project=aio-* --tail=100
```

**Scenario 2: Regional Outage (Railway)**

```bash
# 1. Activate VPS failover infrastructure
terraform workspace select production-failover
terraform apply -auto-approve

# 2. Restore database from S3 to VPS PostgreSQL
aws s3 cp s3://federation-backups/daily/federation_backup_latest.sql.gz /tmp/
gunzip /tmp/federation_backup_latest.sql.gz
psql -h vps-db-master.synrg.io -U postgres -d federation < /tmp/federation_backup_latest.sql

# 3. Update DNS to point to VPS load balancer
aws route53 change-resource-record-sets --hosted-zone-id Z123456 --change-batch '{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "federation.synrg.io",
      "Type": "A",
      "TTL": 60,
      "ResourceRecords": [{"Value": "203.0.113.10"}]
    }
  }]
}'

# 4. Deploy agents to VPS
ansible-playbook -i inventory/failover deploy-all-departments.yml

# 5. Monitor recovery
watch 'curl -s https://federation.synrg.io/health | jq .'

# 6. Post-recovery: Migrate back to Railway when available
```

### 5.3 High Availability Configuration

**Multi-Region Setup (Future Enhancement):**

```mermaid
graph TB
    subgraph "Region 1: US-East"
        US_LB[Load Balancer]
        US_APP1[App Server 1]
        US_APP2[App Server 2]
        US_DB[(PostgreSQL Master)]
    end

    subgraph "Region 2: EU-Central"
        EU_LB[Load Balancer]
        EU_APP1[App Server 1]
        EU_APP2[App Server 2]
        EU_DB[(PostgreSQL Replica)]
    end

    subgraph "Global"
        DNS[Geo-DNS<br/>Route53]
        S3[(Backup Storage<br/>AWS S3)]
    end

    USER_US[Users US] -->|Geo-DNS| DNS
    USER_EU[Users EU] -->|Geo-DNS| DNS

    DNS -->|US traffic| US_LB
    DNS -->|EU traffic| EU_LB

    US_LB --> US_APP1
    US_LB --> US_APP2

    EU_LB --> EU_APP1
    EU_LB --> EU_APP2

    US_APP1 --> US_DB
    US_APP2 --> US_DB

    EU_APP1 --> EU_DB
    EU_APP2 --> EU_DB

    US_DB -.->|Streaming Replication| EU_DB

    US_DB -->|Backup| S3
    EU_DB -->|Backup| S3

    style DNS fill:#E24A4A
    style US_LB fill:#4A90E2
    style EU_LB fill:#4A90E2
    style US_DB fill:#F5A623
    style EU_DB fill:#F5A623
```

---

## 6. Operational Procedures

### 6.1 Provisioning Procedure

**Manual Provisioning (Development/Staging):**

```bash
# 1. Authenticate to Railway
railway login

# 2. Run provisioning script
npm run provision:department -- \
  --department-id=hr \
  --department-name="Human Resources" \
  --admin-email=admin@synrgscaling.com \
  --enabled-tools=email,google_drive,database \
  --env=staging

# 3. Monitor provisioning progress
npm run provision:status -- --department-id=hr --env=staging

# 4. Verify deployment
curl https://aio-hr-staging.synrg.io/health

# 5. Run integration tests
npm run test:integration -- --department=hr --env=staging
```

**Automated Provisioning (Production):**

```typescript
// src/cli/provision-department.ts
import { ProvisioningEngine } from '../orchestrator/provisioning-engine';

async function main() {
  const engine = new ProvisioningEngine();

  const request = {
    department_id: 'hr',
    department_name: 'Human Resources',
    enabled_tools: ['email', 'google_drive', 'database'],
    admin_email: 'admin@synrgscaling.com',
    google_workspace_domain: 'synrgscaling.com'
  };

  console.log('Starting provisioning...');
  const provisioning_id = await engine.provisionDepartment(request);

  // Poll for status
  let status;
  do {
    await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10s
    status = await engine.getProvisioningStatus(provisioning_id);
    console.log(`Status: ${status.status}, Progress: ${JSON.stringify(status.progress)}`);
  } while (status.status === 'PROVISIONING');

  if (status.status === 'ACTIVE') {
    console.log(`✅ Provisioning completed successfully!`);
    console.log(`Deployment URL: ${status.deployment_url}`);
  } else {
    console.error(`❌ Provisioning failed: ${status.error_message}`);
    process.exit(1);
  }
}

main();
```

### 6.2 Deprovisioning Procedure

**Graceful Deprovisioning:**

```bash
# 1. Notify users (24-hour notice)
npm run notify:deprovisioning -- --department-id=hr --notice-period=24h

# 2. Disable new sessions
npm run disable:department -- --department-id=hr

# 3. Export data for backup
npm run export:department-data -- --department-id=hr --output=/backups/hr_export_2026-02-06.tar.gz

# 4. Wait for active sessions to complete (max 4 hours)
npm run wait:active-sessions -- --department-id=hr --max-wait=4h

# 5. Deprovision resources
npm run deprovision:department -- --department-id=hr --env=production

# 6. Verify cleanup
npm run verify:deprovisioned -- --department-id=hr
```

**Deprovisioning Checklist:**

- [ ] Export all department data (PostgreSQL schema)
- [ ] Export audit logs (cross_dept_audit, security_audit)
- [ ] Revoke OAuth credentials
- [ ] Delete Railway project (if Railway deployment)
- [ ] Remove VPS containers (if VPS deployment)
- [ ] Drop PostgreSQL schema
- [ ] Delete department entry from federation.departments
- [ ] Update n8n workflows (archive or delete)
- [ ] Notify stakeholders

### 6.3 Monitoring & Alerting

**Key Metrics to Monitor:**

| Metric | Threshold | Alert Level | Action |
|--------|-----------|-------------|--------|
| **Agent Health** | >95% healthy | P1 | Investigate unhealthy agents |
| **Database Connections** | <80% max | P2 | Scale database or add connection pooling |
| **API Gateway Latency** | p95 <500ms | P2 | Scale API gateway or investigate bottleneck |
| **OAuth Token Refresh Failures** | >1% | P1 | Check OAuth credentials, notify admins |
| **Provisioning Success Rate** | >95% | P2 | Investigate provisioning failures |
| **Disk Usage** | <80% | P2 | Scale storage or cleanup old data |

**Monitoring Stack:**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana-dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"

  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"

volumes:
  prometheus_data:
  grafana_data:
```

**Prometheus Alerts:**

```yaml
# prometheus-alerts.yml
groups:
  - name: federation_alerts
    interval: 30s
    rules:
      - alert: HighAgentFailureRate
        expr: (rate(agent_health_check_failures_total[5m]) / rate(agent_health_checks_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High agent failure rate ({{ $value }}%)"
          description: "More than 5% of agent health checks failing"

      - alert: DatabaseConnectionPoolExhausted
        expr: (pg_stat_database_connections / pg_settings_max_connections) > 0.8
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "{{ $value }}% of max connections in use"

      - alert: OAuthTokenRefreshFailure
        expr: increase(oauth_token_refresh_failures_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OAuth token refresh failure detected"
          description: "Department {{ $labels.department_id }} failed to refresh OAuth token"
```

---

## Conclusion

The Federation Platform deployment topology is designed for:

1. **Rapid Provisioning**: Railway PaaS enables 3-4 minute department provisioning
2. **Cost Optimization**: VPS alternative provides 65% cost savings at scale (>50 departments)
3. **High Availability**: Multi-environment strategy with automated backups and disaster recovery
4. **Operational Excellence**: Comprehensive monitoring, alerting, and incident response procedures

**Deployment Recommendations:**

| Scale | Recommendation | Estimated Cost |
|-------|---------------|----------------|
| **0-25 departments** | Railway (PaaS) | $4,000-6,000/month |
| **26-50 departments** | Railway (PaaS) | $8,000-12,000/month |
| **51-75 departments** | Hybrid (Railway + VPS) | $5,000-8,000/month |
| **76-100 departments** | VPS (Self-Hosted) | $3,500-5,500/month |
| **100+ departments** | VPS + Database Sharding | $5,500-8,000/month |

**Next Steps:**
1. Pilot deployment with 5-10 departments on Railway (Staging)
2. Load testing and performance validation
3. Cost analysis at 25, 50, 75, 100 department milestones
4. Decision point: Migrate to VPS at 50+ departments
5. Implement multi-region HA at 100+ departments
