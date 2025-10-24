# Docker Volumes Guide

## Overview

TeckoChecker uses Docker volumes for persistent data storage. This guide explains where data is stored and how to access it.

## Volume List

| Volume Name | Purpose | Persistence |
|-------------|---------|-------------|
| `teckochecker-data` | SQLite database | Permanent |
| `teckochecker-logs` | Application logs | Permanent |
| `caddy-data` | Let's Encrypt certificates | Permanent |
| `caddy-config` | Caddy configuration cache | Permanent |

## Physical Location

Docker stores volumes on the host system at:

```
/var/lib/docker/volumes/
├── teckochecker_teckochecker-data/
│   └── _data/
│       └── teckochecker.db          # SQLite database
├── teckochecker_teckochecker-logs/
│   └── _data/
│       └── teckochecker.log         # Application logs
├── teckochecker_caddy-data/
│   └── _data/
│       └── caddy/
│           └── certificates/        # Let's Encrypt certificates
└── teckochecker_caddy-config/
    └── _data/
        └── ...                       # Caddy cache files
```

**Note:** You need `sudo` to access `/var/lib/docker/volumes/` directly.

## Accessing Data

### 1. Database (teckochecker.db)

**View database location:**
```bash
docker volume inspect teckochecker_teckochecker-data
```

**Access database from container:**
```bash
# List files in /data
docker exec teckochecker ls -la /data/

# SQLite shell
docker exec -it teckochecker sqlite3 /data/teckochecker.db

# Example queries
docker exec teckochecker sqlite3 /data/teckochecker.db "SELECT * FROM secrets;"
docker exec teckochecker sqlite3 /data/teckochecker.db "SELECT * FROM polling_jobs;"
docker exec teckochecker sqlite3 /data/teckochecker.db ".schema"
```

**Copy database to host:**
```bash
docker cp teckochecker:/data/teckochecker.db ./teckochecker.db
```

**Backup database:**
```bash
# Method 1: Copy from container
docker cp teckochecker:/data/teckochecker.db ./backup/teckochecker-$(date +%Y%m%d).db

# Method 2: Backup entire volume
docker run --rm \
  -v teckochecker_teckochecker-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/teckochecker-data-$(date +%Y%m%d).tar.gz /data
```

**Restore database:**
```bash
# Stop container first
docker-compose stop teckochecker

# Copy backup to container
docker cp ./teckochecker.db.backup teckochecker:/data/teckochecker.db

# Restart container
docker-compose start teckochecker
```

### 2. Application Logs

**View logs in real-time:**
```bash
# Docker logs (stdout/stderr)
docker-compose logs -f teckochecker

# Application log file
docker exec teckochecker tail -f /app/logs/teckochecker.log
```

**Access log file:**
```bash
# View entire log
docker exec teckochecker cat /app/logs/teckochecker.log

# Last 100 lines
docker exec teckochecker tail -n 100 /app/logs/teckochecker.log

# Copy to host
docker cp teckochecker:/app/logs/teckochecker.log ./teckochecker.log
```

**Configure log file location:**

In `.env` file:
```bash
# Log to volume-mounted directory
LOG_FILE=/app/logs/teckochecker.log

# Or disable file logging (stdout only)
LOG_FILE=
```

### 3. Let's Encrypt Certificates

**View certificate location:**
```bash
docker volume inspect teckochecker_caddy-data
```

**Access certificates:**
```bash
# List certificates
docker exec teckochecker-caddy ls -la /data/caddy/certificates/

# View certificate details
docker exec teckochecker-caddy cat /data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/tt.keboola.ai/tt.keboola.ai.crt
```

**Backup certificates:**
```bash
docker run --rm \
  -v teckochecker_caddy-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/caddy-certs-$(date +%Y%m%d).tar.gz /data
```

### 4. Caddy Access Logs

**View access logs:**
```bash
# Real-time
docker exec teckochecker-caddy tail -f /var/log/caddy/access.log

# Full log
docker exec teckochecker-caddy cat /var/log/caddy/access.log

# Copy to host
docker cp teckochecker-caddy:/var/log/caddy/access.log ./caddy-access.log
```

**Parse JSON logs:**
```bash
# Pretty print with jq
docker exec teckochecker-caddy cat /var/log/caddy/access.log | jq .

# Filter by status code
docker exec teckochecker-caddy cat /var/log/caddy/access.log | jq 'select(.status == 200)'

# Show only failed requests
docker exec teckochecker-caddy cat /var/log/caddy/access.log | jq 'select(.status >= 400)'
```

## Volume Management

### List All Volumes

```bash
docker volume ls | grep teckochecker
```

### Inspect Volume

```bash
docker volume inspect teckochecker_teckochecker-data
```

### Volume Size

```bash
# All Docker volumes
docker system df -v

# Specific volume
sudo du -sh /var/lib/docker/volumes/teckochecker_teckochecker-data/
```

### Remove Volumes (⚠️ DESTRUCTIVE)

```bash
# Stop services first
docker-compose down

# Remove specific volume
docker volume rm teckochecker_teckochecker-data

# Remove all project volumes
docker-compose down -v

# Remove unused volumes
docker volume prune
```

**Warning:** This deletes all data permanently!

## Backup Strategy

### Automated Daily Backup Script

Create `/home/ubuntu/backup-teckochecker.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker cp teckochecker:/data/teckochecker.db \
  $BACKUP_DIR/teckochecker-$DATE.db

# Backup logs
docker cp teckochecker:/app/logs/teckochecker.log \
  $BACKUP_DIR/teckochecker-$DATE.log

# Keep only last 7 days
find $BACKUP_DIR -name "teckochecker-*.db" -mtime +7 -delete
find $BACKUP_DIR -name "teckochecker-*.log" -mtime +7 -delete

echo "Backup completed: $DATE"
```

**Schedule with cron:**
```bash
chmod +x /home/ubuntu/backup-teckochecker.sh

crontab -e
# Add line:
0 2 * * * /home/ubuntu/backup-teckochecker.sh >> /home/ubuntu/backup.log 2>&1
```

### Manual Backup

```bash
# Create backup directory
mkdir -p ~/backups/$(date +%Y%m%d)

# Database
docker cp teckochecker:/data/teckochecker.db ~/backups/$(date +%Y%m%d)/

# Logs
docker cp teckochecker:/app/logs/teckochecker.log ~/backups/$(date +%Y%m%d)/

# Caddy certificates
docker run --rm \
  -v teckochecker_caddy-data:/data \
  -v ~/backups/$(date +%Y%m%d):/backup \
  alpine tar czf /backup/caddy-data.tar.gz /data

# Create archive
cd ~/backups
tar czf teckochecker-backup-$(date +%Y%m%d).tar.gz $(date +%Y%m%d)/
```

## Restore from Backup

```bash
# Stop services
docker-compose down

# Restore database
docker cp ~/backups/20250101/teckochecker.db teckochecker:/data/teckochecker.db

# Restore Caddy data (certificates)
docker run --rm \
  -v teckochecker_caddy-data:/data \
  -v ~/backups/20250101:/backup \
  alpine sh -c "cd / && tar xzf /backup/caddy-data.tar.gz"

# Start services
docker-compose up -d

# Verify
docker-compose logs -f
```

## Monitoring Volume Usage

### Disk Space Alert Script

Create `/home/ubuntu/check-disk-space.sh`:

```bash
#!/bin/bash
THRESHOLD=80
USAGE=$(df -h /var/lib/docker | awk 'NR==2 {print $5}' | sed 's/%//')

if [ $USAGE -gt $THRESHOLD ]; then
    echo "WARNING: Docker volume usage is ${USAGE}%"
    docker system df -v
fi
```

**Schedule with cron:**
```bash
chmod +x /home/ubuntu/check-disk-space.sh

crontab -e
# Add line:
0 */6 * * * /home/ubuntu/check-disk-space.sh
```

## Troubleshooting

### Volume Not Mounting

```bash
# Check if volume exists
docker volume ls | grep teckochecker

# Recreate volume
docker-compose down
docker volume create teckochecker_teckochecker-data
docker-compose up -d
```

### Permission Denied

```bash
# Check container user
docker exec teckochecker id

# Fix permissions (if needed)
docker exec --user root teckochecker chown -R 65532:65532 /data
```

### Database Locked

```bash
# Check for multiple connections
docker exec teckochecker fuser /data/teckochecker.db

# Stop all services accessing DB
docker-compose stop teckochecker

# Check integrity
docker exec teckochecker sqlite3 /data/teckochecker.db "PRAGMA integrity_check;"
```

### Volume Corruption

```bash
# Check volume
docker volume inspect teckochecker_teckochecker-data

# Backup current data
docker cp teckochecker:/data/teckochecker.db ./corrupted.db

# Recreate volume
docker-compose down
docker volume rm teckochecker_teckochecker-data
docker-compose up -d

# Restore from backup
docker cp ./backup.db teckochecker:/data/teckochecker.db
docker-compose restart teckochecker
```

## Best Practices

1. **Regular Backups**: Automate daily database backups
2. **Monitor Disk Space**: Set up alerts for volume usage
3. **Version Control**: Keep docker-compose.yml in git
4. **Separate Volumes**: Don't mix data types in one volume
5. **Named Volumes**: Use named volumes (not bind mounts) for portability
6. **Backup Before Updates**: Always backup before upgrading
7. **Test Restores**: Regularly test backup restoration process
8. **Off-site Backups**: Copy backups to S3 or other cloud storage

## AWS-Specific Notes

### EBS Volume Snapshots

Consider using AWS EBS snapshots for the entire EC2 instance:

```bash
aws ec2 create-snapshot \
  --volume-id vol-xxxxx \
  --description "TeckoChecker backup $(date +%Y%m%d)"
```

### S3 Backup Integration

```bash
# Install AWS CLI
sudo apt install awscli

# Upload backup to S3
aws s3 cp ~/backups/teckochecker-backup-$(date +%Y%m%d).tar.gz \
  s3://your-bucket/teckochecker-backups/
```

## Reference

- Database: `/data/teckochecker.db` (inside container)
- Logs: `/app/logs/teckochecker.log` (inside container)
- Certificates: `/data/caddy/certificates/` (inside caddy container)
- Volume mount: `/var/lib/docker/volumes/` (on host)
