# Federation AIO Voice Agent - Multi-stage Base Template
# Version: 1.0.0
# Platform: amd64, arm64
# Target: <500MB final image size

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY entrypoint.sh /app/entrypoint.sh
COPY healthcheck.py /app/healthcheck.py

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 agent && \
    chown -R agent:agent /app && \
    mkdir -p /app/config && \
    chown -R agent:agent /app/config

# Switch to non-root user
USER agent

# Environment variables (injected at deployment time)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEPARTMENT_ID="" \
    DEPARTMENT_NAME="" \
    POSTGRES_URL="" \
    N8N_WEBHOOK_BASE="" \
    LIVEKIT_URL="" \
    LIVEKIT_API_KEY="" \
    LIVEKIT_API_SECRET="" \
    CEREBRAS_API_KEY="" \
    DEEPGRAM_API_KEY="" \
    CARTESIA_API_KEY="" \
    ENABLED_TOOLS="[]" \
    LOG_LEVEL="INFO"

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python /app/healthcheck.py || exit 1

# Expose port for Railway health checks
EXPOSE 8080

# Entrypoint script handles configuration generation
ENTRYPOINT ["/app/entrypoint.sh"]
