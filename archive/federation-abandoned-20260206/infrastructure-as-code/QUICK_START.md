# Infrastructure as Code - Quick Start Guide

**Time to First Deployment:** 10 minutes

---

## Prerequisites (5 minutes)

```bash
# 1. Install dependencies (macOS)
brew install terraform ansible node

# 2. Clone repository
cd federation/infrastructure-as-code

# 3. Install Node.js packages
npm install

# 4. Configure environment
cp .env.example .env
nano .env  # Add your API keys
```

---

## Railway Deployment (5 minutes)

```bash
# 1. Create config file
cat > hr-config.json <<EOF
{
  "departmentId": "hr",
  "departmentName": "Human Resources",
  "environment": "prod",
  "dockerRegistry": "ghcr.io/synrgscaling",
  "imageVersion": "latest",
  "n8nWebhookBase": "https://jayconnorexe.app.n8n.cloud/webhook",
  "livekitUrl": "$LIVEKIT_URL",
  "livekitApiKey": "$LIVEKIT_API_KEY",
  "livekitApiSecret": "$LIVEKIT_API_SECRET",
  "cerebrasApiKey": "$CEREBRAS_API_KEY",
  "cerebrasModel": "llama-3.3-70b",
  "deepgramApiKey": "$DEEPGRAM_API_KEY",
  "deepgramModel": "nova-3",
  "cartesiaApiKey": "$CARTESIA_API_KEY",
  "cartesiaModel": "sonic-3",
  "cartesiaVoice": "a167e0f3-df7e-4d52-a9c3-f949145efdab",
  "enabledTools": ["email", "google_drive", "database"],
  "postgresStorage": 10,
  "voiceAgentCpu": "2000m",
  "voiceAgentMemory": "4096Mi"
}
EOF

# 2. Deploy
npm run build
node deploy-cli.js deploy railway hr-config.json

# 3. Verify
curl https://aio-hr-prod.railway.app/health
```

---

## VPS Deployment (15 minutes)

```bash
# 1. Configure inventory
nano ansible/inventories/prod.yml

# Add your VPS:
# vps-01:
#   ansible_host: YOUR_VPS_IP
#   ansible_user: ubuntu

# 2. Test connection
cd ansible
ansible -i inventories/prod.yml vps_servers -m ping

# 3. Deploy
ansible-playbook -i inventories/prod.yml \
  -e department_id=hr \
  -e department_name="Human Resources" \
  aio-vps.yml

# 4. Verify
ssh ubuntu@YOUR_VPS_IP
curl http://localhost:8080/health
```

---

## Common Commands

```bash
# List deployments
node deploy-cli.js list prod

# Check health
curl https://aio-hr-prod.railway.app/health

# View logs (Railway)
railway logs --service voice-agent-hr --tail

# View logs (VPS)
ssh ubuntu@VPS_IP "journalctl -u aio-hr -n 100"

# Delete deployment
node deploy-cli.js delete <project-id>
```

---

## Troubleshooting

### Deployment fails with "Missing RAILWAY_API_TOKEN"
```bash
# Export Railway token
export RAILWAY_API_TOKEN="your_token_here"
```

### Health check fails
```bash
# Check environment variables
railway variables --service voice-agent-hr

# Check logs
railway logs --service voice-agent-hr
```

### Ansible connection timeout
```bash
# Test SSH connection
ssh ubuntu@YOUR_VPS_IP

# Check firewall
ansible -i inventories/prod.yml vps_servers \
  -m shell -a "ufw status"
```

---

## Next Steps

1. **Scale to Multiple Departments**
   - Create configs for each department
   - Deploy in parallel using script

2. **Set Up Monitoring**
   - Configure Prometheus metrics
   - Set up Grafana dashboards

3. **Enable Backups**
   - Configure S3 bucket
   - Set backup schedule

4. **Production Hardening**
   - Enable autoscaling
   - Configure custom domains
   - Set up CI/CD pipeline

---

**Full Documentation:** See README.md
