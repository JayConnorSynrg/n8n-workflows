# Federation Platform - Infrastructure as Code

**Version:** 1.0.0
**Date:** 2026-02-06
**Architecture:** Multi-cloud department provisioning automation

---

## Overview

Automated infrastructure provisioning for Federation Platform department instances using:

- **Terraform** - Railway project and service management
- **Ansible** - VPS server configuration and deployment
- **TypeScript CLI** - Unified deployment interface

**Deployment Targets:**
- **Railway (PaaS)** - Rapid provisioning, zero-config (1-50 departments)
- **VPS (Self-hosted)** - Cost optimization at scale (50+ departments)

---

## Quick Start

### 1. Install Dependencies

```bash
cd federation/infrastructure-as-code

# Install Node.js dependencies
npm install

# Install Terraform (macOS)
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# Install Ansible (macOS)
brew install ansible

# Verify installations
terraform --version
ansible --version
node --version
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required credentials:
- `RAILWAY_API_TOKEN` - Railway API token
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` - LiveKit credentials
- `CEREBRAS_API_KEY` - Cerebras LLM API key
- `DEEPGRAM_API_KEY` - Deepgram STT API key
- `CARTESIA_API_KEY` - Cartesia TTS API key

### 3. Create Deployment Config

```bash
# Copy example config
cp config.example.json hr-config.json

# Edit config for your department
nano hr-config.json
```

### 4. Deploy

**Option A: Railway (Recommended for <50 departments)**

```bash
npm run deploy:railway hr-config.json
```

**Option B: VPS (Recommended for 50+ departments)**

```bash
# First, configure Ansible inventory
nano ansible/inventories/prod.yml

# Then deploy
npm run deploy:vps hr-config.json
```

---

## Directory Structure

```
infrastructure-as-code/
├── terraform/
│   └── railway/
│       ├── main.tf                  # Railway resources
│       ├── variables.tf             # Input variables
│       ├── outputs.tf               # Output values
│       ├── versions.tf              # Provider versions
│       └── terraform.tfvars.example # Example variables
│
├── ansible/
│   ├── aio-vps.yml                  # Main playbook
│   ├── templates/
│   │   ├── docker-compose.yml.j2    # Docker Compose template
│   │   ├── .env.j2                  # Environment variables template
│   │   ├── aio.service.j2           # Systemd service template
│   │   └── monitor.sh.j2            # Monitoring script
│   └── inventories/
│       ├── prod.yml                 # Production inventory
│       └── staging.yml              # Staging inventory
│
├── cli/
│   ├── deploy-cli.ts                # Unified deployment CLI
│   ├── railway-client.ts            # Railway API client
│   └── types.ts                     # TypeScript types
│
├── config.example.json              # Example deployment config
├── .env.example                     # Example environment variables
├── package.json                     # Node.js dependencies
└── README.md                        # This file
```

---

## Deployment Methods

### Method 1: Terraform + Railway

**Best for:** 1-50 departments, rapid provisioning, minimal operations overhead

**Advantages:**
- 3-4 minute provisioning time
- Zero-config deployment
- Automatic SSL/TLS
- Built-in monitoring
- Auto-scaling support

**Cost:** $150-250/month per department

**Usage:**

```bash
cd terraform/railway

# Initialize Terraform
terraform init

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit variables for your department
nano terraform.tfvars

# Plan deployment
terraform plan

# Apply deployment
terraform apply
```

### Method 2: Ansible + VPS

**Best for:** 50+ departments, cost optimization, custom infrastructure

**Advantages:**
- 65% cost savings at scale
- Full control over infrastructure
- Custom networking configurations
- Dedicated resources

**Cost:** $50-100/month per department (including shared infrastructure)

**Usage:**

```bash
cd ansible

# Test connection to VPS
ansible -i inventories/prod.yml vps_servers -m ping

# Dry-run deployment
ansible-playbook -i inventories/prod.yml aio-vps.yml --check

# Deploy
ansible-playbook -i inventories/prod.yml aio-vps.yml
```

### Method 3: TypeScript CLI (Recommended)

**Best for:** Unified interface for both Railway and VPS

```bash
# Deploy to Railway
npm run build
node deploy-cli.js deploy railway hr-config.json

# Deploy to VPS
node deploy-cli.js deploy vps hr-config.json

# List deployments
node deploy-cli.js list prod

# Delete deployment
node deploy-cli.js delete <project-id>
```

---

## Configuration Reference

### Deployment Config File

```json
{
  "departmentId": "hr",                    // Unique department slug
  "departmentName": "Human Resources",     // Human-readable name
  "environment": "prod",                   // dev, staging, or prod

  "dockerRegistry": "ghcr.io/synrgscaling",
  "imageVersion": "v1.0.0",

  "n8nWebhookBase": "https://...",

  "livekitUrl": "wss://...",
  "livekitApiKey": "...",
  "livekitApiSecret": "...",

  "cerebrasApiKey": "csk-...",
  "cerebrasModel": "llama-3.3-70b",
  "cerebrasTemperature": "0.6",
  "cerebrasMaxTokens": "150",

  "deepgramApiKey": "...",
  "deepgramModel": "nova-3",

  "cartesiaApiKey": "...",
  "cartesiaModel": "sonic-3",
  "cartesiaVoice": "a167e0f3-...",

  "enabledTools": ["email", "google_drive", "database"],

  "postgresStorage": 10,              // GB
  "voiceAgentCpu": "2000m",          // 2 vCPUs
  "voiceAgentMemory": "4096Mi",      // 4GB

  "customDomain": "aio.synrg.io",    // Optional
  "costCenter": "DEPT-HR-001",       // Optional

  "autoscaling": {                    // Railway only
    "enabled": true,
    "minInstances": 1,
    "maxInstances": 3,
    "cpuThreshold": 70
  },

  "backup": {                         // Optional
    "enabled": true,
    "schedule": "0 2 * * *",
    "retentionDays": 30
  }
}
```

### Terraform Variables

Key variables in `terraform.tfvars`:

```hcl
department_name = "Human Resources"
department_id   = "hr"
environment     = "prod"

docker_registry = "ghcr.io/synrgscaling"
image_version   = "v1.0.0"

# Resources
postgres_storage_gb = 10
voice_agent_cpu     = "2000m"
voice_agent_memory  = "4096Mi"

# Autoscaling
autoscaling_enabled       = true
autoscaling_min_instances = 1
autoscaling_max_instances = 3
autoscaling_cpu_threshold = 70

# Networking
custom_domain = "aio.synrg.io"
```

### Ansible Inventory

Configure VPS hosts in `inventories/prod.yml`:

```yaml
all:
  vars:
    environment: production
    docker_registry: ghcr.io/synrgscaling

  children:
    vps_servers:
      hosts:
        vps-01:
          ansible_host: 203.0.113.10

    hr_vps:
      hosts:
        vps-01:
      vars:
        department_id: hr
        department_name: Human Resources
        voice_agent_port: 8080
```

---

## Deployment Workflows

### Scenario 1: Deploy First Department

```bash
# 1. Create configuration
cp config.example.json hr-config.json
nano hr-config.json

# 2. Validate configuration
npm run build
node deploy-cli.js validate hr-config.json

# 3. Deploy to Railway (fast, for testing)
node deploy-cli.js deploy railway hr-config.json

# 4. Verify deployment
curl https://aio-hr-prod.railway.app/health

# 5. Monitor logs
railway logs --service voice-agent-hr --tail
```

### Scenario 2: Scale to 10 Departments

```bash
# Deploy departments 1-10 to Railway
for dept in hr accounting sales marketing legal; do
  node deploy-cli.js deploy railway ${dept}-config.json
done

# Monitor all deployments
node deploy-cli.js list prod
```

### Scenario 3: Migrate to VPS (50+ Departments)

```bash
# 1. Provision VPS infrastructure with Terraform
cd terraform/vps
terraform init
terraform plan
terraform apply

# 2. Configure Ansible inventory
nano ansible/inventories/prod.yml

# 3. Deploy departments to VPS
for dept in hr accounting sales ...; do
  ansible-playbook -i inventories/prod.yml \
    -e department_id=${dept} \
    aio-vps.yml
done

# 4. Verify deployments
ansible -i inventories/prod.yml vps_servers -m shell \
  -a "docker ps | grep voice_agent"
```

---

## Operational Procedures

### Health Checks

**Railway:**
```bash
# View service status
railway status --service voice-agent-hr

# Check health endpoint
curl https://aio-hr-prod.railway.app/health

# View recent logs
railway logs --service voice-agent-hr --tail=100
```

**VPS:**
```bash
# Check systemd service
ansible -i inventories/prod.yml hr_vps \
  -m systemd -a "name=aio-hr state=status"

# Check health endpoint
ansible -i inventories/prod.yml hr_vps \
  -m uri -a "url=http://localhost:8080/health"

# View logs
ansible -i inventories/prod.yml hr_vps \
  -m shell -a "journalctl -u aio-hr -n 100"
```

### Updates

**Railway:**
```bash
# Update Terraform configuration
cd terraform/railway
nano terraform.tfvars  # Update image_version

# Apply update
terraform apply
```

**VPS:**
```bash
# Update Ansible inventory
nano ansible/inventories/prod.yml  # Update image_version

# Deploy update
ansible-playbook -i inventories/prod.yml aio-vps.yml
```

### Rollback

**Railway:**
```bash
# Revert to previous version
cd terraform/railway
terraform apply -var="image_version=v1.0.0"
```

**VPS:**
```bash
# Rollback to previous version
ansible-playbook -i inventories/prod.yml \
  -e image_version=v1.0.0 \
  aio-vps.yml
```

### Deprovisioning

**Railway:**
```bash
# Destroy all resources
cd terraform/railway
terraform destroy
```

**VPS:**
```bash
# Stop and remove services
ansible-playbook -i inventories/prod.yml \
  -e department_id=hr \
  deprovision.yml
```

---

## Cost Analysis

### Railway (PaaS)

| Departments | Base Cost | Autoscaling | Total/Month | Per Dept |
|-------------|-----------|-------------|-------------|----------|
| 1-10        | $1,500    | $0-1,000    | $1,500-2,500 | $150-250 |
| 11-25       | $3,750    | $0-2,500    | $3,750-6,250 | $150-250 |
| 26-50       | $7,500    | $0-5,000    | $7,500-12,500 | $150-250 |

### VPS (Self-hosted)

| Departments | App Servers | DB Servers | Total/Month | Per Dept |
|-------------|-------------|------------|-------------|----------|
| 1-10        | 1 ($100)    | 1 ($200)   | $300        | $30      |
| 11-25       | 3 ($300)    | 1 ($200)   | $500        | $20      |
| 26-50       | 5 ($500)    | 2 ($400)   | $900        | $18      |
| 51-100      | 10 ($1,000) | 3 ($600)   | $1,600      | $16      |

**Break-even point:** 50 departments
**Annual savings (100 depts):** Railway $180k/year vs VPS $19k/year = $161k savings

---

## Monitoring & Alerting

### Prometheus Metrics

```yaml
# Exposed by voice agent on :8080/metrics
aio_requests_total
aio_request_duration_seconds
aio_errors_total
aio_database_connections
aio_tool_calls_total
aio_tool_call_duration_seconds
```

### Health Check Monitoring

```bash
# Railway - automatic health checks via platform
# VPS - cron job runs every 5 minutes

# Manual health check
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "checks": {
    "database": true,
    "livekit": true,
    "llm": true,
    "n8n": true
  },
  "uptime": 86400
}
```

---

## Troubleshooting

### Railway Deployment Fails

```bash
# Check Railway service logs
railway logs --service voice-agent-hr

# Common issues:
# 1. Missing environment variables
railway variables --service voice-agent-hr

# 2. Image pull failure
railway builds --service voice-agent-hr

# 3. Health check timeout
railway status --service voice-agent-hr
```

### VPS Deployment Fails

```bash
# Check Ansible output
ansible-playbook -i inventories/prod.yml aio-vps.yml -vvv

# Common issues:
# 1. SSH connection failed
ansible -i inventories/prod.yml vps_servers -m ping

# 2. Docker service not running
ansible -i inventories/prod.yml vps_servers \
  -m systemd -a "name=docker state=started"

# 3. Port already in use
ansible -i inventories/prod.yml vps_servers \
  -m shell -a "netstat -tulpn | grep 8080"
```

### Health Check Fails

```bash
# Check container logs
docker logs hr_voice_agent

# Check database connectivity
docker exec hr_voice_agent python -c "import psycopg2; ..."

# Check environment variables
docker exec hr_voice_agent env | grep LIVEKIT
```

---

## Security Best Practices

1. **Secrets Management**
   - Use environment variables for all credentials
   - Never commit `.env` or `terraform.tfvars` to git
   - Use Railway's secret manager or Ansible Vault

2. **Network Security**
   - Use private networks for database connections
   - Enable UFW firewall on VPS hosts
   - Restrict SSH access to known IPs

3. **Access Control**
   - Use role-based access control (RBAC)
   - Rotate API keys regularly
   - Audit access logs

4. **Data Protection**
   - Enable PostgreSQL backups
   - Encrypt data at rest and in transit
   - Implement GDPR compliance measures

---

## Quality Gates

Before merging to main:

- [ ] Terraform plan succeeds with no errors
- [ ] Railway API provisions test project successfully
- [ ] VPS playbook deploys to test VM
- [ ] CLI can deploy to both Railway and VPS
- [ ] Health checks pass after deployment
- [ ] Deployment completes in <5 minutes
- [ ] All documentation is complete
- [ ] Example configs are validated

---

## References

- **Deployment Topology**: `../platform-architect/deployment-topology.md`
- **Docker Templates**: `../docker-templates/`
- **Database Schema**: `../database-schema-generator/`
- **API Gateway**: `../api-gateway-template/`

---

## Support

For issues or questions:
- Check logs: `railway logs` or `journalctl -u aio-<dept>`
- Verify configuration: `terraform validate` or `ansible-playbook --check`
- Review deployment status: `node deploy-cli.js list`
- Contact platform team: platform@synrgscaling.com

---

**Last Updated:** 2026-02-06
**Maintainer:** SYNRG Scaling Platform Team
