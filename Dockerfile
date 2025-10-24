# Multi-stage Dockerfile using Google's distroless Python image
# Stage 1: Builder - install dependencies
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies to a specific directory
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY teckochecker.py .

# Create /data directory with permissions for nonroot user (UID 65532)
RUN mkdir -p /data && chown -R 65532:65532 /data

# Stage 2: Runtime - distroless image
FROM gcr.io/distroless/python3-debian12:nonroot

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code from builder
COPY --from=builder /app /app

# Copy /data directory with correct permissions from builder
COPY --from=builder --chown=65532:65532 /data /data

# Ensure Python can find the installed packages
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:/app
ENV PYTHONUNBUFFERED=1

# Switch to nonroot user (UID 65532)
USER nonroot

# Expose API port
EXPOSE 8000

# Default command: Start the API server
# Configuration is loaded from environment variables
# For CLI commands, override with docker run command
ENTRYPOINT ["python3", "teckochecker.py"]
CMD ["start"]
