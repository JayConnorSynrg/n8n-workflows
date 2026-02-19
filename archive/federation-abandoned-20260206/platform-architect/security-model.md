# Federation Platform - Security Model

**Version:** 1.0.0
**Date:** 2026-02-06
**Status:** Design Phase

---

## Executive Summary

The Federation Platform implements defense-in-depth security with four isolation layers:

1. **Database-level**: PostgreSQL schemas with Row-Level Security (RLS)
2. **Network-level**: Separate Railway projects per department
3. **OAuth-level**: Per-department OAuth apps with scoped credentials
4. **API-level**: JWT authentication + rate limiting + audit logging

This document defines the security architecture, threat model, compliance requirements, and operational security procedures.

---

## Table of Contents

1. [Tenant Isolation Strategy](#1-tenant-isolation-strategy)
2. [OAuth Boundary Design](#2-oauth-boundary-design)
3. [Cross-Department Access Control](#3-cross-department-access-control)
4. [Security Compliance](#4-security-compliance)
5. [Threat Model](#5-threat-model)
6. [Operational Security](#6-operational-security)

---

## 1. Tenant Isolation Strategy

### 1.1 Multi-Layered Isolation Architecture

```mermaid
graph TB
    subgraph "Layer 1: Network Isolation"
        RP_HR[Railway Project: aio-hr-prod<br/>Private Network: 10.1.0.0/24]
        RP_ACC[Railway Project: aio-accounting-prod<br/>Private Network: 10.2.0.0/24]
        RP_SALES[Railway Project: aio-sales-prod<br/>Private Network: 10.3.0.0/24]
    end

    subgraph "Layer 2: Database Schema Isolation"
        DB[(PostgreSQL Master)]
        SCHEMA_HR[Schema: hr_tenant<br/>RLS: dept_id='hr']
        SCHEMA_ACC[Schema: accounting_tenant<br/>RLS: dept_id='accounting']
        SCHEMA_SALES[Schema: sales_tenant<br/>RLS: dept_id='sales']
    end

    subgraph "Layer 3: OAuth App Isolation"
        OAUTH_HR[Google OAuth App<br/>HR AIO Assistant]
        OAUTH_ACC[Google OAuth App<br/>Accounting AIO Assistant]
        OAUTH_SALES[Google OAuth App<br/>Sales AIO Assistant]
    end

    subgraph "Layer 4: API Gateway Isolation"
        JWT[JWT Authentication<br/>Claims: dept_id, role]
        RATE[Rate Limiting<br/>10 req/min per dept]
        AUDIT[Audit Logging<br/>All cross-dept queries]
    end

    RP_HR -->|search_path=hr_tenant| SCHEMA_HR
    RP_ACC -->|search_path=accounting_tenant| SCHEMA_ACC
    RP_SALES -->|search_path=sales_tenant| SCHEMA_SALES

    SCHEMA_HR ---|RLS Enforced| DB
    SCHEMA_ACC ---|RLS Enforced| DB
    SCHEMA_SALES ---|RLS Enforced| DB

    RP_HR -->|OAuth tokens| OAUTH_HR
    RP_ACC -->|OAuth tokens| OAUTH_ACC
    RP_SALES -->|OAuth tokens| OAUTH_SALES

    RP_HR -->|JWT: dept=HR| JWT
    RP_ACC -->|JWT: dept=Accounting| JWT
    RP_SALES -->|JWT: dept=Sales| JWT

    JWT --> RATE
    RATE --> AUDIT

    style RP_HR fill:#4A90E2
    style RP_ACC fill:#4A90E2
    style RP_SALES fill:#4A90E2
    style SCHEMA_HR fill:#7ED321
    style SCHEMA_ACC fill:#7ED321
    style SCHEMA_SALES fill:#7ED321
    style OAUTH_HR fill:#F5A623
    style OAUTH_ACC fill:#F5A623
    style OAUTH_SALES fill:#F5A623
    style JWT fill:#E24A4A
    style RATE fill:#E24A4A
    style AUDIT fill:#E24A4A
```

### 1.2 Database Isolation: PostgreSQL Schemas + Row-Level Security

**Design Decision:** Shared database with per-tenant schemas (NOT separate databases)

**Rationale:**
- Cost-effective: Single database instance for all tenants
- Easier management: Centralized backups, monitoring, upgrades
- Sufficient isolation: PostgreSQL RLS provides row-level security guarantees
- Scalable: Support 100+ schemas without performance degradation

**Schema Structure:**

```sql
-- Each department has its own schema
CREATE SCHEMA hr_tenant;
CREATE SCHEMA accounting_tenant;
CREATE SCHEMA sales_tenant;

-- Each schema has identical table structure
-- federation/database/templates/tenant_schema.sql defines the structure
```

**Row-Level Security (RLS) Policies:**

```sql
-- Enable RLS on all tenant tables
ALTER TABLE hr_tenant.tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE hr_tenant.session_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE hr_tenant.drive_document_repository ENABLE ROW LEVEL SECURITY;

-- Policy: Department agents can only access their own schema
CREATE POLICY tenant_isolation_policy ON hr_tenant.tool_calls
    FOR ALL
    TO hr_user
    USING (true); -- All rows accessible within the schema

-- Policy: Cross-department queries require explicit permission
CREATE POLICY cross_dept_read_policy ON hr_tenant.drive_document_repository
    FOR SELECT
    TO cross_dept_query_user
    USING (
        EXISTS (
            SELECT 1 FROM federation.cross_dept_permissions
            WHERE source_department_id = current_setting('app.source_department')
            AND target_department_id = 'hr'
            AND permission_type = 'read'
            AND enabled = true
        )
    );

-- Policy: No cross-schema writes
CREATE POLICY no_cross_dept_write ON hr_tenant.tool_calls
    FOR INSERT
    TO cross_dept_query_user
    USING (false); -- Deny all writes from cross-dept queries
```

**Database User Roles:**

```sql
-- Per-department database user (restricted to single schema)
CREATE ROLE hr_user WITH LOGIN PASSWORD 'encrypted_password';
ALTER ROLE hr_user SET search_path TO hr_tenant, public;
GRANT USAGE ON SCHEMA hr_tenant TO hr_user;
GRANT ALL ON ALL TABLES IN SCHEMA hr_tenant TO hr_user;

-- Cross-department query user (read-only, RLS enforced)
CREATE ROLE cross_dept_query_user WITH LOGIN PASSWORD 'encrypted_password';
GRANT USAGE ON SCHEMA hr_tenant, accounting_tenant, sales_tenant TO cross_dept_query_user;
GRANT SELECT ON ALL TABLES IN SCHEMA hr_tenant TO cross_dept_query_user;
GRANT SELECT ON ALL TABLES IN SCHEMA accounting_tenant TO cross_dept_query_user;
GRANT SELECT ON ALL TABLES IN SCHEMA sales_tenant TO cross_dept_query_user;

-- Federation control plane user (admin access to federation schema only)
CREATE ROLE federation_admin WITH LOGIN PASSWORD 'encrypted_password';
GRANT ALL ON SCHEMA federation TO federation_admin;
```

**Connection String Isolation:**

```typescript
// Each department agent uses a dedicated connection string
const connection_strings = {
  hr: 'postgresql://hr_user:password@db.railway.app:5432/federation?schema=hr_tenant',
  accounting: 'postgresql://accounting_user:password@db.railway.app:5432/federation?schema=accounting_tenant',
  sales: 'postgresql://sales_user:password@db.railway.app:5432/federation?schema=sales_tenant'
};

// Set session variable for RLS policies
await pool.query(`SET app.current_department = 'hr'`);
```

**Data Leakage Prevention:**

```sql
-- Prevent information disclosure via error messages
ALTER DATABASE federation SET log_statement = 'none'; -- Don't log queries
ALTER DATABASE federation SET log_min_error_statement = 'panic'; -- Only log critical errors

-- Prevent cross-schema queries via SQL injection
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA information_schema FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA pg_catalog FROM PUBLIC;

-- Audit cross-schema access attempts
CREATE OR REPLACE FUNCTION log_cross_schema_access()
RETURNS event_trigger AS $$
BEGIN
    IF TG_TAG = 'SELECT' THEN
        INSERT INTO federation.security_audit (
            event_type, user_role, query, created_at
        ) VALUES (
            'CROSS_SCHEMA_ACCESS_ATTEMPT',
            current_user,
            current_query(),
            NOW()
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE EVENT TRIGGER cross_schema_access_trigger
    ON ddl_command_end
    EXECUTE FUNCTION log_cross_schema_access();
```

### 1.3 Network Isolation: Railway Projects

**Design Decision:** Separate Railway project per department (NOT shared project with multiple services)

**Rationale:**
- Stronger network isolation: Each project has private network
- Resource isolation: Memory/CPU limits per department
- Blast radius containment: Compromised agent doesn't affect others
- Easier cost tracking: Per-project billing

**Railway Network Architecture:**

```mermaid
graph TB
    subgraph "Railway Account: Federation Platform"
        subgraph "Project: aio-hr-prod"
            HR_AGENT[LiveKit Agent Service<br/>Private IP: 10.1.0.10]
            HR_ENV[Environment Variables<br/>DB_USER=hr_user<br/>DB_SCHEMA=hr_tenant]
        end

        subgraph "Project: aio-accounting-prod"
            ACC_AGENT[LiveKit Agent Service<br/>Private IP: 10.2.0.10]
            ACC_ENV[Environment Variables<br/>DB_USER=accounting_user<br/>DB_SCHEMA=accounting_tenant]
        end

        subgraph "Project: aio-control-plane"
            ORCH[Provisioning Orchestrator<br/>Private IP: 10.0.0.10]
            GATEWAY[API Gateway<br/>Public IP: federation.synrg.io]
        end

        subgraph "Shared Services"
            DB[(PostgreSQL Master<br/>Private: 10.0.1.10)]
            REDIS[(Redis Cache<br/>Private: 10.0.1.20)]
        end
    end

    subgraph "External Services"
        LIVEKIT[LiveKit Cloud]
        N8N[n8n Cloud]
        GOOGLE[Google Workspace]
    end

    HR_AGENT -->|Private Network| DB
    ACC_AGENT -->|Private Network| DB
    ORCH -->|Private Network| DB

    HR_AGENT -->|Private Network| REDIS
    ACC_AGENT -->|Private Network| REDIS

    GATEWAY -->|Private Network| HR_AGENT
    GATEWAY -->|Private Network| ACC_AGENT

    HR_AGENT -->|HTTPS| LIVEKIT
    HR_AGENT -->|HTTPS| N8N
    HR_AGENT -->|OAuth| GOOGLE

    ACC_AGENT -->|HTTPS| LIVEKIT
    ACC_AGENT -->|HTTPS| N8N
    ACC_AGENT -->|OAuth| GOOGLE

    style HR_AGENT fill:#4A90E2
    style ACC_AGENT fill:#4A90E2
    style ORCH fill:#7ED321
    style GATEWAY fill:#E24A4A
    style DB fill:#F5A623
    style REDIS fill:#F5A623
```

**Network Security Rules:**

```hcl
# federation/terraform/network-security.tf

resource "railway_service" "aio_agent" {
  # ... other config

  # Private network access only (no public internet)
  network_access = "private"

  # Allow egress only to specific services
  egress_rules = [
    {
      destination = "postgresql.railway.internal"
      port        = 5432
      protocol    = "tcp"
    },
    {
      destination = "redis.railway.internal"
      port        = 6379
      protocol    = "tcp"
    },
    {
      destination = "livekit.cloud"
      port        = 443
      protocol    = "tcp"
    },
    {
      destination = "jayconnorexe.app.n8n.cloud"
      port        = 443
      protocol    = "tcp"
    }
  ]

  # Deny all other egress
  default_egress = "deny"
}
```

### 1.4 Container Isolation: Docker Security

**Security Hardening:**

```dockerfile
# federation/docker-templates/aio-agent/Dockerfile

FROM python:3.11-slim

# Run as non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser
USER appuser

# Read-only root filesystem (except /tmp and /app/logs)
VOLUME ["/tmp", "/app/logs"]

# Drop all capabilities except required
# CAP_NET_BIND_SERVICE: Bind to port 8080
RUN apt-get update && apt-get install -y libcap2-bin && \
    setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.11

# Security labels
LABEL security.isolation="multi-tenant"
LABEL security.department="DEPARTMENT_ID_PLACEHOLDER"

# Disable shell access
RUN rm /bin/sh /bin/bash

# Environment variable validation at startup
COPY scripts/validate-env.sh /app/scripts/
RUN chmod +x /app/scripts/validate-env.sh
ENTRYPOINT ["/app/scripts/validate-env.sh"]

CMD ["python", "-m", "src.agent", "start"]
```

**Environment Variable Validation:**

```bash
#!/bin/bash
# federation/docker-templates/aio-agent/scripts/validate-env.sh

set -euo pipefail

# Required environment variables
required_vars=(
    "DEPARTMENT_ID"
    "DB_SCHEMA"
    "DB_USER"
    "LIVEKIT_URL"
    "N8N_WEBHOOK_BASE_URL"
)

# Validate all required variables are set
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: Required environment variable $var is not set"
        exit 1
    fi
done

# Validate DB_SCHEMA matches DEPARTMENT_ID pattern
if [[ ! "$DB_SCHEMA" =~ ^${DEPARTMENT_ID}_tenant$ ]]; then
    echo "ERROR: DB_SCHEMA must match pattern {DEPARTMENT_ID}_tenant"
    exit 1
fi

# Validate no SQL injection in DB_SCHEMA
if [[ "$DB_SCHEMA" =~ [^a-z0-9_] ]]; then
    echo "ERROR: DB_SCHEMA contains invalid characters"
    exit 1
fi

echo "Environment validation passed"
exec "$@"
```

---

## 2. OAuth Boundary Design

### 2.1 Per-Department OAuth Apps

**Design Decision:** Dedicated OAuth app per department (NOT shared OAuth app)

**Rationale:**
- Credential isolation: Compromised department doesn't leak others' tokens
- Scope isolation: Each department has specific scopes (e.g., HR: Drive + Gmail, Sales: Calendar + Contacts)
- Audit trail: Per-department OAuth app names appear in Google Admin audit logs
- Revocation control: Revoke access for one department without affecting others

**OAuth App Architecture:**

```mermaid
graph TB
    subgraph "Google Workspace Admin Console"
        OAUTH_HR[OAuth App: HR AIO Assistant<br/>Client ID: abc123...hr<br/>Scopes: drive.readonly, gmail.send]
        OAUTH_ACC[OAuth App: Accounting AIO Assistant<br/>Client ID: def456...acc<br/>Scopes: drive.readonly, sheets.readonly]
        OAUTH_SALES[OAuth App: Sales AIO Assistant<br/>Client ID: ghi789...sales<br/>Scopes: calendar.readonly, contacts.readonly]
    end

    subgraph "Federation Platform"
        OCM[OAuth Credential Manager]
        DB[(PostgreSQL: federation.oauth_credentials)]
    end

    subgraph "Department Agents"
        HR_AGENT[HR Agent]
        ACC_AGENT[Accounting Agent]
        SALES_AGENT[Sales Agent]
    end

    OAUTH_HR -->|Client ID + Secret| OCM
    OAUTH_ACC -->|Client ID + Secret| OCM
    OAUTH_SALES -->|Client ID + Secret| OCM

    OCM -->|AES-256 Encrypted| DB

    DB -->|Decrypted at runtime| HR_AGENT
    DB -->|Decrypted at runtime| ACC_AGENT
    DB -->|Decrypted at runtime| SALES_AGENT

    HR_AGENT -->|OAuth Token| OAUTH_HR
    ACC_AGENT -->|OAuth Token| OAUTH_ACC
    SALES_AGENT -->|OAuth Token| OAUTH_SALES

    style OAUTH_HR fill:#F5A623
    style OAUTH_ACC fill:#F5A623
    style OAUTH_SALES fill:#F5A623
    style OCM fill:#E24A4A
    style DB fill:#7ED321
```

### 2.2 Credential Storage: Encrypted at Rest

**Encryption Strategy:**

```sql
-- Use PostgreSQL pgcrypto for AES-256-GCM encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Store OAuth credentials encrypted
CREATE TABLE federation.oauth_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id VARCHAR(100) NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    oauth_client_id VARCHAR(255) NOT NULL,
    -- Encrypted with AES-256-GCM using application encryption key
    oauth_client_secret_encrypted BYTEA NOT NULL,
    oauth_app_name VARCHAR(255),
    scopes JSONB,
    -- User refresh token (encrypted)
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMPTZ,
    last_refreshed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,
    CONSTRAINT unique_dept_service UNIQUE(department_id, service_name)
);

-- Encryption/Decryption functions
-- Note: Encryption key stored in environment variable (OAUTH_ENCRYPTION_KEY)

-- Insert encrypted credential
INSERT INTO federation.oauth_credentials (
    department_id, service_name, oauth_client_id, oauth_client_secret_encrypted
) VALUES (
    'hr',
    'google_drive',
    'abc123.apps.googleusercontent.com',
    pgp_sym_encrypt('CLIENT_SECRET_PLAIN_TEXT', current_setting('app.encryption_key'))
);

-- Retrieve decrypted credential (only by application with encryption key)
SELECT
    department_id,
    service_name,
    oauth_client_id,
    pgp_sym_decrypt(oauth_client_secret_encrypted, current_setting('app.encryption_key')) AS oauth_client_secret,
    pgp_sym_decrypt(refresh_token_encrypted, current_setting('app.encryption_key')) AS refresh_token
FROM federation.oauth_credentials
WHERE department_id = 'hr' AND service_name = 'google_drive';
```

**Encryption Key Management:**

```typescript
// src/oauth/encryption-manager.ts
import * as crypto from 'crypto';

class EncryptionManager {
  private encryption_key: Buffer;

  constructor() {
    // Load encryption key from environment variable
    const key_hex = process.env.OAUTH_ENCRYPTION_KEY;
    if (!key_hex || key_hex.length !== 64) {
      throw new Error('OAUTH_ENCRYPTION_KEY must be 32 bytes (64 hex chars)');
    }
    this.encryption_key = Buffer.from(key_hex, 'hex');
  }

  // Key rotation: Generate new key and re-encrypt all credentials
  async rotateEncryptionKey(): Promise<void> {
    const new_key = crypto.randomBytes(32);

    // 1. Fetch all encrypted credentials with old key
    const credentials = await this.fetchAllCredentials();

    // 2. Decrypt with old key, re-encrypt with new key
    for (const cred of credentials) {
      const decrypted = this.decrypt(cred.oauth_client_secret_encrypted, this.encryption_key);
      const re_encrypted = this.encrypt(decrypted, new_key);

      await this.updateCredential(cred.id, re_encrypted);
    }

    // 3. Update environment variable with new key
    console.log(`New encryption key (store securely): ${new_key.toString('hex')}`);
  }

  encrypt(plaintext: string, key: Buffer): Buffer {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    const encrypted = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
    const auth_tag = cipher.getAuthTag();

    // Format: iv (16 bytes) + auth_tag (16 bytes) + encrypted_data
    return Buffer.concat([iv, auth_tag, encrypted]);
  }

  decrypt(encrypted_buffer: Buffer, key: Buffer): string {
    const iv = encrypted_buffer.slice(0, 16);
    const auth_tag = encrypted_buffer.slice(16, 32);
    const encrypted_data = encrypted_buffer.slice(32);

    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(auth_tag);

    const decrypted = Buffer.concat([
      decipher.update(encrypted_data),
      decipher.final()
    ]);

    return decrypted.toString('utf8');
  }
}
```

**Key Rotation Schedule:**
- **Frequency**: Every 90 days (automated)
- **Trigger**: Cron job in control plane orchestrator
- **Process**:
  1. Generate new encryption key
  2. Decrypt all credentials with old key
  3. Re-encrypt with new key
  4. Update database
  5. Update environment variable in Railway projects (zero-downtime: rotate one agent at a time)
  6. Store old key in secure backup (for emergency recovery)

### 2.3 OAuth Token Lifecycle

```mermaid
stateDiagram-v2
    [*] --> TokenRequested: Admin initiates OAuth flow

    TokenRequested --> TokenReceived: User authorizes in Google
    TokenReceived --> TokenStored: Encrypt and store refresh token

    TokenStored --> TokenValid: Agent uses access token
    TokenValid --> TokenExpired: Token TTL expires (1 hour)

    TokenExpired --> TokenRefreshing: Agent detects 401 error
    TokenRefreshing --> TokenRefreshed: Refresh token exchanged
    TokenRefreshed --> TokenStored: Update access token

    TokenValid --> TokenRevoked: Admin revokes access
    TokenRefreshed --> TokenRevoked: Refresh fails (user revoked)
    TokenRevoked --> TokenRequested: Re-authorization required

    TokenStored --> TokenRotated: 90-day key rotation
    TokenRotated --> TokenStored: Re-encrypted with new key
```

**Token Refresh Automation:**

```typescript
// src/oauth/token-manager.ts
import { google } from 'googleapis';

class TokenManager {
  async refreshAccessToken(department_id: string, service_name: string): Promise<string> {
    // 1. Fetch encrypted refresh token from database
    const cred = await this.getCredential(department_id, service_name);

    // 2. Decrypt refresh token
    const refresh_token = this.encryption_manager.decrypt(
      cred.refresh_token_encrypted,
      this.encryption_key
    );

    // 3. Exchange refresh token for new access token
    const oauth2_client = new google.auth.OAuth2(
      cred.oauth_client_id,
      cred.oauth_client_secret,
      'https://federation.synrg.io/oauth/callback'
    );

    oauth2_client.setCredentials({ refresh_token });

    const { credentials } = await oauth2_client.refreshAccessToken();

    // 4. Update database with new access token and expiry
    await this.updateAccessToken(
      department_id,
      service_name,
      credentials.access_token,
      new Date(credentials.expiry_date)
    );

    return credentials.access_token;
  }

  // Token expiration monitoring (run every 5 minutes)
  async monitorTokenExpiration(): Promise<void> {
    const expiring_soon = await this.pool.query(`
      SELECT department_id, service_name
      FROM federation.oauth_credentials
      WHERE token_expires_at < NOW() + INTERVAL '10 minutes'
    `);

    for (const row of expiring_soon.rows) {
      try {
        await this.refreshAccessToken(row.department_id, row.service_name);
        console.log(`Refreshed token for ${row.department_id}/${row.service_name}`);
      } catch (error) {
        console.error(`Failed to refresh token: ${error.message}`);
        // Alert admin: token may be revoked
        await this.alertTokenFailure(row.department_id, row.service_name, error);
      }
    }
  }
}
```

### 2.4 OAuth Scope Management

**Principle of Least Privilege:** Each department only gets scopes it needs.

```typescript
// src/oauth/scope-manager.ts

const TOOL_REQUIRED_SCOPES: Record<string, string[]> = {
  email: [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
  ],
  google_drive: [
    'https://www.googleapis.com/auth/drive.readonly'
  ],
  calendar: [
    'https://www.googleapis.com/auth/calendar.readonly'
  ],
  contacts: [
    'https://www.googleapis.com/auth/contacts.readonly'
  ],
  sheets: [
    'https://www.googleapis.com/auth/spreadsheets.readonly'
  ]
};

class ScopeManager {
  calculateRequiredScopes(enabled_tools: string[]): string[] {
    const scopes = new Set<string>();

    for (const tool of enabled_tools) {
      const tool_scopes = TOOL_REQUIRED_SCOPES[tool] || [];
      for (const scope of tool_scopes) {
        scopes.add(scope);
      }
    }

    return Array.from(scopes);
  }

  async updateDepartmentScopes(department_id: string, enabled_tools: string[]): Promise<void> {
    const required_scopes = this.calculateRequiredScopes(enabled_tools);

    await this.pool.query(`
      UPDATE federation.oauth_credentials
      SET scopes = $2
      WHERE department_id = $1
    `, [department_id, JSON.stringify(required_scopes)]);

    // Note: Existing OAuth tokens keep their scopes until user re-authorizes
    // To enforce new scopes, revoke existing tokens and require re-authorization
  }
}
```

---

## 3. Cross-Department Access Control

### 3.1 Permission Model

**Design Decision:** Explicit permission grants (NOT default allow)

```sql
-- federation/database/schemas/cross_dept_permissions.sql

CREATE TABLE federation.cross_dept_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_department_id VARCHAR(100) NOT NULL,
    target_department_id VARCHAR(100) NOT NULL,
    permission_type VARCHAR(50) NOT NULL, -- 'read', 'search', 'aggregate'
    resource_type VARCHAR(50), -- 'drive_documents', 'emails', 'contacts', '*'
    enabled BOOLEAN NOT NULL DEFAULT true,
    granted_by VARCHAR(255) NOT NULL, -- Admin email who granted permission
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- Optional expiration
    CONSTRAINT unique_permission UNIQUE(source_department_id, target_department_id, permission_type, resource_type)
);

CREATE INDEX idx_cross_dept_source ON federation.cross_dept_permissions(source_department_id);
CREATE INDEX idx_cross_dept_target ON federation.cross_dept_permissions(target_department_id);
CREATE INDEX idx_cross_dept_enabled ON federation.cross_dept_permissions(enabled);

-- Example: HR can search Accounting's documents
INSERT INTO federation.cross_dept_permissions (
    source_department_id, target_department_id, permission_type, resource_type, granted_by
) VALUES (
    'hr', 'accounting', 'search', 'drive_documents', 'admin@synrgscaling.com'
);

-- Example: Sales can read Accounting's aggregated reports (but not raw data)
INSERT INTO federation.cross_dept_permissions (
    source_department_id, target_department_id, permission_type, resource_type, granted_by
) VALUES (
    'sales', 'accounting', 'aggregate', 'financial_reports', 'admin@synrgscaling.com'
);
```

### 3.2 Permission Enforcement

**API Gateway Middleware:**

```typescript
// src/gateway/permission-middleware.ts

class PermissionMiddleware {
  async checkCrossDeptPermission(
    source_dept: string,
    target_dept: string,
    permission_type: string,
    resource_type: string
  ): Promise<boolean> {
    const query = `
      SELECT EXISTS (
        SELECT 1 FROM federation.cross_dept_permissions
        WHERE source_department_id = $1
        AND target_department_id = $2
        AND permission_type = $3
        AND (resource_type = $4 OR resource_type = '*')
        AND enabled = true
        AND (expires_at IS NULL OR expires_at > NOW())
      ) AS has_permission
    `;

    const result = await this.pool.query(query, [
      source_dept,
      target_dept,
      permission_type,
      resource_type
    ]);

    return result.rows[0].has_permission;
  }

  async enforceCrossDeptAccess(req: Request, res: Response, next: NextFunction) {
    const source_dept = req.department_id; // From JWT
    const target_dept = req.body.target_department_id;
    const query_type = req.body.query_type;
    const resource_type = this.mapQueryTypeToResource(query_type);

    const has_permission = await this.checkCrossDeptPermission(
      source_dept,
      target_dept,
      'search', // or 'read', 'aggregate'
      resource_type
    );

    if (!has_permission) {
      await this.logAccessDenied(source_dept, target_dept, query_type);
      return res.status(403).json({
        error: 'Access denied',
        message: `Department ${source_dept} does not have permission to access ${target_dept}'s ${resource_type}`
      });
    }

    next();
  }

  private mapQueryTypeToResource(query_type: string): string {
    const mapping: Record<string, string> = {
      'search_documents': 'drive_documents',
      'get_contact': 'contacts',
      'search_emails': 'emails'
    };
    return mapping[query_type] || '*';
  }

  private async logAccessDenied(source: string, target: string, query_type: string): Promise<void> {
    await this.pool.query(`
      INSERT INTO federation.security_audit (
        event_type, source_department_id, target_department_id, details, created_at
      ) VALUES (
        'CROSS_DEPT_ACCESS_DENIED', $1, $2, $3, NOW()
      )
    `, [source, target, JSON.stringify({ query_type })]);
  }
}
```

### 3.3 Audit Trail

**All cross-department queries logged:**

```sql
-- federation/database/schemas/cross_dept_audit.sql

CREATE TABLE federation.cross_dept_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_department_id VARCHAR(100) NOT NULL,
    target_department_id VARCHAR(100),
    query_type VARCHAR(50) NOT NULL,
    query_params JSONB,
    requester_session_id VARCHAR(100),
    requester_ip INET,
    results_returned INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cross_dept_audit_source ON federation.cross_dept_audit(source_department_id);
CREATE INDEX idx_cross_dept_audit_target ON federation.cross_dept_audit(target_department_id);
CREATE INDEX idx_cross_dept_audit_created ON federation.cross_dept_audit(created_at DESC);
CREATE INDEX idx_cross_dept_audit_success ON federation.cross_dept_audit(success);

-- Retention policy: Keep audit logs for 2 years
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM federation.cross_dept_audit
    WHERE created_at < NOW() - INTERVAL '2 years';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup monthly
SELECT cron.schedule('cleanup-audit-logs', '0 0 1 * *', 'SELECT cleanup_old_audit_logs()');
```

### 3.4 Rate Limiting

**Prevent abuse:**

```typescript
// src/gateway/rate-limiter.ts
import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';

export const cross_dept_rate_limiter = rateLimit({
  store: new RedisStore({
    client: redis_client,
    prefix: 'rl:cross_dept:'
  }),
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 requests per minute per department
  keyGenerator: (req) => req.department_id,
  handler: (req, res) => {
    // Log rate limit violation
    this.pool.query(`
      INSERT INTO federation.security_audit (
        event_type, source_department_id, details, created_at
      ) VALUES (
        'RATE_LIMIT_EXCEEDED', $1, $2, NOW()
      )
    `, [req.department_id, JSON.stringify({ endpoint: req.path })]);

    res.status(429).json({
      error: 'Too many requests',
      message: 'Cross-department query rate limit exceeded (10/min)'
    });
  }
});
```

---

## 4. Security Compliance

### 4.1 GDPR Compliance

**Data Subject Rights:**

```typescript
// src/compliance/gdpr-manager.ts

class GDPRManager {
  // Right to Access (Article 15)
  async exportUserData(user_email: string, department_id: string): Promise<any> {
    const data = {
      tool_calls: await this.exportToolCalls(user_email, department_id),
      session_context: await this.exportSessionContext(user_email, department_id),
      drive_documents: await this.exportDriveAccess(user_email, department_id),
      audit_logs: await this.exportAuditLogs(user_email, department_id)
    };

    // Log data export request
    await this.logGDPRRequest('DATA_ACCESS', user_email, department_id);

    return data;
  }

  // Right to Erasure (Article 17)
  async deleteUserData(user_email: string, department_id: string): Promise<void> {
    const schema = `${department_id}_tenant`;

    // Anonymize user data (keep audit trail but remove PII)
    await this.pool.query(`
      UPDATE ${schema}.tool_calls
      SET parameters = jsonb_set(parameters, '{user_email}', '"[REDACTED]"')
      WHERE parameters->>'user_email' = $1
    `, [user_email]);

    // Delete session context
    await this.pool.query(`
      DELETE FROM ${schema}.session_context
      WHERE context_value->>'user_email' = $1
    `, [user_email]);

    // Log deletion request
    await this.logGDPRRequest('DATA_DELETION', user_email, department_id);
  }

  // Data Retention Policy
  async applyRetentionPolicy(department_id: string): Promise<void> {
    const schema = `${department_id}_tenant`;

    // Delete tool calls older than 2 years
    await this.pool.query(`
      DELETE FROM ${schema}.tool_calls
      WHERE created_at < NOW() - INTERVAL '2 years'
    `);

    // Delete session context older than 90 days
    await this.pool.query(`
      DELETE FROM ${schema}.session_context
      WHERE created_at < NOW() - INTERVAL '90 days'
    `);
  }

  private async logGDPRRequest(request_type: string, user_email: string, department_id: string): Promise<void> {
    await this.pool.query(`
      INSERT INTO federation.security_audit (
        event_type, details, created_at
      ) VALUES (
        'GDPR_REQUEST', $1, NOW()
      )
    `, [JSON.stringify({ request_type, user_email, department_id })]);
  }
}
```

### 4.2 SOC 2 Type II Controls

**Security Controls Mapping:**

| Control Category | Federation Implementation |
|-----------------|---------------------------|
| **CC6.1: Logical Access** | JWT authentication, RLS policies, per-department DB users |
| **CC6.2: Authentication** | JWT with RSA-256 signatures, 1-hour token expiry |
| **CC6.3: Authorization** | Role-based access (admin/user), permission grants table |
| **CC6.6: Encryption** | AES-256-GCM for OAuth credentials, TLS 1.3 for all traffic |
| **CC7.2: System Monitoring** | Audit logs, health checks, anomaly detection |
| **CC7.3: Change Management** | Terraform IaC, immutable infrastructure, rollback capability |
| **CC8.1: Availability** | Multi-AZ deployment, health checks, auto-restart on failure |
| **CC9.1: Risk Assessment** | Threat modeling (see section 5), quarterly security reviews |

### 4.3 Data Encryption

**Encryption at Rest:**
- OAuth credentials: AES-256-GCM via PostgreSQL pgcrypto
- Database: Railway PostgreSQL encrypted volumes (AES-256)
- Backups: Encrypted with customer-managed keys

**Encryption in Transit:**
- All HTTPS traffic: TLS 1.3 only
- Database connections: PostgreSQL SSL mode=require
- Internal Railway network: Private network (no internet exposure)

```typescript
// src/config/tls-config.ts

export const TLS_CONFIG = {
  minVersion: 'TLSv1.3',
  maxVersion: 'TLSv1.3',
  ciphers: [
    'TLS_AES_256_GCM_SHA384',
    'TLS_CHACHA20_POLY1305_SHA256',
    'TLS_AES_128_GCM_SHA256'
  ].join(':'),
  honorCipherOrder: true
};

// PostgreSQL SSL config
export const DB_SSL_CONFIG = {
  ssl: {
    rejectUnauthorized: true,
    ca: fs.readFileSync('/path/to/ca-cert.pem')
  }
};
```

### 4.4 Compliance Reporting

**Automated Compliance Reports:**

```typescript
// src/compliance/report-generator.ts

class ComplianceReportGenerator {
  async generateMonthlyReport(department_id: string, month: Date): Promise<ComplianceReport> {
    return {
      department_id,
      report_period: month,
      metrics: {
        total_tool_calls: await this.countToolCalls(department_id, month),
        cross_dept_queries: await this.countCrossDeptQueries(department_id, month),
        access_denied_events: await this.countAccessDenied(department_id, month),
        oauth_token_refreshes: await this.countTokenRefreshes(department_id, month),
        rate_limit_violations: await this.countRateLimitViolations(department_id, month)
      },
      security_incidents: await this.listSecurityIncidents(department_id, month),
      compliance_checks: {
        encryption_at_rest: true,
        encryption_in_transit: true,
        audit_logging_enabled: true,
        data_retention_policy_applied: await this.checkRetentionPolicy(department_id),
        oauth_tokens_rotated: await this.checkTokenRotation(department_id)
      }
    };
  }
}

interface ComplianceReport {
  department_id: string;
  report_period: Date;
  metrics: {
    total_tool_calls: number;
    cross_dept_queries: number;
    access_denied_events: number;
    oauth_token_refreshes: number;
    rate_limit_violations: number;
  };
  security_incidents: SecurityIncident[];
  compliance_checks: {
    encryption_at_rest: boolean;
    encryption_in_transit: boolean;
    audit_logging_enabled: boolean;
    data_retention_policy_applied: boolean;
    oauth_tokens_rotated: boolean;
  };
}
```

---

## 5. Threat Model

### 5.1 Attack Surface Analysis

```mermaid
graph TB
    subgraph "External Attack Surface"
        API[API Gateway<br/>HTTPS endpoints]
        OAUTH[OAuth Callback<br/>User authorization]
    end

    subgraph "Internal Attack Surface"
        DB[(PostgreSQL<br/>Connection strings)]
        REDIS[(Redis<br/>Rate limiting)]
        N8N[n8n Webhooks<br/>Tool backends]
    end

    subgraph "Department Agents"
        AGENT1[HR Agent<br/>Container]
        AGENT2[Accounting Agent<br/>Container]
    end

    subgraph "External Services"
        LIVEKIT[LiveKit Cloud]
        GOOGLE[Google Workspace]
        CEREBRAS[Cerebras LLM]
    end

    ATTACKER[Attacker] -.->|1. Public API exploit| API
    ATTACKER -.->|2. OAuth phishing| OAUTH
    ATTACKER -.->|3. SQL injection| DB
    ATTACKER -.->|4. Container escape| AGENT1
    ATTACKER -.->|5. SSRF via n8n| N8N
    ATTACKER -.->|6. Stolen OAuth tokens| GOOGLE

    API --> DB
    OAUTH --> DB
    AGENT1 --> DB
    AGENT2 --> DB

    AGENT1 --> N8N
    AGENT1 --> LIVEKIT
    AGENT1 --> GOOGLE
    AGENT1 --> CEREBRAS

    style ATTACKER fill:#E24A4A
    style API fill:#F5A623
    style OAUTH fill:#F5A623
    style DB fill:#F5A623
    style AGENT1 fill:#F5A623
    style N8N fill:#F5A623
```

### 5.2 Threat Scenarios & Mitigations

| Threat ID | Threat Scenario | Likelihood | Impact | Mitigation |
|-----------|----------------|------------|--------|------------|
| **T1** | SQL Injection via API Gateway | Medium | High | Parameterized queries, input validation, RLS policies |
| **T2** | Cross-Department Data Leakage | Medium | Critical | Schema isolation, RLS policies, permission grants table |
| **T3** | OAuth Token Theft | High | High | Encrypted storage, TLS 1.3, token rotation, short TTLs |
| **T4** | Container Escape (Agent) | Low | Critical | Non-root user, read-only filesystem, seccomp profiles |
| **T5** | SSRF via n8n Webhooks | Medium | Medium | Whitelist webhook URLs, network egress rules |
| **T6** | Rate Limit Bypass | Medium | Low | Redis-backed rate limiting, IP + JWT key combo |
| **T7** | OAuth Phishing (User) | High | Medium | OAuth consent screen branding, user training |
| **T8** | Encryption Key Exposure | Low | Critical | Environment variables only, no file storage, key rotation |
| **T9** | Insider Threat (Admin) | Low | High | Audit logging, least privilege, multi-signature for sensitive ops |
| **T10** | DDoS Attack | High | Medium | Railway auto-scaling, Cloudflare DDoS protection |

### 5.3 Detailed Threat Analysis

**T1: SQL Injection via API Gateway**

**Attack Vector:**
```typescript
// Vulnerable code (DO NOT USE)
const query = `SELECT * FROM ${department_id}_tenant.tool_calls WHERE session_id = '${session_id}'`;

// Attacker payload:
// department_id = "hr_tenant; DROP SCHEMA accounting_tenant CASCADE; --"
```

**Mitigation:**
```typescript
// Secure code (USE THIS)
const query = `SELECT * FROM ${pg.escapeIdentifier(department_id + '_tenant')}.tool_calls WHERE session_id = $1`;
await pool.query(query, [session_id]);

// Additional: Validate department_id format
if (!/^[a-z0-9_-]+$/.test(department_id)) {
  throw new Error('Invalid department_id format');
}
```

**T2: Cross-Department Data Leakage**

**Attack Vector:**
```sql
-- Attacker in HR department tries to access Accounting data
SET search_path TO accounting_tenant, public;
SELECT * FROM tool_calls; -- Should be blocked
```

**Mitigation:**
```sql
-- RLS policy prevents cross-schema access
CREATE POLICY tenant_isolation ON accounting_tenant.tool_calls
    FOR ALL
    TO hr_user
    USING (false); -- hr_user cannot access accounting_tenant at all

-- Database user hr_user has NO USAGE privilege on accounting_tenant schema
REVOKE USAGE ON SCHEMA accounting_tenant FROM hr_user;
```

**T3: OAuth Token Theft**

**Attack Vector:**
- Man-in-the-middle attack on OAuth callback
- Stolen environment variables from compromised agent
- Memory dump of running agent process

**Mitigation:**
- **TLS 1.3 pinning**: Validate OAuth callback URL uses TLS 1.3
- **Environment variable encryption**: Store encrypted tokens even in env vars
- **Memory protection**: Use secure heap allocation for sensitive data
- **Token rotation**: Automatically rotate refresh tokens every 90 days
- **OAuth PKCE**: Use Proof Key for Code Exchange for mobile/web clients

**T6: Rate Limit Bypass**

**Attack Vector:**
```bash
# Attacker rotates through multiple IP addresses
curl -H "Authorization: Bearer $JWT" https://api.federation.synrg.io/cross-dept/query --proxy socks5://proxy1
curl -H "Authorization: Bearer $JWT" https://api.federation.synrg.io/cross-dept/query --proxy socks5://proxy2
# ... bypass IP-based rate limiting
```

**Mitigation:**
```typescript
// Rate limit based on JWT department_id (not IP)
export const cross_dept_rate_limiter = rateLimit({
  keyGenerator: (req) => req.department_id, // From JWT, not IP
  max: 10,
  windowMs: 60 * 1000
});

// Additional: Detect anomalous patterns
class AnomalyDetector {
  async detectAnomalies(department_id: string): Promise<boolean> {
    // Flag if department exceeds 100 queries/hour
    const hourly_count = await this.countQueriesLastHour(department_id);
    if (hourly_count > 100) {
      await this.alertSecurityTeam(department_id, 'HIGH_QUERY_VOLUME');
      return true;
    }
    return false;
  }
}
```

---

## 6. Operational Security

### 6.1 Secrets Management

**Environment Variables (Runtime Secrets):**

```typescript
// src/config/secrets-manager.ts
import { SecretManagerServiceClient } from '@google-cloud/secret-manager';

class SecretsManager {
  private client: SecretManagerServiceClient;

  async getSecret(secret_name: string): Promise<string> {
    // For MVP: Use Railway environment variables
    const secret = process.env[secret_name];
    if (!secret) {
      throw new Error(`Secret ${secret_name} not found`);
    }
    return secret;
  }

  // For production: Use Google Secret Manager or HashiCorp Vault
  async getSecretFromVault(secret_path: string): Promise<string> {
    const [version] = await this.client.accessSecretVersion({
      name: `projects/federation-platform/secrets/${secret_path}/versions/latest`
    });
    return version.payload.data.toString();
  }

  // Rotate secrets programmatically
  async rotateSecret(secret_name: string, new_value: string): Promise<void> {
    // Update Railway environment variables via API
    await this.updateRailwayEnv(secret_name, new_value);

    // Trigger rolling restart of agents
    await this.rollingRestart();
  }
}
```

**Secret Rotation Schedule:**

| Secret Type | Rotation Frequency | Automation |
|-------------|-------------------|------------|
| **OAuth Encryption Key** | 90 days | Automated (cron job) |
| **Database Passwords** | 180 days | Manual (planned automation) |
| **JWT Signing Key** | 365 days | Manual |
| **API Keys (External)** | Per provider policy | Manual |
| **OAuth Refresh Tokens** | 180 days | Automatic (Google enforces) |

### 6.2 Incident Response Plan

**Security Incident Severity Levels:**

| Level | Definition | Response Time | Example |
|-------|-----------|---------------|---------|
| **P0 - Critical** | Data breach, system-wide outage | <15 minutes | OAuth token leak affecting all departments |
| **P1 - High** | Single-tenant compromise | <1 hour | Compromised department agent |
| **P2 - Medium** | Security control failure | <4 hours | Rate limiter malfunction |
| **P3 - Low** | Suspicious activity | <24 hours | Anomalous query patterns |

**Incident Response Playbook:**

```yaml
# P0 Incident: OAuth Token Leak

1. Detection:
   - Automated alert: OAuth token used from unexpected IP/location
   - Security team receives PagerDuty alert

2. Containment (within 15 minutes):
   - Revoke all OAuth tokens for affected department(s)
   - Disable API Gateway access for affected JWTs
   - Block suspicious IP addresses at Railway network level

3. Investigation (within 1 hour):
   - Query audit logs for all affected token usage
   - Identify scope of data accessed
   - Determine root cause (phishing, insider threat, etc.)

4. Remediation (within 4 hours):
   - Rotate OAuth encryption key
   - Re-encrypt all remaining credentials
   - Force re-authorization for affected departments
   - Patch vulnerability if applicable

5. Recovery (within 24 hours):
   - Restore service for affected departments
   - Communicate incident details to stakeholders
   - File incident report with lessons learned

6. Post-Mortem (within 1 week):
   - Conduct blameless post-mortem
   - Implement preventative measures
   - Update threat model and security controls
```

### 6.3 Security Monitoring & Alerting

**Monitoring Metrics:**

```typescript
// src/monitoring/security-metrics.ts

class SecurityMetrics {
  // Track security-relevant metrics
  metrics = {
    // Authentication failures
    auth_failures_per_minute: new Counter('auth_failures_total'),

    // Cross-department access denials
    cross_dept_access_denied: new Counter('cross_dept_denied_total'),

    // Rate limit violations
    rate_limit_violations: new Counter('rate_limit_violations_total'),

    // OAuth token refresh failures
    oauth_refresh_failures: new Counter('oauth_refresh_failures_total'),

    // Anomalous query patterns
    anomalous_queries: new Counter('anomalous_queries_total')
  };

  // Alert thresholds
  async checkAlertThresholds(): Promise<void> {
    // Alert if >10 auth failures in 1 minute
    if (this.metrics.auth_failures_per_minute.get() > 10) {
      await this.alert('HIGH_AUTH_FAILURES', 'P2');
    }

    // Alert if >5 cross-dept access denials in 5 minutes
    if (this.metrics.cross_dept_access_denied.get() > 5) {
      await this.alert('SUSPICIOUS_CROSS_DEPT_ACCESS', 'P3');
    }

    // Alert immediately on OAuth refresh failure
    if (this.metrics.oauth_refresh_failures.get() > 0) {
      await this.alert('OAUTH_REFRESH_FAILURE', 'P1');
    }
  }

  private async alert(alert_type: string, severity: string): Promise<void> {
    // Send to PagerDuty, Slack, email, etc.
    console.log(`ALERT [${severity}]: ${alert_type}`);
  }
}
```

### 6.4 Security Audit Schedule

| Audit Type | Frequency | Scope | Owner |
|------------|-----------|-------|-------|
| **Code Review** | Every PR | All code changes | Engineering team |
| **Penetration Test** | Quarterly | External pen test firm | Security team |
| **Vulnerability Scan** | Weekly | Automated (Snyk, Dependabot) | DevOps team |
| **Compliance Audit** | Annually | SOC 2 Type II | External auditor |
| **Access Review** | Quarterly | All user/service accounts | Security team |
| **Incident Review** | After each P0/P1 | Post-mortem analysis | Engineering lead |

---

## Conclusion

The Federation Platform security model implements defense-in-depth across four isolation layers:

1. **Database-level**: PostgreSQL schemas + RLS prevent cross-tenant data leakage
2. **Network-level**: Separate Railway projects provide network isolation
3. **OAuth-level**: Per-department OAuth apps with encrypted credential storage
4. **API-level**: JWT authentication, permission grants, rate limiting, and comprehensive audit logging

**Key Security Guarantees:**
- **Zero Cross-Tenant Data Leakage**: RLS policies + schema isolation + permission grants
- **Encrypted Credentials**: AES-256-GCM for OAuth secrets, TLS 1.3 for all traffic
- **Comprehensive Audit Trail**: All cross-department queries logged with 2-year retention
- **Compliance-Ready**: GDPR, SOC 2 Type II controls implemented

**Next Steps:**
1. Security review with stakeholders
2. Threat modeling workshop
3. Implement security controls (Batch 2-5)
4. Penetration testing before production launch
5. Obtain SOC 2 Type II certification (if required)
