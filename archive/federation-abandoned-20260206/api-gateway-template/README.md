# Federation API Gateway

**Version:** 1.0.0
**Status:** Production Ready

Secure API gateway for cross-department data queries with JWT authentication, Redis-backed rate limiting, and comprehensive audit logging.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [API Endpoints](#api-endpoints)
7. [Authentication](#authentication)
8. [Rate Limiting](#rate-limiting)
9. [Audit Logging](#audit-logging)
10. [Deployment](#deployment)
11. [Security](#security)
12. [Testing](#testing)
13. [Monitoring](#monitoring)

---

## Overview

The Federation API Gateway is a secure middleware layer that enables controlled cross-department data access within a multi-tenant architecture. It enforces:

- **JWT-based authentication** with department-scoped claims
- **Rate limiting** (100 req/15min general, 10 req/hour cross-dept)
- **Audit logging** (all queries logged to PostgreSQL)
- **Permission-based access control** (explicit grants required)
- **Query validation** (SQL injection prevention, read-only enforcement)

---

## Features

### Security
- ✅ JWT authentication with HS256 signing
- ✅ Department-scoped authorization
- ✅ SQL injection prevention
- ✅ Read-only query enforcement
- ✅ TLS 1.3 ready
- ✅ Helmet.js security headers

### Rate Limiting
- ✅ Redis-backed distributed rate limiting
- ✅ Per-department general limits (100/15min)
- ✅ Per-department-pair cross-dept limits (10/hour)
- ✅ Auth endpoint brute force protection (5/15min)

### Audit Logging
- ✅ All cross-dept queries logged to PostgreSQL
- ✅ Query content, reason, and results captured
- ✅ Department statistics and analytics
- ✅ 2-year retention policy (configurable)

### Query Engine
- ✅ Row-Level Security (RLS) enforced
- ✅ Schema-scoped queries (no cross-schema leakage)
- ✅ Permission checks before execution
- ✅ Query validation (blacklist dangerous operations)

---

## Architecture

```mermaid
graph TB
    subgraph "External Clients"
        CLIENT[Department Agents<br/>JWT Bearer Token]
    end

    subgraph "API Gateway"
        EXPRESS[Express Server]
        AUTH[Auth Middleware<br/>JWT Validation]
        RATE[Rate Limiter<br/>Redis Store]
        AUDIT[Audit Logger<br/>PostgreSQL]
        QUERY[Query Handler<br/>RLS Enforced]
    end

    subgraph "Data Stores"
        REDIS[(Redis<br/>Rate Limit State)]
        POSTGRES[(PostgreSQL<br/>Audit Logs + Permissions)]
    end

    CLIENT -->|HTTPS + JWT| EXPRESS
    EXPRESS --> AUTH
    AUTH --> RATE
    RATE --> AUDIT
    AUDIT --> QUERY

    RATE -.-> REDIS
    AUDIT -.-> POSTGRES
    QUERY -.-> POSTGRES
```

### Request Flow

1. **Client** sends request with `Authorization: Bearer <JWT>`
2. **Auth Middleware** validates JWT, extracts department claims
3. **Rate Limiter** checks Redis for rate limit state
4. **Audit Logger** prepares to log request/response
5. **Query Handler** validates query, checks permissions, executes with RLS
6. **Response** returned to client with audit log ID

---

## Quick Start

### Prerequisites

- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+ (or use Docker)
- Redis 7+ (or use Docker)

### Local Development

```bash
# Clone repository
cd federation/api-gateway-template

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start dependencies (Redis + PostgreSQL)
docker-compose up -d redis postgres

# Wait for PostgreSQL to initialize (10 seconds)
sleep 10

# Build TypeScript
npm run build

# Start API gateway
npm start
```

Gateway will be available at `http://localhost:3000`

### Using Docker Compose (Recommended)

```bash
# Start all services (API Gateway + Redis + PostgreSQL)
docker-compose up -d

# View logs
docker-compose logs -f api-gateway

# Check health
curl http://localhost:3000/health

# Stop services
docker-compose down
```

---

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Server
NODE_ENV=development
PORT=3000

# JWT (CRITICAL: Change in production)
JWT_SECRET=your-secret-key-min-32-chars-long-change-this-in-production

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/federation

# Redis
REDIS_URL=redis://localhost:6379

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000          # 15 minutes
RATE_LIMIT_MAX=100                    # 100 requests per window
CROSS_DEPT_RATE_LIMIT_WINDOW_MS=3600000  # 1 hour
CROSS_DEPT_RATE_LIMIT_MAX=10          # 10 requests per window

# CORS
ALLOWED_ORIGINS=*
```

### Generate Secure JWT Secret

```bash
# Generate 32-byte secret key
openssl rand -hex 32
```

### Database Setup

If not using Docker, manually initialize the database:

```bash
# Connect to PostgreSQL
psql -U postgres -d federation -f init-db.sql
```

---

## API Endpoints

### Public Endpoints

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T18:00:00.000Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

#### `GET /`
API information.

---

### Authenticated Endpoints

All `/api/*` endpoints require JWT authentication.

#### `POST /api/cross-dept/query`
Execute cross-department query.

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Request Body:**
```json
{
  "targetDepartment": "sales",
  "query": "SELECT * FROM test_data LIMIT 10",
  "reason": "Quarterly sales analysis for HR report",
  "resourceType": "test_data"
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "results": [
      { "id": 1, "name": "Lead 1", "department": "sales" }
    ],
    "count": 1,
    "executionTimeMs": 45,
    "targetDepartment": "sales"
  },
  "meta": {
    "timestamp": "2026-02-06T18:00:00.000Z"
  }
}
```

**Response (Forbidden):**
```json
{
  "error": "Forbidden",
  "message": "Cross-department access denied",
  "details": "Check permissions or contact administrator"
}
```

#### `GET /api/cross-dept/audit-log/:logId`
Retrieve specific audit log entry.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "audit_1738855200000_abc123",
    "timestamp": "2026-02-06T18:00:00.000Z",
    "sourceDepartment": "hr",
    "targetDepartment": "sales",
    "userId": "user123",
    "operation": "query",
    "query": "SELECT * FROM test_data LIMIT 10",
    "reason": "Quarterly sales analysis",
    "allowed": true,
    "resultCount": 10,
    "executionTimeMs": 45,
    "ipAddress": "192.168.1.1"
  }
}
```

#### `GET /api/cross-dept/audit-logs`
List audit logs for your department.

**Query Parameters:**
- `startDate` (ISO 8601): Start date filter
- `endDate` (ISO 8601): End date filter
- `userId` (string): User ID filter
- `allowed` (boolean): Filter by allowed/denied
- `limit` (number): Max results (default 1000)

#### `GET /api/cross-dept/stats`
Get department statistics.

**Query Parameters:**
- `startDate` (ISO 8601): Start date
- `endDate` (ISO 8601): End date

**Response:**
```json
{
  "success": true,
  "data": {
    "totalQueries": 150,
    "successfulQueries": 140,
    "failedQueries": 10,
    "averageExecutionTime": 52,
    "topTargetDepartments": [
      { "department": "sales", "count": 80 },
      { "department": "legal", "count": 60 }
    ]
  }
}
```

#### `GET /api/cross-dept/permissions`
List permissions for your department.

#### `POST /api/cross-dept/permissions/grant` (Admin Only)
Grant cross-department permission.

**Request Body:**
```json
{
  "sourceDepartment": "hr",
  "targetDepartment": "sales",
  "permissionType": "read",
  "resourceType": "*",
  "expiresAt": "2027-02-06T18:00:00.000Z"
}
```

#### `POST /api/cross-dept/permissions/revoke` (Admin Only)
Revoke cross-department permission.

#### `GET /api/cross-dept/tables/:department`
List accessible tables in target department.

#### `GET /api/cross-dept/schema/:department/:table`
Get schema information for a table.

---

## Authentication

### JWT Token Format

Tokens contain department-scoped claims:

```json
{
  "userId": "user123",
  "department": "hr",
  "role": "user",
  "permissions": ["read", "search"],
  "iat": 1738855200,
  "exp": 1738941600
}
```

### Generating Tokens (Server-Side)

```typescript
import { generateToken } from './auth-middleware';

const token = generateToken({
  userId: 'user123',
  department: 'hr',
  role: 'user',
  permissions: ['read', 'search'],
  expiresIn: 86400 // 24 hours
});
```

### Using Tokens (Client-Side)

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     -H "Content-Type: application/json" \
     -d '{"targetDepartment":"sales","query":"SELECT * FROM test_data","reason":"Analysis"}' \
     http://localhost:3000/api/cross-dept/query
```

---

## Rate Limiting

### Rate Limit Tiers

| Tier | Window | Limit | Key |
|------|--------|-------|-----|
| General | 15 minutes | 100 requests | Department ID |
| Cross-Dept | 1 hour | 10 requests | Source-Target pair |
| Auth | 15 minutes | 5 attempts | IP address |

### Rate Limit Headers

Responses include rate limit information:

```
RateLimit-Limit: 100
RateLimit-Remaining: 95
RateLimit-Reset: 1738855200
```

### Rate Limit Exceeded

```json
{
  "error": "Rate limit exceeded",
  "message": "Your department has exceeded the rate limit. Please try again later.",
  "retryAfter": "Check Retry-After header"
}
```

---

## Audit Logging

### What is Logged?

All cross-department queries capture:
- Source and target departments
- User ID and IP address
- Query content and reason
- Success/failure status
- Result count
- Execution time
- User agent

### Retention Policy

- **Default:** 2 years
- **Configurable:** Modify `cleanupOldLogs()` function
- **Cleanup:** Manual or cron-scheduled

### Retrieving Audit Logs

```bash
# Get specific log
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:3000/api/cross-dept/audit-log/audit_1738855200000_abc123

# List department logs
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:3000/api/cross-dept/audit-logs?startDate=2026-01-01&limit=100"

# Get statistics
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:3000/api/cross-dept/stats?startDate=2026-01-01&endDate=2026-02-01"
```

---

## Deployment

### Production Checklist

- [ ] Generate secure JWT secret (`openssl rand -hex 32`)
- [ ] Configure production DATABASE_URL
- [ ] Configure production REDIS_URL
- [ ] Set NODE_ENV=production
- [ ] Configure ALLOWED_ORIGINS (no wildcards)
- [ ] Enable TLS/SSL for PostgreSQL
- [ ] Set up PostgreSQL backups
- [ ] Configure Redis persistence (AOF)
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Configure log aggregation (ELK stack)
- [ ] Set up alerting (PagerDuty)

### Railway Deployment

```bash
# Install Railway CLI
npm install -g railway

# Login
railway login

# Link project
railway link

# Set environment variables
railway variables set JWT_SECRET=$(openssl rand -hex 32)
railway variables set DATABASE_URL=postgresql://...
railway variables set REDIS_URL=redis://...

# Deploy
railway up
```

### Docker Production Deployment

```bash
# Build image
docker build -t federation-api-gateway:1.0.0 .

# Run container
docker run -d \
  -p 3000:3000 \
  -e NODE_ENV=production \
  -e JWT_SECRET=your-secret \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  --name federation-gateway \
  federation-api-gateway:1.0.0
```

---

## Security

### Query Validation

Queries are validated to prevent:
- SQL injection
- Schema hopping
- Write operations (INSERT, UPDATE, DELETE)
- DDL operations (CREATE, DROP, ALTER)
- System catalog access
- Multiple statements
- SQL comments

### Blacklisted Keywords

```
DELETE, DROP, TRUNCATE, ALTER, GRANT, REVOKE, INSERT, UPDATE,
CREATE, REPLACE, EXEC, EXECUTE, CALL, SET, COMMIT, ROLLBACK
```

### Row-Level Security (RLS)

Queries execute with `cross_dept_query_user` role:
- Read-only access to tenant schemas
- RLS policies enforced at database level
- No schema hopping allowed

### Permission Model

Permissions are **explicit grants** (not default allow):
- Source department
- Target department
- Permission type (read, search, aggregate)
- Resource type (table name or wildcard)
- Optional expiration date

---

## Testing

### Unit Tests

```bash
npm test
```

### Integration Tests

```bash
# Start test environment
docker-compose up -d

# Run integration tests
npm run test:integration
```

### Manual Testing

```bash
# Generate test token
node -e "
const jwt = require('jsonwebtoken');
const token = jwt.sign({
  userId: 'test-user',
  department: 'hr',
  role: 'user',
  permissions: ['read'],
  exp: Math.floor(Date.now() / 1000) + 3600
}, 'your-jwt-secret');
console.log(token);
"

# Test query
curl -X POST http://localhost:3000/api/cross-dept/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetDepartment": "sales",
    "query": "SELECT * FROM test_data LIMIT 5",
    "reason": "Test query"
  }'
```

---

## Monitoring

### Health Check

```bash
# Check gateway health
curl http://localhost:3000/health

# Expected response
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

### Metrics

Monitor:
- Request rate (requests/minute)
- Error rate (errors/minute)
- Response time (P50, P95, P99)
- Rate limit hits
- Auth failures
- Cross-dept queries (successful/failed)

### Logs

```bash
# Docker logs
docker-compose logs -f api-gateway

# Railway logs
railway logs

# Filter by level
docker-compose logs api-gateway | grep ERROR
```

---

## Troubleshooting

### Connection Refused (Redis)

**Symptom:** `Redis connection error: ECONNREFUSED`

**Solution:**
```bash
# Check Redis status
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### JWT Verification Failed

**Symptom:** `Invalid token` or `Token expired`

**Solution:**
- Verify JWT_SECRET matches between token generation and gateway
- Check token expiration (exp claim)
- Ensure token format is `Bearer <token>`

### Permission Denied

**Symptom:** `Cross-department access denied`

**Solution:**
```sql
-- Check permissions
SELECT * FROM federation.cross_dept_permissions
WHERE source_department_id = 'hr' AND target_department_id = 'sales';

-- Grant permission
INSERT INTO federation.cross_dept_permissions (...) VALUES (...);
```

### Rate Limit Not Working

**Symptom:** No rate limiting applied

**Solution:**
- Check Redis connection
- Verify REDIS_URL environment variable
- Check rate limiter middleware is applied

---

## License

MIT License - See LICENSE file for details

---

## Support

For issues or questions:
- Create GitHub issue
- Contact: federation-team@example.com
- Documentation: `/docs/`

---

**Built with ❤️ by the Federation Platform Team**
