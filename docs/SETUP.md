# TeckoChecker Setup Guide

This guide walks you through setting up TeckoChecker from scratch.

## Prerequisites

- **Python 3.11 or higher** installed
- **pip** package manager
- **Git** for cloning the repository
- Basic knowledge of command line operations

## Quick Start

### 1. Clone and Setup Virtual Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/teckochecker.git
cd teckochecker

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Create .env file from template
cp .env.example .env

# Generate a secure SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Edit .env and paste the generated key
nano .env  # or use your preferred editor
```

**Important:** Replace the `SECRET_KEY` value in `.env` with the generated key.

### 4. Initialize Database

```bash
# Method 1: Using the init script (recommended)
python scripts/init_db.py

# Method 2: With automatic .env creation
python scripts/init_db.py --create-env

# Method 3: Reset existing database (WARNING: deletes all data)
python scripts/init_db.py --reset
```

### 5. Verify Setup

```bash
# Run verification script
python scripts/verify_setup.py

# View database schema
python scripts/show_schema.py
```

## Detailed Configuration

### Environment Variables

Edit your `.env` file to customize these settings:

#### Database Configuration
```env
DATABASE_URL=sqlite:///./teckochecker.db
```

For PostgreSQL (future):
```env
DATABASE_URL=postgresql://user:password@localhost/teckochecker
```

#### Security Configuration
```env
SECRET_KEY=<your-generated-key-here>
```

**CRITICAL:** Never commit your `.env` file or share your `SECRET_KEY`!

#### Polling Configuration
```env
DEFAULT_POLL_INTERVAL=120  # Default interval in seconds
MIN_POLL_INTERVAL=30       # Minimum allowed interval
MAX_POLL_INTERVAL=3600     # Maximum allowed interval (1 hour)
MAX_RETRIES=3              # Retry attempts for failed operations
RETRY_DELAY=60             # Delay between retries
```

#### API Configuration
```env
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE=TeckoChecker API
API_VERSION=1.0.0
```

#### Logging Configuration
```env
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=                  # Leave empty for console only
```

#### CORS Configuration (for future UI)
```env
CORS_ORIGINS=["*"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=["*"]
CORS_ALLOW_HEADERS=["*"]
```

## Database Schema

TeckoChecker uses three main tables:

### Secrets Table
Stores encrypted API keys and tokens.

| Column      | Type      | Description                    |
|-------------|-----------|--------------------------------|
| id          | INTEGER   | Primary key                    |
| name        | TEXT      | Unique name for the secret     |
| type        | TEXT      | 'openai' or 'keboola'          |
| value       | TEXT      | Encrypted secret value         |
| created_at  | TIMESTAMP | Creation timestamp             |

### Polling Jobs Table
Tracks polling jobs and their configuration.

| Column                   | Type      | Description                     |
|--------------------------|-----------|--------------------------------|
| id                       | INTEGER   | Primary key                    |
| name                     | TEXT      | Job name                       |
| batch_id                 | TEXT      | OpenAI batch ID to monitor     |
| openai_secret_id         | INTEGER   | FK to secrets table            |
| keboola_secret_id        | INTEGER   | FK to secrets table            |
| keboola_stack_url        | TEXT      | Keboola stack URL              |
| keboola_configuration_id | TEXT      | Keboola config ID to trigger   |
| poll_interval_seconds    | INTEGER   | Polling interval               |
| status                   | TEXT      | 'active', 'paused', 'completed', 'failed' |
| last_check_at            | TIMESTAMP | Last check time                |
| next_check_at            | TIMESTAMP | Next scheduled check           |
| created_at               | TIMESTAMP | Creation timestamp             |
| completed_at             | TIMESTAMP | Completion timestamp           |

### Polling Logs Table
Records polling events and status changes.

| Column      | Type      | Description                    |
|-------------|-----------|--------------------------------|
| id          | INTEGER   | Primary key                    |
| job_id      | INTEGER   | FK to polling_jobs table       |
| status      | TEXT      | Log status                     |
| message     | TEXT      | Log message                    |
| created_at  | TIMESTAMP | Creation timestamp             |

## Running the Application

### Development Mode

```bash
# Start the FastAPI server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Production Mode (Coming Soon)

```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or using the CLI
teckochecker start --daemon
```

## Troubleshooting

### Issue: "Database not initialized"

**Solution:**
```bash
python scripts/init_db.py
```

### Issue: "SECRET_KEY not set" or "Invalid SECRET_KEY"

**Solution:**
```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env file with the generated key
nano .env
```

### Issue: "Cannot import app.models" or "Cannot import app.database"

**Solution:**
This is likely a circular import issue. Make sure you're running scripts from the project root:
```bash
cd /path/to/teckochecker
python scripts/init_db.py
```

### Issue: Database file permission denied

**Solution:**
```bash
# Check database file permissions
ls -la teckochecker.db

# If needed, fix permissions
chmod 644 teckochecker.db
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

## Next Steps

After setup is complete:

1. **Add Secrets**: Store your OpenAI and Keboola API credentials
   ```bash
   teckochecker secret add --name "openai-prod" --type openai
   ```

2. **Create Polling Jobs**: Set up jobs to monitor
   ```bash
   teckochecker job create --name "My Job" --batch-id "batch_123" ...
   ```

3. **Start Polling**: Begin monitoring jobs
   ```bash
   teckochecker start
   ```

## Development Setup

For development, install additional tools:

```bash
# Install development dependencies
pip install pytest black ruff mypy

# Run tests
pytest tests/

# Format code
black app/

# Lint code
ruff check app/

# Type check
mypy app/
```

## Security Best Practices

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Generate unique `SECRET_KEY`** for each environment
3. **Rotate secrets regularly** - Update API keys periodically
4. **Use environment-specific configs** - Different keys for dev/prod
5. **Limit database access** - Set appropriate file permissions
6. **Enable HTTPS in production** - Use reverse proxy (nginx/caddy)

## Support

- **Documentation**: See [docs/prd.md](prd.md) and [docs/architecture.md](architecture.md)
- **Issues**: Report bugs on GitHub Issues
- **Questions**: Open a discussion on GitHub Discussions

## License

Apache License 2.0 - See [LICENSE](../LICENSE) file for details.
