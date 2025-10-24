# Security Guide

## Basic Authentication Setup

TeckoChecker uses Caddy's Basic Auth to protect the API and Web UI.

### Generate Password Hash

**On EC2:**
```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext "your-secure-password"
```

This outputs a bcrypt hash like:
```
$2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5BykvkMTR8zA4Y.jgO
```

### Update Caddyfile

1. Edit `Caddyfile` or `Caddyfile.letsencrypt-manual`:

```bash
nano Caddyfile.letsencrypt-manual
```

2. Update the `basicauth` section:

```
basicauth {
    # Username: your-username
    your-username $2a$14$YOUR_GENERATED_HASH_HERE
}
```

3. You can add multiple users:

```
basicauth {
    admin $2a$14$hash1...
    readonly $2a$14$hash2...
    api-user $2a$14$hash3...
}
```

### Apply Changes

```bash
# Copy updated Caddyfile
cp Caddyfile.letsencrypt-manual Caddyfile

# Reload Caddy (no downtime)
docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Or restart Caddy service
docker-compose restart caddy
```

### Test Authentication

```bash
# Without auth (should fail with 401)
curl https://tt.keboola.ai/api/secrets

# With auth (should succeed)
curl -u admin:your-password https://tt.keboola.ai/api/secrets

# Health check (no auth required)
curl https://tt.keboola.ai/api/health
```

### Browser Access

When accessing `https://tt.keboola.ai` in browser:
1. Browser will prompt for username/password
2. Enter credentials from Caddyfile
3. Browser caches credentials for the session

### API Access with Authentication

**Python:**
```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.get(
    "https://tt.keboola.ai/api/secrets",
    auth=HTTPBasicAuth("admin", "your-password")
)
```

**curl:**
```bash
curl -u admin:password https://tt.keboola.ai/api/jobs
```

**JavaScript:**
```javascript
fetch("https://tt.keboola.ai/api/secrets", {
    headers: {
        'Authorization': 'Basic ' + btoa('admin:password')
    }
})
```

## Default Credentials

**⚠️ SECURITY WARNING ⚠️**

The default Caddyfile includes:
- **Username:** `admin`
- **Password:** `changeme`

**YOU MUST CHANGE THIS IMMEDIATELY!**

## Endpoints Without Authentication

These endpoints are public (no auth required):
- `/api/health` - Health check for monitoring

All other endpoints require authentication.

## Additional Security Measures

### 1. SSH Key Only (No Password)

```bash
# On EC2
sudo nano /etc/ssh/sshd_config

# Set:
PasswordAuthentication no
PubkeyAuthentication yes

sudo systemctl restart sshd
```

### 2. Firewall (UFW)

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 3. Fail2Ban (Brute Force Protection)

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4. Regular Updates

```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Docker images
cd /home/ubuntu/teckochecker
docker-compose pull
docker-compose up -d
```

### 5. Secret Key Protection

Never commit `.env` file to git:

```bash
# Verify .env is ignored
cat .gitignore | grep .env

# Set restrictive permissions
chmod 600 .env
```

### 6. Database Encryption

The `SECRET_KEY` in `.env` encrypts all API keys stored in the database using Fernet (AES-256).

**Backup your SECRET_KEY securely!** Without it, encrypted secrets cannot be decrypted.

```bash
# Backup SECRET_KEY
grep SECRET_KEY .env > secret_key.backup

# Store securely (AWS Secrets Manager, 1Password, etc.)
```

### 7. HTTPS Only

- Never expose port 8000 directly to the internet
- Always use Caddy reverse proxy with HTTPS
- Current setup: TeckoChecker bound to 127.0.0.1:8000 (localhost only)

### 8. AWS Security Group Best Practices

Minimum required rules:
```
Inbound:
- SSH (22): Your IP only
- HTTPS (443): 0.0.0.0/0
- HTTP (80): 0.0.0.0/0 (only during Let's Encrypt renewal, then close)

Outbound:
- All traffic (for API calls to OpenAI, Keboola)
```

### 9. Monitoring Failed Authentication Attempts

```bash
# Check Caddy access logs for 401 responses
docker exec teckochecker-caddy cat /var/log/caddy/access.log | grep 401

# Set up alert for repeated failures
```

### 10. API Rate Limiting (Future Enhancement)

Consider adding rate limiting to Caddyfile:

```
rate_limit {
    zone dynamic {
        key {remote_host}
        events 100
        window 1m
    }
}
```

## Incident Response

### If Credentials Compromised

1. Generate new password hash:
   ```bash
   docker run --rm caddy:2-alpine caddy hash-password --plaintext "new-password"
   ```

2. Update Caddyfile and reload:
   ```bash
   nano Caddyfile
   docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile
   ```

3. Review logs for unauthorized access:
   ```bash
   docker-compose logs caddy | grep -v "401 Unauthorized"
   ```

4. Rotate API secrets in database if necessary

### If SECRET_KEY Compromised

**⚠️ CRITICAL: All stored secrets will need re-encryption**

1. Stop services:
   ```bash
   docker-compose down
   ```

2. Generate new SECRET_KEY:
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. Export all secrets (before changing key):
   ```bash
   # Backup database
   docker cp teckochecker:/data/teckochecker.db ./backup.db
   ```

4. Update `.env` with new SECRET_KEY

5. Re-create all secrets via API/CLI with new key

6. Restart services

## Security Checklist

- [ ] Changed default password (`admin:changeme`)
- [ ] SECRET_KEY backed up securely
- [ ] SSH password authentication disabled
- [ ] Firewall (UFW) enabled
- [ ] Fail2Ban configured
- [ ] AWS Security Group restricted to minimum ports
- [ ] Port 80 closed (except during cert renewal)
- [ ] Regular updates scheduled
- [ ] Database backups automated
- [ ] Monitoring alerts configured
- [ ] `.env` file not committed to git
- [ ] `.env` permissions set to 600
- [ ] Tested authentication works
- [ ] Documented credentials in secure vault

## Compliance

### Data Encryption
- **In Transit**: TLS 1.3 (Let's Encrypt certificates)
- **At Rest**: Fernet encryption (AES-256) for API keys in database

### Access Control
- Basic Authentication for all API endpoints
- Multi-user support with different credentials
- Public health check endpoint for monitoring

### Audit Trail
- Caddy access logs: All HTTP requests logged
- Application logs: Polling activity, API calls, errors
- Docker logs: Container lifecycle events

## Support

For security issues, please:
1. Do NOT open a public GitHub issue
2. Contact repository maintainers privately
3. Allow time for patch before disclosure
