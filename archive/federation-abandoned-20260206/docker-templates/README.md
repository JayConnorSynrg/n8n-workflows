# Federation AIO Voice Agent - Docker Template System

**Version:** 1.0.0
**Platform:** Multi-tenant AIO voice assistant provisioning
**Architecture:** Multi-stage Docker builds for <500MB images

---

## Overview

This directory contains the pre-loaded AIO container template used by the Federation platform to provision department-specific voice assistant instances. The template includes:

- **Multi-stage Dockerfile** for optimized image size
- **Dynamic entrypoint** for department-specific configuration
- **Health check system** for Railway/Kubernetes
- **Multi-architecture support** (amd64, arm64)
- **Security best practices** (non-root user, minimal dependencies)

---

## Directory Structure

```
docker-templates/
├── aio-base.Dockerfile          # Multi-stage Dockerfile
├── entrypoint.sh                # Dynamic configuration generator
├── healthcheck.py               # Health check implementation
├── requirements.txt             # Python dependencies
├── build-and-push.sh            # Build & publish script
├── .dockerignore                # Build context exclusions
├── docker-compose.test.yml      # Local testing setup
├── README.md                    # This file
└── tests/
    ├── test-build.sh            # Build validation tests
    └── init-db.sql              # PostgreSQL test schema
```

---

## Quick Start

### 1. Build the Docker Image

```bash
# Local build for testing
cd federation/docker-templates
./build-and-push.sh dev

# Production build with version
./build-and-push.sh v1.0.0
```

### 2. Test Locally with Docker Compose

```bash
# Start test environment (HR + Accounting departments)
docker-compose -f docker-compose.test.yml up

# Test HR department
curl http://localhost:8080/health

# Test Accounting department
curl http://localhost:8081/health
```

### 3. Run Build Validation Tests

```bash
cd tests
./test-build.sh
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DEPARTMENT_ID` | Unique department identifier (slug) | `hr`, `accounting`, `sales` |
| `DEPARTMENT_NAME` | Human-readable department name | `Human Resources` |
| `POSTGRES_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `N8N_WEBHOOK_BASE` | n8n webhook base URL | `https://jayconnorexe.app.n8n.cloud/webhook` |
| `LIVEKIT_URL` | LiveKit WebRTC URL | `wss://livekit.example.com` |
| `LIVEKIT_API_KEY` | LiveKit API key | `API_KEY` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `API_SECRET` |
| `CEREBRAS_API_KEY` | Cerebras LLM API key | `csk-xxx` |
| `DEEPGRAM_API_KEY` | Deepgram STT API key | `xxx` |
| `CARTESIA_API_KEY` | Cartesia TTS API key | `xxx` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_SCHEMA` | PostgreSQL schema name | `{DEPARTMENT_ID}_tenant` |
| `ENABLED_TOOLS` | JSON array of enabled tools | `["email","google_drive","database","vector_store","agent_context"]` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `AGENT_NAME` | Voice assistant name | `{DEPARTMENT_NAME} Voice Assistant` |
| `CEREBRAS_MODEL` | LLM model | `llama-3.3-70b` |
| `CEREBRAS_TEMPERATURE` | LLM temperature | `0.6` |
| `CEREBRAS_MAX_TOKENS` | Max tokens per response | `150` |
| `DEEPGRAM_MODEL` | STT model | `nova-3` |
| `CARTESIA_MODEL` | TTS model | `sonic-3` |
| `CARTESIA_VOICE` | TTS voice ID | `a167e0f3-df7e-4d52-a9c3-f949145efdab` |

---

## Build Specifications

### Image Size Optimization

The multi-stage Dockerfile is optimized for minimal final image size:

- **Builder stage**: Installs build dependencies and compiles packages
- **Runtime stage**: Copies only necessary files from builder
- **Target size**: <500MB (typical: 350-450MB)

### Multi-Architecture Support

The build system supports multiple architectures:

```bash
# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/synrgscaling/aio-federation-template:latest \
  --push \
  -f aio-base.Dockerfile .
```

### Security Features

- Non-root user (`agent:1000`)
- Minimal base image (`python:3.11-slim`)
- No development dependencies in final image
- Security scanning with Trivy
- Read-only root filesystem compatible

---

## Configuration Generation

The `entrypoint.sh` script generates department-specific configuration at runtime:

### Generated Configuration File

Located at `/app/config/config.yaml`:

```yaml
department:
  id: "hr"
  name: "Human Resources"
  schema: "hr_tenant"

database:
  url: "postgresql://..."
  schema: "hr_tenant"

n8n:
  base_url: "https://..."
  webhooks:
    drive_repository: "https://.../hr/drive-repository"
    execute_gmail: "https://.../hr/execute-gmail"

livekit:
  url: "wss://..."
  api_key: "..."

llm:
  provider: "cerebras"
  model: "llama-3.3-70b"

# ... (see entrypoint.sh for full structure)
```

---

## Health Check System

The `healthcheck.py` script validates:

1. Configuration file exists and is readable
2. Database connectivity (optional, non-critical)
3. LiveKit credentials are present and valid format
4. LLM (Cerebras) credentials are present
5. STT/TTS credentials are present
6. n8n webhook base URL is configured
7. Agent module can be imported

### Health Check Endpoint

Railway and Kubernetes will use this for liveness/readiness probes:

```bash
# Docker HEALTHCHECK
CMD python /app/healthcheck.py || exit 1

# Manual test
docker exec <container_id> python /app/healthcheck.py
```

---

## Build & Deployment Workflow

### Local Development

```bash
# 1. Build image
./build-and-push.sh dev

# 2. Test with Docker Compose
docker-compose -f docker-compose.test.yml up

# 3. Run validation tests
cd tests && ./test-build.sh
```

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
- name: Build and push Docker image
  run: |
    cd federation/docker-templates
    ./build-and-push.sh ${{ github.ref_name }}

- name: Run build validation tests
  run: |
    cd federation/docker-templates/tests
    ./test-build.sh
```

### Railway Deployment

The Provisioning Orchestrator will deploy this image to Railway:

```bash
# Deploy to Railway
railway up --service aio-hr-prod --environment production

# Set environment variables
railway variables set \
  DEPARTMENT_ID=hr \
  DEPARTMENT_NAME="Human Resources" \
  POSTGRES_URL="postgresql://..." \
  # ... (all required variables)
```

---

## Testing

### Validation Tests

The `tests/test-build.sh` script runs 7 validation tests:

1. **Build succeeds** - Image builds within 5 minutes
2. **Image size** - Final image <500MB
3. **Multi-arch support** - Builds for amd64 + arm64
4. **Container starts** - Starts with valid env vars
5. **Fails gracefully** - Fails with missing env vars
6. **Health check** - Health check script executes
7. **Security scan** - No HIGH/CRITICAL vulnerabilities (Trivy)

### Run Tests

```bash
cd federation/docker-templates/tests
./test-build.sh
```

### Expected Output

```
[INFO] Federation AIO Docker Template - Build Validation Tests
===========================================================
[INFO] Test 1: Build succeeds within 300s
[PASS] Build succeeded in 127s
[INFO] Test 2: Image size < 500MB
[PASS] Image size: 387MB (limit: 500MB)
[INFO] Test 3: Multi-architecture build support
[PASS] Multi-architecture build succeeded (amd64, arm64)
[INFO] Test 4: Container starts with valid env vars
[PASS] Container started and generated config
[INFO] Test 5: Container fails gracefully with missing env vars
[PASS] Container failed with expected error message
[INFO] Test 6: Health check script executes
[PASS] Health check script executed successfully
[INFO] Test 7: Security vulnerability scan
[PASS] No HIGH/CRITICAL vulnerabilities found

===========================================================
Test Results Summary
===========================================================
Passed: 7
Failed: 0

[PASS] ALL TESTS PASSED
```

---

## Troubleshooting

### Build Fails with "source not found"

The build script automatically copies the AIO source code from `../../voice-agent-poc/livekit-voice-agent/src`. Ensure this path exists.

### Container exits immediately

Check logs for missing environment variables:

```bash
docker logs <container_id>
```

Expected error: `[FATAL] Missing required environment variables: ...`

### Health check fails

Run health check manually to see detailed output:

```bash
docker exec <container_id> python /app/healthcheck.py
```

### Image size exceeds 500MB

Check Dockerfile layers:

```bash
docker history aio-federation-template:latest
```

Optimize by:
- Removing unnecessary dependencies
- Cleaning apt cache
- Using `.dockerignore` effectively

---

## Integration with Federation Platform

This Docker template is used by the Federation Provisioning Orchestrator:

```typescript
// Provisioning Orchestrator (src/docker/deployer.ts)
const deploymentConfig = {
  image: 'ghcr.io/synrgscaling/aio-federation-template:latest',
  environment: {
    DEPARTMENT_ID: 'hr',
    DEPARTMENT_NAME: 'Human Resources',
    POSTGRES_URL: 'postgresql://...',
    // ... (all required variables)
  }
};

await railwayAPI.deployService(deploymentConfig);
```

---

## Quality Gates

Before merging to main:

- [ ] All 7 build validation tests pass
- [ ] Image size <500MB
- [ ] Multi-architecture builds succeed
- [ ] Security scan shows no HIGH/CRITICAL vulnerabilities
- [ ] Docker Compose test environment runs successfully
- [ ] Health check responds correctly
- [ ] Documentation is complete

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial release with multi-stage Dockerfile |

---

## References

- **Architecture Blueprint**: `../platform-architect/architecture-blueprint.md`
- **Existing AIO Voice Agent**: `../../voice-agent-poc/livekit-voice-agent/`
- **AIO Tools Registry**: `../../voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`

---

## Support

For issues or questions:
- Check `TROUBLESHOOTING.md` (if available)
- Review Docker logs: `docker logs <container_id>`
- Verify environment variables are correctly set
- Test with `docker-compose.test.yml` first
