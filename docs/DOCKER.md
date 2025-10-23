# Docker Deployment Guide

This guide explains how to run TeckoChecker in Docker using Google's distroless images for maximum security and minimal size.

## Overview

TeckoChecker uses a multi-stage Docker build with Google's distroless Python image:

- **Base image**: `gcr.io/distroless/python3-debian12:nonroot`
- **Security**: No shell, no package managers, minimal attack surface
- **Size**: Significantly smaller than traditional Python images
- **User**: Runs as non-root user (UID 65532)

## Quick Start

### 1. Generate Encryption Key

First, generate a Fernet encryption key for securing secrets:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save this key - you'll need it to run the container.

### 2. Set Environment Variable

```bash
export SECRET_KEY="your-generated-key-here"
```

### 3. Run with Docker Compose (Recommended)

```bash
# Start the service
make docker-compose-up

# View logs
make docker-compose-logs

# Stop the service
make docker-compose-down
```

### 4. Or Run with Docker Directly

```bash
# Build the image
make docker-build

# Run the container
make docker-run

# View logs
make docker-logs

# Stop the container
make docker-stop
```

## Available Make Commands

### Build Commands

- `make docker-build` - Build production image (distroless)
- `make docker-build-debug` - Build debug image with shell access
- `make docker-test` - Test the Docker image

### Run Commands

- `make docker-run` - Run container directly with Docker
- `make docker-compose-up` - Start services with docker-compose
- `make docker-compose-down` - Stop docker-compose services
- `make docker-compose-logs` - View docker-compose logs

### Management Commands

- `make docker-stop` - Stop and remove Docker container
- `make docker-logs` - View container logs
- `make docker-shell` - Open shell in debug container
- `make docker-clean` - Remove images and volumes

## Manual Docker Commands

### Building

```bash
# Production image
docker build -t teckochecker:latest .

# Debug image (with busybox shell)
docker build -f Dockerfile.debug -t teckochecker:debug .
```

### Running

```bash
# Run in detached mode
docker run -d \
  --name teckochecker \
  -p 8000:8000 \
  -e SECRET_KEY="your-key-here" \
  -v teckochecker-data:/data \
  teckochecker:latest

# Run with custom polling intervals
docker run -d \
  --name teckochecker \
  -p 8000:8000 \
  -e SECRET_KEY="your-key-here" \
  -e POLLING_INTERVAL=30 \
  -e RETRY_INTERVAL=120 \
  -v teckochecker-data:/data \
  teckochecker:latest

# Run CLI commands (example: show status)
docker run --rm \
  -e SECRET_KEY="your-key-here" \
  -v teckochecker-data:/data \
  teckochecker:latest \
  status
```

### Docker Compose

Edit `docker-compose.yml` to customize settings, then:

```bash
# Start services
SECRET_KEY="your-key" docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Configuration

### Environment Variables

Required:
- `SECRET_KEY` - Fernet encryption key for secrets (required)

Optional:
- `DATABASE_URL` - Database location (default: `sqlite:////data/teckochecker.db`)
- `POLLING_INTERVAL` - Seconds between polls (default: 60)
- `RETRY_INTERVAL` - Seconds before retry on error (default: 300)

### Persistent Storage

The container uses a named volume for data persistence:

```bash
# View volume
docker volume inspect teckochecker-data

# Backup volume
docker run --rm \
  -v teckochecker-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/teckochecker-backup.tar.gz -C /data .

# Restore volume
docker run --rm \
  -v teckochecker-data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/teckochecker-backup.tar.gz -C /data
```

### Port Mapping

Default: `8000:8000`

Change the host port if needed:
```bash
docker run -p 9000:8000 ...  # Access on host port 9000
```

## Debugging

### Using Debug Image

The debug image includes busybox for troubleshooting:

```bash
# Build debug image
make docker-build-debug

# Open shell in debug container
make docker-shell

# Inside the container, you can:
# - Check file structure: /busybox/ls -la
# - View files: /busybox/cat /app/teckochecker.py
# - Test Python: python3 -c "import app; print('OK')"
# - Check environment: /busybox/env
```

### Docker Compose Debug Profile

```bash
# Start with debug container
SECRET_KEY="your-key" docker-compose --profile debug up -d teckochecker-debug

# Attach to debug container
docker exec -it teckochecker-debug /busybox/sh
```

### Viewing Logs

```bash
# Follow logs
docker logs -f teckochecker

# Last 100 lines
docker logs --tail 100 teckochecker

# With timestamps
docker logs -t teckochecker
```

### Health Checks

The container includes a health check endpoint:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' teckochecker

# Manual health check
curl http://localhost:8000/health
```

## Security Best Practices

### 1. Use Non-Root User

The distroless image runs as user `nonroot` (UID 65532) by default.

### 2. Protect SECRET_KEY

Never commit SECRET_KEY to version control:

```bash
# Store in .env file (gitignored)
echo "SECRET_KEY=your-key" > .env
source .env
docker-compose up -d

# Or use Docker secrets (Swarm/Kubernetes)
echo "your-key" | docker secret create teckochecker_key -
```

### 3. Network Security

```bash
# Run on custom network
docker network create teckochecker-net
docker run -d \
  --network teckochecker-net \
  --name teckochecker \
  ...
```

### 4. Read-Only Filesystem

```bash
# Run with read-only root filesystem
docker run -d \
  --read-only \
  --tmpfs /tmp \
  -v teckochecker-data:/data \
  ...
```

## Production Deployment

### Docker Swarm

```yaml
# docker-stack.yml
version: '3.8'
services:
  teckochecker:
    image: teckochecker:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:////data/teckochecker.db
    secrets:
      - secret_key
    volumes:
      - teckochecker-data:/data
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '1'
          memory: 512M

secrets:
  secret_key:
    external: true

volumes:
  teckochecker-data:
```

Deploy:
```bash
docker secret create teckochecker_key /path/to/key/file
docker stack deploy -c docker-stack.yml teckochecker
```

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: teckochecker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: teckochecker
  template:
    metadata:
      labels:
        app: teckochecker
    spec:
      containers:
      - name: teckochecker
        image: teckochecker:latest
        ports:
        - containerPort: 8000
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: teckochecker-secret
              key: secret-key
        - name: DATABASE_URL
          value: "sqlite:////data/teckochecker.db"
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          limits:
            cpu: "1"
            memory: "512Mi"
          requests:
            cpu: "250m"
            memory: "128Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: teckochecker-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: teckochecker
spec:
  selector:
    app: teckochecker
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Troubleshooting

### Container Won't Start

1. Check logs: `docker logs teckochecker`
2. Verify SECRET_KEY is set
3. Check volume permissions
4. Try debug image: `make docker-shell`

### Database Locked

```bash
# Stop all containers
docker stop teckochecker

# Clean start
docker rm teckochecker
make docker-run
```

### Out of Memory

Increase memory limits:
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
```

### Network Issues

```bash
# Check container network
docker inspect teckochecker | grep -A 20 NetworkSettings

# Test connectivity from container
docker exec teckochecker python3 -c "import urllib.request; print(urllib.request.urlopen('https://api.openai.com').status)"
```

## Image Details

### Size Comparison

- Distroless image: ~150MB
- Alpine-based: ~300MB
- Debian-based: ~800MB

### Included in Image

- Python 3.11 runtime
- TeckoChecker application
- Python dependencies
- Minimal Debian base (distroless)

### NOT Included

- Shell (bash, sh)
- Package managers (apt, pip)
- System utilities (curl, wget)
- Debugging tools

For debugging, use the `debug` variant which includes busybox.

## References

- [Distroless Images](https://github.com/GoogleContainerTools/distroless)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [TeckoChecker Documentation](../README.md)
