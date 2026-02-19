# Provisioning Orchestrator - Deployment Guide

Quick reference for deploying the provisioning orchestrator to production.

## Pre-Deployment Checklist

- [ ] PostgreSQL database created
- [ ] Environment variables configured
- [ ] JWT secret generated
- [ ] External service API keys obtained
- [ ] Railway CLI installed
- [ ] Dependencies installed (`npm install`)
- [ ] TypeScript compiled (`npm run build`)
- [ ] Tests passing (`npm test`)

## Environment Variables

Create `.env` file:

```bash
# Server
PORT=3000
NODE_ENV=production

# JWT
JWT_SECRET=<generate-with: openssl rand -base64 32>

# Database
DB_HOST=<postgresql-host>
DB_PORT=5432
DB_NAME=federation
DB_USER=<username>
DB_PASSWORD=<password>

# Railway
RAILWAY_API_TOKEN=<your-railway-token>

# n8n
N8N_API_KEY=<your-n8n-api-key>
N8N_BASE_URL=https://jayconnorexe.app.n8n.cloud

# Timeouts (milliseconds)
MAX_PROVISIONING_TIME=300000
STEP_TIMEOUT=60000
```

## Railway Deployment

```bash
# 1. Login to Railway
railway login

# 2. Create new project
railway init

# 3. Link to existing project (if applicable)
railway link

# 4. Add environment variables
railway variables set JWT_SECRET=<secret>
railway variables set DB_HOST=<host>
# ... (add all variables)

# 5. Deploy
railway up
```

## Docker Deployment (Alternative)

```dockerfile
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY dist ./dist

EXPOSE 3000

CMD ["node", "dist/api.js"]
```

```bash
# Build
docker build -t provisioning-orchestrator .

# Run
docker run -p 3000:3000 \
  -e JWT_SECRET=<secret> \
  -e DB_HOST=<host> \
  provisioning-orchestrator
```

## Database Setup

Run database migrations:

```sql
-- Create federation schema
CREATE SCHEMA IF NOT EXISTS federation;

-- Create departments table
CREATE TABLE federation.departments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  department_id VARCHAR(100) UNIQUE NOT NULL,
  department_name VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PROVISIONING',
  tenant_schema VARCHAR(63) NOT NULL,
  railway_project_id VARCHAR(255),
  railway_deployment_url TEXT,
  n8n_workflow_ids JSONB,
  enabled_tools JSONB,
  admin_email VARCHAR(255) NOT NULL,
  config JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deprovisioned_at TIMESTAMPTZ
);

-- Create provisioning jobs table
CREATE TABLE federation.provisioning_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  department_id VARCHAR(100) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  progress JSONB NOT NULL DEFAULT '{}',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

-- Create indexes
CREATE INDEX idx_departments_status ON federation.departments(status);
CREATE INDEX idx_provisioning_dept ON federation.provisioning_jobs(department_id);
```

## Health Check

Verify deployment:

```bash
# Health endpoint
curl https://federation.synrg.io/health

# Expected response:
# {"status":"healthy","timestamp":"2026-02-06T..."}
```

## Monitoring

Set up monitoring:

1. **Railway Dashboard**: Monitor CPU, memory, logs
2. **Database Metrics**: Query performance, connection pool
3. **API Metrics**: Request rate, error rate, latency
4. **Alerts**: Set up for provisioning failures

## Troubleshooting

### Issue: Cannot connect to database
- Verify `DB_HOST`, `DB_PORT`, `DB_NAME`
- Check firewall rules
- Test with: `psql -h $DB_HOST -U $DB_USER -d $DB_NAME`

### Issue: JWT token invalid
- Verify `JWT_SECRET` matches across services
- Check token expiration
- Regenerate secret if needed

### Issue: Provisioning timeout
- Increase `MAX_PROVISIONING_TIME`
- Check component service health
- Review logs for bottlenecks

## Rollback

If deployment fails:

```bash
# Railway
railway rollback

# Docker
docker stop <container-id>
docker run <previous-image>
```

## Post-Deployment

1. Test provisioning endpoint
2. Monitor first few provisions
3. Set up alerting
4. Document any issues
5. Update runbook

## Support

For issues:
- Check logs: `railway logs`
- Review metrics: Railway dashboard
- Contact: support@synrgscaling.com
