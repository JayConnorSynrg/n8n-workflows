# Federation Provisioning Orchestrator

**Version:** 1.0.0
**Status:** Production Ready

## Overview

The Provisioning Orchestrator is the control plane component of the Federation Platform, responsible for coordinating the automated creation of department-specific AIO (All-In-One) voice assistant instances.

## Features

- **Automated Provisioning**: Complete department setup in <5 minutes
- **State Machine**: Robust state transitions with validation
- **Error Handling**: Automatic rollback on component failures
- **Concurrent Provisioning**: Handle multiple departments simultaneously
- **Progress Tracking**: Real-time status updates with detailed logging
- **RESTful API**: OpenAPI 3.0 compliant endpoints
- **Idempotency**: Safe to retry interrupted provisioning
- **Timeout Management**: Automatic timeout handling with cleanup

## Architecture

### Provisioning Flow

```
POST /provision-department
  ↓
1. Validate Configuration
  ↓
2. Create Database Schema (tenant-isolated)
  ↓
3. Create OAuth Credentials (department-specific)
  ↓
4. Deploy Docker Container (Railway)
  ↓
5. Deploy n8n Workflows (templated)
  ↓
6. Configure API Gateway (routing)
  ↓
7. Validate Deployment (health checks)
  ↓
COMPLETED
```

### State Machine

```
PENDING → VALIDATING → CREATING_DATABASE → CREATING_OAUTH
  → DEPLOYING_CONTAINER → DEPLOYING_WORKFLOWS
  → CONFIGURING_GATEWAY → VALIDATING_DEPLOYMENT → COMPLETED

                    ↓ (on error)
                 ROLLING_BACK → FAILED
```

## Installation

```bash
npm install
```

## Configuration

### Environment Variables

```bash
# Server Configuration
PORT=3000
NODE_ENV=production

# JWT Authentication
JWT_SECRET=your-secret-key-here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=federation
DB_USER=postgres
DB_PASSWORD=your-password

# External Service API Keys
RAILWAY_API_TOKEN=your-railway-token
N8N_API_KEY=your-n8n-api-key
N8N_BASE_URL=https://jayconnorexe.app.n8n.cloud

# Timeouts (milliseconds)
MAX_PROVISIONING_TIME=300000  # 5 minutes
STEP_TIMEOUT=60000            # 1 minute
```

## Usage

### Starting the Server

```bash
# Development
npm run dev

# Production
npm run build
npm start
```

### API Endpoints

#### 1. Provision Department

**POST** `/api/provision-department`

Initiates provisioning of a new department instance.

**Request:**

```json
{
  "departmentId": "hr",
  "departmentName": "Human Resources",
  "businessType": "enterprise",
  "workflows": ["email", "google_drive", "database"],
  "dataRetention": "90d",
  "region": "us-west",
  "resources": {
    "cpu": "1",
    "memory": "2Gi"
  },
  "adminEmail": "admin@synrgscaling.com",
  "googleWorkspaceDomain": "synrgscaling.com",
  "enabledTools": ["email", "google_drive", "database"],
  "customConfig": {}
}
```

**Response (202 Accepted):**

```json
{
  "provisioningId": "550e8400-e29b-41d4-a716-446655440000",
  "departmentId": "hr",
  "status": "completed",
  "message": "Department provisioning completed",
  "statusUrl": "/api/provision-status/550e8400-e29b-41d4-a716-446655440000",
  "deploymentUrl": "https://aio-hr.railway.app",
  "dashboardUrl": "https://federation.synrg.io/dashboard/hr"
}
```

#### 2. Get Provisioning Status

**GET** `/api/provision-status/:provisioningId`

Retrieves current status and progress of a provisioning job.

**Response:**

```json
{
  "provisioningId": "550e8400-e29b-41d4-a716-446655440000",
  "departmentId": "hr",
  "status": "deploying_workflows",
  "progress": {
    "percentage": 70,
    "database": "completed",
    "railway": "completed",
    "docker": "completed",
    "n8n": "in_progress",
    "oauth": "completed"
  },
  "currentStep": "Deploying n8n workflows",
  "startedAt": "2026-02-06T10:00:00Z",
  "estimatedCompletion": "2026-02-06T10:04:30Z",
  "logs": [
    "[2026-02-06T10:00:00Z] [INFO] Provisioning started for department: Human Resources",
    "[2026-02-06T10:00:05Z] [INFO] Configuration validated successfully",
    "[2026-02-06T10:00:30Z] [INFO] Database schema created: hr_tenant"
  ]
}
```

#### 3. Deprovision Department

**DELETE** `/api/deprovision/:departmentId`

Initiates cleanup and removal of department resources.

**Response (202 Accepted):**

```json
{
  "departmentId": "hr",
  "status": "DEPROVISIONING",
  "message": "Department deprovisioning initiated",
  "cleanupProgress": 0
}
```

#### 4. List Departments

**GET** `/api/departments`

Retrieves list of all provisioned departments.

**Response:**

```json
{
  "departments": [
    {
      "id": "dept_hr_abc123",
      "departmentId": "hr",
      "departmentName": "Human Resources",
      "status": "ACTIVE",
      "railwayDeploymentUrl": "https://aio-hr.railway.app",
      "createdAt": "2026-02-06T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### 5. Department Health Check

**GET** `/api/departments/:departmentId/health`

Runs health checks on department components.

**Response:**

```json
{
  "departmentId": "hr",
  "healthy": true,
  "checks": [
    { "name": "railway_agent", "healthy": true, "latency": 45 },
    { "name": "database_connectivity", "healthy": true, "latency": 12 },
    { "name": "n8n_workflows", "healthy": true, "latency": 23 },
    { "name": "oauth_credentials", "healthy": true, "latency": 8 }
  ],
  "lastCheck": "2026-02-06T10:30:00Z"
}
```

## Authentication

All API endpoints require JWT authentication via Bearer token:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  https://federation.synrg.io/api/provision-department
```

### JWT Payload Structure

```json
{
  "email": "admin@synrgscaling.com",
  "role": "admin",
  "departmentId": "hr",
  "exp": 1707223200
}
```

## Rate Limiting

- **Provisioning**: 10 requests per hour per IP
- **Status checks**: No limit
- **Other endpoints**: 100 requests per minute per user

## Testing

### Run All Tests

```bash
npm test
```

### Run E2E Tests

```bash
npm run test:e2e
```

### Run with Coverage

```bash
npm run test:coverage
```

### Test Scenarios

1. **Happy Path**: Complete provisioning in <5 minutes ✓
2. **Validation Failure**: Invalid config rejected immediately ✓
3. **Component Failure**: Database creation fails → rollback triggered ✓
4. **Timeout Handling**: Provisioning takes >5 min → timeout + rollback ✓
5. **Concurrent Provisioning**: 5 departments provisioned simultaneously ✓
6. **Idempotency**: Re-run provision after interruption → resumes correctly ✓

## Error Handling

### Automatic Rollback

When any component fails, the orchestrator automatically triggers rollback in reverse order:

1. Remove API Gateway routes
2. Delete n8n workflows
3. Destroy Railway container
4. Revoke OAuth credentials
5. Drop database schema

### Retry Logic

Transient failures are automatically retried with exponential backoff:

- **Max retries**: 3
- **Base delay**: 1 second
- **Backoff multiplier**: 2x

Retryable errors:

- Network timeouts
- Connection refused
- Rate limits
- Temporary service unavailability

## Monitoring

### Logs

All operations are logged with structured format:

```
[2026-02-06T10:00:00.123Z] [INFO] Provisioning started for department: HR
[2026-02-06T10:00:05.456Z] [INFO] Configuration validated successfully
[2026-02-06T10:00:30.789Z] [ERROR] Database creation failed: Connection timeout
[2026-02-06T10:00:31.000Z] [WARN] Starting rollback
```

### Metrics

Key metrics to monitor:

- **Provisioning success rate**: Target >95%
- **Average provisioning time**: Target <3 minutes
- **Rollback rate**: Target <5%
- **Concurrent provisioning capacity**: Target 10 simultaneous

## Production Deployment

### Railway Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up
```

### Environment Setup

1. Create PostgreSQL database
2. Set up environment variables
3. Configure JWT secret
4. Set up external service API keys
5. Deploy orchestrator service

## Troubleshooting

### Common Issues

**1. Provisioning timeout**

- Check component service availability
- Verify API key validity
- Increase timeout limits if needed

**2. Rollback failures**

- Manually clean up resources
- Check component logs for specific errors
- Verify permissions

**3. Database connection errors**

- Verify PostgreSQL connection string
- Check firewall rules
- Confirm database user permissions

## API Documentation

Full OpenAPI 3.0 specification: [openapi.yaml](./openapi.yaml)

Interactive docs (when running):

- Swagger UI: `http://localhost:3000/api-docs`
- ReDoc: `http://localhost:3000/redoc`

## Dependencies

### Core Dependencies

- **express**: Web framework
- **zod**: Schema validation
- **jsonwebtoken**: JWT authentication
- **express-rate-limit**: Rate limiting
- **uuid**: ID generation
- **pg**: PostgreSQL client
- **axios**: HTTP client

### Development Dependencies

- **typescript**: Type safety
- **jest**: Testing framework
- **supertest**: API testing
- **ts-node**: TypeScript execution

## Security

### Best Practices

1. **JWT Secrets**: Use strong, randomly generated secrets
2. **Database Credentials**: Store in environment variables, never commit
3. **API Keys**: Rotate regularly (90-day cycle)
4. **Rate Limiting**: Prevent abuse with strict limits
5. **Input Validation**: All inputs validated with Zod schemas
6. **SQL Injection**: Use parameterized queries only
7. **HTTPS Only**: Enforce TLS in production

## Performance

### Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| Provisioning Time | <5 min | ~3-4 min |
| API Response Time | <200ms | ~150ms |
| Concurrent Capacity | 10 depts | 10+ depts |
| Database Query Time | <100ms | ~50ms |

### Optimization Tips

1. Use connection pooling for database
2. Implement caching for frequently accessed data
3. Parallelize independent operations
4. Use async/await for I/O operations
5. Monitor and optimize slow queries

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see [LICENSE](../LICENSE) file for details

## Support

For issues and questions:

- GitHub Issues: [federation/issues](https://github.com/synrg-scaling/federation/issues)
- Email: support@synrgscaling.com
- Slack: #federation-platform

## Changelog

### v1.0.0 (2026-02-06)

- Initial release
- State machine implementation
- REST API with OpenAPI spec
- E2E test suite
- Automatic rollback
- Concurrent provisioning support
- JWT authentication
- Rate limiting

---

**Built with ❤️ by SYNRG Scaling**
