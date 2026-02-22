# Multi-stage build for smaller image
# Force rebuild: 2026-01-17T00:14 - Switch to official groq plugin
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies globally
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model so it's baked into the image (not downloaded at runtime)
ENV SENTENCE_TRANSFORMERS_HOME=/app/models
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Production image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder (global site-packages)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded model from builder
COPY --from=builder /app/models /app/models

# Copy application code
COPY src/ ./src/

# Create memory volume directory and set permissions before switching to non-root user
RUN mkdir -p /app/data/memory/sessions && chmod -R 755 /app/data

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash agent
RUN chown -R agent:agent /app/data
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point
ENV PYTHONUNBUFFERED=1
ENV SENTENCE_TRANSFORMERS_HOME=/app/models
ENV AIO_MEMORY_DIR=/app/data/memory
ENV AIO_MODELS_DIR=/app/models
CMD ["python", "-m", "src.agent", "start"]
