# Dockerfile for FastAPI Backend (Non-root user)
FROM python:3.11-slim AS runtime

# Set environment variables:
# - PYTHONDONTWRITEBYTECODE: Disables writing .pyc files (cleaner container state)
# - PYTHONUNBUFFERED: Flushes stdout/stderr immediately for real-time log monitoring
# - PIP_NO_CACHE_DIR: Eliminates redundant pip caching to minimize image size
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install essential OS dependencies and clear package caches to minimize CVE attack surface
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# DevSecOps Best Practice: Never run containers as root
# Create an explicit unprivileged system user and group (UID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code with non-root ownership
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup run.py .

# Drop privileges to non-root user
USER appuser

EXPOSE 8000

# DevSecOps Healthcheck probe for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
