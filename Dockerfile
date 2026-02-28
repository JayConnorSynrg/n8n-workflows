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

# Pre-download fastembed model so it's baked into the image (not downloaded at runtime)
ENV FASTEMBED_CACHE_PATH=/app/fastembed_cache
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

# Production image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder (global site-packages)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded model from builder
COPY --from=builder /app/fastembed_cache /app/fastembed_cache

# Copy application code
COPY src/ ./src/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point — shell wrapper ensures memory volume directory exists at runtime
# (Docker volume mounts replace build-time directories, so mkdir must run at startup)
ENV PYTHONUNBUFFERED=1
ENV FASTEMBED_CACHE_PATH=/app/fastembed_cache
ENV AIO_MEMORY_DIR=/app/data/memory
ENV AIO_MODELS_DIR=/app/fastembed_cache
CMD ["sh", "-c", "mkdir -p /app/data/memory/users/_default && exec python -m src.agent start"]
