#!/bin/bash
# Federation AIO Voice Agent - Dynamic Entrypoint
# Version: 1.0.0
# Purpose: Generate department-specific configuration and start agent

set -e  # Exit on error
set -u  # Exit on undefined variable

# ============================================================================
# Configuration
# ============================================================================
readonly CONFIG_FILE="/app/config/config.yaml"
readonly LOG_PREFIX="[entrypoint]"

# ============================================================================
# Logging functions
# ============================================================================
log_info() {
    echo "${LOG_PREFIX} [INFO] $*" >&2
}

log_error() {
    echo "${LOG_PREFIX} [ERROR] $*" >&2
}

log_fatal() {
    echo "${LOG_PREFIX} [FATAL] $*" >&2
    exit 1
}

# ============================================================================
# Step 1: Validate required environment variables
# ============================================================================
check_env_vars() {
    log_info "Validating required environment variables..."

    local required_vars=(
        "DEPARTMENT_ID"
        "DEPARTMENT_NAME"
        "POSTGRES_URL"
        "N8N_WEBHOOK_BASE"
        "LIVEKIT_URL"
        "LIVEKIT_API_KEY"
        "LIVEKIT_API_SECRET"
        "CEREBRAS_API_KEY"
        "DEEPGRAM_API_KEY"
        "CARTESIA_API_KEY"
    )

    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_fatal "Missing required environment variables: ${missing_vars[*]}"
    fi

    log_info "All required environment variables present"
}

# ============================================================================
# Step 2: Generate department-specific configuration
# ============================================================================
generate_config() {
    log_info "Generating department configuration for: ${DEPARTMENT_NAME}"

    # Extract database schema from POSTGRES_URL or use department_id
    local db_schema="${DB_SCHEMA:-${DEPARTMENT_ID}_tenant}"

    # Parse enabled tools (JSON array string to YAML array)
    local enabled_tools="${ENABLED_TOOLS:-'["email","google_drive","database","vector_store","agent_context"]'}"

    # Create directory if it doesn't exist
    mkdir -p "$(dirname "${CONFIG_FILE}")"

    # Generate YAML configuration
    cat > "${CONFIG_FILE}" <<EOF
# Federation AIO Voice Agent Configuration
# Department: ${DEPARTMENT_NAME}
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

department:
  id: "${DEPARTMENT_ID}"
  name: "${DEPARTMENT_NAME}"
  schema: "${db_schema}"

database:
  url: "${POSTGRES_URL}"
  schema: "${db_schema}"
  pool_size: 10
  max_overflow: 5
  pool_timeout: 30

n8n:
  base_url: "${N8N_WEBHOOK_BASE}"
  webhooks:
    drive_repository: "${N8N_WEBHOOK_BASE}/${DEPARTMENT_ID}/drive-repository"
    execute_gmail: "${N8N_WEBHOOK_BASE}/${DEPARTMENT_ID}/execute-gmail"
    vector_db: "${N8N_WEBHOOK_BASE}/${DEPARTMENT_ID}/voice-query-vector-db"
    agent_context: "${N8N_WEBHOOK_BASE}/${DEPARTMENT_ID}/agent-context"
    file_download_email: "${N8N_WEBHOOK_BASE}/${DEPARTMENT_ID}/file-download-email"

livekit:
  url: "${LIVEKIT_URL}"
  api_key: "${LIVEKIT_API_KEY}"
  api_secret: "${LIVEKIT_API_SECRET}"

llm:
  provider: "cerebras"
  api_key: "${CEREBRAS_API_KEY}"
  base_url: "${CEREBRAS_BASE_URL:-https://api.cerebras.ai/v1}"
  model: "${CEREBRAS_MODEL:-llama-3.3-70b}"
  temperature: ${CEREBRAS_TEMPERATURE:-0.6}
  max_tokens: ${CEREBRAS_MAX_TOKENS:-150}

stt:
  provider: "deepgram"
  api_key: "${DEEPGRAM_API_KEY}"
  model: "${DEEPGRAM_MODEL:-nova-3}"
  language: "${DEEPGRAM_LANGUAGE:-en-US}"

tts:
  provider: "cartesia"
  api_key: "${CARTESIA_API_KEY}"
  model: "${CARTESIA_MODEL:-sonic-3}"
  voice: "${CARTESIA_VOICE:-a167e0f3-df7e-4d52-a9c3-f949145efdab}"

agent:
  name: "${AGENT_NAME:-${DEPARTMENT_NAME} Voice Assistant}"
  log_level: "${LOG_LEVEL:-INFO}"
  enabled_tools: ${enabled_tools}

observability:
  enable_metrics: ${ENABLE_METRICS:-true}
  enable_tracing: ${ENABLE_TRACING:-false}
  otel_endpoint: "${OTEL_ENDPOINT:-}"
EOF

    log_info "Configuration generated: ${CONFIG_FILE}"
}

# ============================================================================
# Step 3: Database connectivity check
# ============================================================================
check_database_connectivity() {
    log_info "Checking database connectivity..."

    # Extract connection parameters from POSTGRES_URL
    # Format: postgresql://user:pass@host:port/dbname

    python3 <<EOF
import sys
import asyncio
try:
    import asyncpg

    async def test_connection():
        try:
            conn = await asyncpg.connect('${POSTGRES_URL}', timeout=10)
            await conn.execute('SELECT 1')
            await conn.close()
            return True
        except Exception as e:
            print(f"Database connection failed: {e}", file=sys.stderr)
            return False

    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
except ImportError:
    print("asyncpg not available, skipping database check", file=sys.stderr)
    sys.exit(0)
EOF

    if [ $? -eq 0 ]; then
        log_info "Database connectivity verified"
    else
        log_error "Database connectivity check failed (non-fatal, will retry during agent startup)"
    fi
}

# ============================================================================
# Step 4: Run database migrations (if needed)
# ============================================================================
run_migrations() {
    log_info "Checking for database migrations..."

    # Check if migrations module exists
    if [ -f "/app/src/migrations/__init__.py" ]; then
        log_info "Running database migrations for schema: ${DB_SCHEMA:-${DEPARTMENT_ID}_tenant}"
        python3 -m src.migrations migrate --schema "${DB_SCHEMA:-${DEPARTMENT_ID}_tenant}" || {
            log_error "Database migrations failed (non-fatal)"
        }
    else
        log_info "No migrations module found, skipping"
    fi
}

# ============================================================================
# Step 5: Start the AIO voice agent
# ============================================================================
start_agent() {
    log_info "Starting AIO voice agent: ${DEPARTMENT_NAME}"
    log_info "Configuration: ${CONFIG_FILE}"
    log_info "Log level: ${LOG_LEVEL:-INFO}"

    # Export configuration path for agent to read
    export AIO_CONFIG_PATH="${CONFIG_FILE}"

    # Start the agent (blocking call)
    exec python3 -m src.agent start --config "${CONFIG_FILE}"
}

# ============================================================================
# Graceful shutdown handler
# ============================================================================
shutdown_handler() {
    log_info "Received shutdown signal, gracefully terminating..."
    # Agent process will receive SIGTERM and handle cleanup
    exit 0
}

# Trap SIGTERM and SIGINT for graceful shutdown
trap shutdown_handler SIGTERM SIGINT

# ============================================================================
# Main execution
# ============================================================================
main() {
    log_info "Federation AIO Voice Agent Entrypoint v1.0.0"
    log_info "Department: ${DEPARTMENT_NAME:-UNKNOWN}"

    check_env_vars
    generate_config
    check_database_connectivity
    run_migrations
    start_agent
}

# Execute main
main
