# AWS EC2 Deployment Guide

Complete guide for deploying TeckoChecker to AWS EC2 (t4g.micro ARM Ubuntu).

## Prerequisites

- AWS EC2 instance (t4g.micro or larger, Ubuntu 22.04 LTS)
- Domain name (optional, for automatic Let's Encrypt HTTPS)
- SSH access to EC2 instance

## Architecture

```
Internet → AWS Security Group (80, 443) → Caddy (HTTPS) → TeckoChecker (localhost:8000)
```

- **TeckoChecker**: Bound to `127.0.0.1:8000` (localhost only)
- **Caddy**: Public-facing reverse proxy on ports 80/443 with automatic HTTPS

## Step 1: AWS Security Group Configuration

Configure your EC2 security group to allow:

| Type  | Protocol | Port Range | Source    | Description               |
|-------|----------|------------|-----------|---------------------------|
| SSH   | TCP      | 22         | Your IP   | SSH access                |
| HTTP  | TCP      | 80         | 0.0.0.0/0 | Let's Encrypt challenge   |
| HTTPS | TCP      | 443        | 0.0.0.0/0 | HTTPS traffic             |

```bash
# Using AWS CLI (replace sg-xxxxx with your security group ID)
aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 22 --cidr YOUR_IP/32
aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id sg-xxxxx --protocol tcp --port 443 --cidr 0.0.0.0/0
```

## Step 2: DNS Configuration (Optional but Recommended)

If you have a domain, create an A record:

```
Type: A
Name: teckochecker (or subdomain of your choice)
Value: YOUR_EC2_PUBLIC_IP
TTL: 300
```

Example: `teckochecker.yourdomain.com` → `54.123.45.67`

**Without domain**: Skip this step and use `Caddyfile.ip-only` (see Step 5).

## Step 3: Install Docker on EC2

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Log out and log back in for group changes to take effect
exit
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Verify Docker works
docker --version
docker-compose --version
```

## Step 4: Clone Repository

```bash
# Clone to home directory
cd /home/ubuntu
git clone https://github.com/padak/teckochecker.git
cd teckochecker

# Verify you're on main branch
git branch
git log --oneline -3
```

## Step 5: Configure Caddyfile

### Option A: With Domain (Recommended)

Edit `Caddyfile` and replace `your-domain.com` with your actual domain:

```bash
nano Caddyfile
```

Change line:
```
your-domain.com {
```

To:
```
teckochecker.yourdomain.com {
```

### Option B: Without Domain (IP Only)

Use the IP-only configuration with self-signed certificate:

```bash
# Replace Caddyfile with IP-only version
cp Caddyfile.ip-only Caddyfile
```

**Note**: Browsers will show a security warning. You'll need to accept the self-signed certificate.

## Step 6: Generate SECRET_KEY

```bash
# Generate a secure encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Save the output - you'll need it in the next step
# Example output: qYxW00Bw3IWPNaIMP5u1QRM83AfaEWg4hRcoIiC_zrg=
```

## Step 7: Create .env File

```bash
# Create .env file with your SECRET_KEY
cat > .env << 'EOF'
# REQUIRED: Encryption key for secrets
SECRET_KEY=PASTE_YOUR_GENERATED_KEY_HERE

# Optional: Customize polling intervals (seconds)
DEFAULT_POLL_INTERVAL=120
RETRY_DELAY=300

# Optional: API configuration
API_HOST=0.0.0.0
API_PORT=8000

# Optional: Logging
LOG_LEVEL=INFO
EOF

# Edit and paste your actual SECRET_KEY
nano .env
```

## Step 8: Build and Start Services

```bash
# Build Docker images (this may take 5-10 minutes on t4g.micro)
docker-compose build

# Start services in detached mode
docker-compose up -d

# Check if services are running
docker-compose ps

# Expected output:
# NAME                  STATUS    PORTS
# teckochecker          Up        127.0.0.1:8000->8000/tcp
# teckochecker-caddy    Up        80/tcp, 443/tcp
```

## Step 9: Verify Deployment

```bash
# Check logs
docker-compose logs -f

# Test health endpoint locally
curl http://localhost:8000/api/health

# Test HTTPS from outside (replace with your domain or IP)
curl https://teckochecker.yourdomain.com/api/health

# Or with IP (accept self-signed cert)
curl -k https://YOUR_EC2_IP/api/health
```

Expected response:
```json
{"status":"healthy"}
```

## Step 10: Initialize Database

```bash
# Run init command inside container
docker-compose exec teckochecker python3 teckochecker.py init

# Verify database was created
docker-compose exec teckochecker python3 -c "import sqlite3; conn = sqlite3.connect('/data/teckochecker.db'); print('Tables:', [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"
```

## Access Web UI

Open browser and navigate to:

- **With domain**: `https://teckochecker.yourdomain.com`
- **With IP only**: `https://YOUR_EC2_IP` (accept security warning)

You should see the TeckoChecker Web UI.

## Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Only TeckoChecker
docker-compose logs -f teckochecker

# Only Caddy
docker-compose logs -f caddy

# Last 100 lines
docker-compose logs --tail=100
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart only TeckoChecker
docker-compose restart teckochecker

# Restart only Caddy
docker-compose restart caddy
```

### Update Application

```bash
# Pull latest changes
cd /home/ubuntu/teckochecker
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs -f
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database!)
docker-compose down -v
```

### Backup Database

```bash
# Copy database from container to host
docker cp teckochecker:/data/teckochecker.db ./teckochecker.db.backup

# Or backup entire volume
docker run --rm -v teckochecker_teckochecker-data:/data -v $(pwd):/backup alpine tar czf /backup/teckochecker-data-backup.tar.gz /data
```

### Restore Database

```bash
# Copy database from host to container
docker cp ./teckochecker.db.backup teckochecker:/data/teckochecker.db

# Restart service
docker-compose restart teckochecker
```

## Monitoring

### Resource Usage

```bash
# Real-time resource usage
docker stats teckochecker teckochecker-caddy

# Disk usage
docker system df

# Container details
docker-compose top
```

### Health Checks

```bash
# Check health status
docker-compose ps

# Manually trigger health check
docker exec teckochecker python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read())"
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker-compose logs

# Check if ports are already in use
sudo netstat -tulpn | grep -E ':(80|443|8000)'

# Verify SECRET_KEY is set
docker-compose config | grep SECRET_KEY
```

### Let's Encrypt Certificate Issues

```bash
# Check Caddy logs
docker-compose logs caddy

# Verify DNS points to your EC2 IP
dig +short teckochecker.yourdomain.com

# Verify port 80 is accessible from internet
curl -I http://teckochecker.yourdomain.com

# Manually reload Caddy config
docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### Database Corruption

```bash
# Stop services
docker-compose down

# Check database integrity
docker run --rm -v teckochecker_teckochecker-data:/data alpine sh -c "cd /data && sqlite3 teckochecker.db 'PRAGMA integrity_check;'"

# If corrupted, restore from backup or recreate
docker volume rm teckochecker_teckochecker-data
docker-compose up -d
docker-compose exec teckochecker python3 teckochecker.py init
```

### Out of Memory on t4g.micro

```bash
# Check memory usage
free -h

# Add swap space (1GB)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```

### Build Fails on ARM

```bash
# Check Docker platform
docker version | grep -i arch

# Verify you're using ARM-compatible base image
docker-compose build --no-cache

# If still fails, check requirements.txt for ARM-incompatible packages
```

## Security Best Practices

1. **Restrict SSH Access**: Only allow your IP in security group
2. **Keep SECRET_KEY Safe**: Never commit to git, use `.env` file
3. **Regular Updates**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   docker-compose pull
   docker-compose up -d
   ```
4. **Firewall**: Consider enabling UFW:
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```
5. **Automated Backups**: Set up cron job for daily database backups
6. **Monitoring**: Set up CloudWatch alarms for CPU/memory/disk usage

## Performance Tuning for t4g.micro

### Reduce Memory Usage

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 384M
    reservations:
      cpus: '0.1'
      memory: 64M
```

### Increase Polling Interval

Edit `.env`:

```bash
DEFAULT_POLL_INTERVAL=300  # Poll every 5 minutes instead of 2
```

### Disable Caddy Access Logs

Edit `Caddyfile` and remove the `log` block.

## Cost Optimization

- **t4g.micro**: ~$3-4/month (free tier: 750 hours/month for 12 months)
- **EBS Storage**: ~$0.08/GB/month (8GB = ~$0.64/month)
- **Data Transfer**: First 100GB/month free
- **Total estimated cost**: ~$4-5/month (after free tier)

## Next Steps

1. **Create API Secrets**: Add OpenAI and Keboola credentials via Web UI or CLI
2. **Create Polling Jobs**: Set up batch monitoring jobs
3. **Configure Monitoring**: Set up CloudWatch or external monitoring
4. **Backups**: Implement automated backup strategy
5. **CI/CD**: Set up GitHub Actions for automated deployments

## Support

For issues specific to AWS deployment:
- Check CloudWatch logs
- Review security group rules
- Verify IAM permissions (if using AWS services)

For TeckoChecker issues:
- See main README.md
- Run `make test` locally before deploying
- Check application logs: `docker-compose logs -f teckochecker`
