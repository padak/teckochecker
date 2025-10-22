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
git clone https://github.com/padak/teckochecker.git
cd teckochecker

# Create virtual environment
python3 -m venv venv

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

### 3. Initialize Database and Environment

**Recommended - Interactive Setup:**
```bash
# Run the interactive setup wizard
# This will guide you through:
# 1. Creating .env file with auto-generated SECRET_KEY
# 2. Initializing database tables
python teckochecker.py setup
```

**Alternative - Automatic Setup (non-interactive):**
```bash
# This command will:
# 1. Create .env file from .env.example (if it doesn't exist)
# 2. Auto-generate a secure SECRET_KEY using Fernet encryption
# 3. Initialize the database tables
python teckochecker.py init --generate-env
```

**Advanced - Manual Setup:**
```bash
# Step 1: Create .env file
cp .env.example .env

# Step 2: Generate a secure SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Step 3: Edit .env and paste the generated key
nano .env  # or use your preferred editor

# Step 4: Initialize database
python teckochecker.py init
```

**What is SECRET_KEY?**
The `SECRET_KEY` is used for AES-256 encryption of API keys and tokens stored in the database. It's generated using the Fernet encryption library (part of cryptography package). This ensures that your OpenAI and Keboola credentials are stored securely and cannot be read without the correct key.

**Important Security Notes:**
- Never commit your `.env` file to git (it's already in `.gitignore`)
- Keep the same `SECRET_KEY` across runs - changing it will make existing secrets unreadable
- Back up your `SECRET_KEY` securely - losing it means losing access to all stored secrets
- Use different `SECRET_KEY` values for development and production environments

### 4. Verify Setup

```bash
# Make sure virtual environment is activated
source venv/bin/activate

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
| keboola_component_id     | TEXT      | Keboola component ID           |
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
# Make sure virtual environment is activated
source venv/bin/activate

# Start the FastAPI server with auto-reload (polling service starts automatically)
python teckochecker.py start --reload
```

Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Note: The polling service starts automatically with the API server.

### Production Mode

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start the server as daemon
python teckochecker.py start --daemon
```

## Troubleshooting

### Issue: "Database not initialized"

**Solution:**
```bash
# Initialize database only (assumes .env already exists)
python teckochecker.py init

# Or run full setup if .env also needs to be created
python teckochecker.py setup
```

### Issue: "SECRET_KEY not set" or "Invalid SECRET_KEY"

**Solution:**
```bash
# Method 1: Generate a new key manually
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then update .env file with the generated key:
nano .env

# Method 2: Use automatic setup (recreates .env with new SECRET_KEY)
# WARNING: This will overwrite your existing .env file
python teckochecker.py init --generate-env

# Method 3: Use interactive setup wizard
python teckochecker.py setup
```

**Note:** The SECRET_KEY must be a valid Fernet key (44 characters, base64-encoded). If you change the SECRET_KEY, all previously encrypted secrets will become unreadable.

### Issue: "Cannot import app.models" or "Cannot import app.database"

**Solution:**
This is likely a circular import issue. Make sure you're running commands from the project root:
```bash
cd /path/to/teckochecker
source venv/bin/activate
python teckochecker.py init
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

After setup is complete, see the [User Guide](USER_GUIDE.md) for detailed instructions on:

1. **Managing Secrets**: How to add and manage your OpenAI and Keboola API credentials
2. **Creating Polling Jobs**: Complete examples with all required parameters including component IDs
3. **Running the Service**: Starting and managing the polling service

Quick example to get started:
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Add your API credentials
python teckochecker.py secret add --name "openai-prod" --type openai
python teckochecker.py secret add --name "keboola-prod" --type keboola

# Start the API server (polling service starts automatically)
python teckochecker.py start --reload

# In another terminal (also activate venv first), check system status
source venv/bin/activate
python teckochecker.py status
```

For full command reference and examples, please refer to the [User Guide](USER_GUIDE.md).

## Development Setup

For development, install additional tools:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

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

- **Documentation**: See [prd.md](prd.md) and [architecture/](architecture/)
- **Issues**: Report bugs on GitHub Issues
- **Questions**: Open a discussion on GitHub Discussions

## License

Apache License 2.0 - See [LICENSE](../LICENSE) file for details.
