# API Gateway - Quick Start Guide

**Get running in 2 minutes**

---

## 1. Start Services (Docker Compose)

```bash
cd federation/api-gateway-template

# Start gateway + redis + postgres
docker-compose up -d

# Wait 20 seconds for PostgreSQL to initialize
sleep 20
```

---

## 2. Verify Health

```bash
curl http://localhost:3000/health
```

Expected output:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

---

## 3. Generate JWT Token

```bash
export JWT_SECRET="your-secret-key-min-32-chars-long-change-this-in-production"

export TOKEN=$(node -e "
const jwt = require('jsonwebtoken');
console.log(jwt.sign({
  userId: 'test-user',
  department: 'hr',
  role: 'user',
  permissions: ['read'],
  exp: Math.floor(Date.now() / 1000) + 3600
}, process.env.JWT_SECRET));
")

echo "Token: $TOKEN"
```

---

## 4. Test Cross-Department Query

```bash
curl -X POST http://localhost:3000/api/cross-dept/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "targetDepartment": "sales",
    "query": "SELECT * FROM test_data LIMIT 5",
    "reason": "Test query from HR to Sales"
  }' | jq '.'
```

Expected output:
```json
{
  "success": true,
  "data": {
    "results": [
      { "id": 1, "name": "Lead 1", "department": "sales" },
      ...
    ],
    "count": 5,
    "executionTimeMs": 45,
    "targetDepartment": "sales"
  }
}
```

---

## 5. View Audit Logs

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/cross-dept/audit-logs?limit=10 | jq '.'
```

---

## 6. Run Full Test Suite

```bash
./test-queries.sh
```

Runs 13 tests covering:
- Health checks
- JWT authentication
- Cross-dept queries
- Invalid queries (blocked)
- Audit logging
- Rate limiting
- Permissions

---

## 7. View Logs

```bash
# Gateway logs
docker-compose logs -f api-gateway

# Redis logs
docker-compose logs redis

# PostgreSQL logs
docker-compose logs postgres
```

---

## 8. Stop Services

```bash
docker-compose down
```

---

## Common Issues

### "Redis connection error"
```bash
docker-compose restart redis
```

### "Database connection failed"
```bash
docker-compose restart postgres
sleep 10  # Wait for PostgreSQL to be ready
```

### "JWT verification failed"
Ensure `JWT_SECRET` environment variable matches between token generation and gateway.

---

## Next Steps

1. Read full documentation: `README.md`
2. Configure for production: Edit `.env` (copy from `.env.example`)
3. Deploy to Railway: See `DELIVERABLES.md` section "Deployment"
4. Set up monitoring: Add Prometheus metrics endpoint

---

**Built by API Gateway Template Agent**
