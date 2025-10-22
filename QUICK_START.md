# TeckoChecker - Quick Start Guide

Get TeckoChecker up and running in 5 minutes!

## Prerequisites

- Python 3.11 or higher
- pip package manager

## Installation Steps

### 1. Create Virtual Environment

```bash
cd /Users/padak/github/teckochecker
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Option A: Manual configuration
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output and paste it as SECRET_KEY in .env

# Option B: Automatic configuration (recommended)
python scripts/init_db.py --create-env
```

### 4. Initialize Database

```bash
python scripts/init_db.py
```

### 5. Verify Setup

```bash
python scripts/verify_setup.py
```

## What's Next?

After setup is complete, you can:

1. **Start the API Server** (when implemented):
   ```bash
   uvicorn app.main:app --reload
   ```

2. **Use the CLI** (when implemented):
   ```bash
   python teckochecker.py --help
   ```

3. **View Schema**:
   ```bash
   python scripts/show_schema.py
   ```

## Project Structure

```
teckochecker/
├── app/
│   ├── config.py          # ✅ Configuration management
│   ├── database.py        # ✅ Database setup
│   ├── models.py          # ✅ SQLAlchemy models
│   ├── schemas.py         # Pydantic schemas (next)
│   ├── main.py            # FastAPI app (next)
│   ├── api/               # API endpoints (next)
│   ├── cli/               # CLI commands (next)
│   ├── services/          # Business logic (next)
│   └── integrations/      # External clients (next)
├── scripts/
│   ├── init_db.py         # ✅ Database initialization
│   ├── verify_setup.py    # ✅ Setup verification
│   └── show_schema.py     # ✅ Schema visualization
├── docs/
│   ├── SETUP.md           # ✅ Detailed setup guide
│   ├── prd.md             # ✅ Product requirements
│   └── architecture.md    # ✅ System architecture
├── .env.example           # ✅ Configuration template
└── requirements.txt       # ✅ Python dependencies
```

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py

# Reset database (deletes all data!)
python scripts/init_db.py --reset

# Verify setup
python scripts/verify_setup.py

# View database schema
python scripts/show_schema.py

# Deactivate virtual environment
deactivate
```

## Troubleshooting

### Issue: "Module not found" errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: "SECRET_KEY not set"
```bash
# Generate a new key and update .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
nano .env  # paste the key
```

### Issue: "Database not initialized"
```bash
python scripts/init_db.py
```

## Need Help?

- 📖 **Detailed Setup**: See [docs/SETUP.md](docs/SETUP.md)
- 📋 **Architecture**: See [docs/architecture.md](docs/architecture.md)
- 📝 **Requirements**: See [docs/prd.md](docs/prd.md)
- 📄 **Implementation**: See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## What's Been Implemented

✅ **Phase 1 - Database Layer** (Complete)
- Project structure
- Configuration management (Pydantic Settings)
- Database setup (SQLAlchemy 2.0)
- Models: Secret, PollingJob, PollingLog
- Initialization scripts
- Verification scripts
- Documentation

🚧 **Phase 2 - Services** (Next)
- Secrets management with encryption
- Polling jobs CRUD
- OpenAI integration
- Keboola integration
- Polling engine
- REST API
- CLI commands

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
