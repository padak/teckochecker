# TeckoChecker

A lightweight polling orchestration system that monitors asynchronous job statuses and triggers downstream workflows. TeckoChecker bridges the gap between OpenAI's batch processing capabilities and Keboola's data pipeline execution, automating the workflow from batch job completion to data processing.

## Key Features

- Automated monitoring of OpenAI batch job completion status
- Automatic triggering of Keboola workflows when jobs complete
- Secure credential management with encryption
- Flexible polling intervals configurable per job
- REST API for programmatic access and future UI integration
- Rich CLI interface with shell completion support

*This project was inspired by the idea of Tomáš Trnka (tomas.trnka@live.com), who is the spiritual father of this repository.*

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/teckochecker.git
cd teckochecker
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Initialize
python scripts/init_db.py --create-env

# Add credentials
teckochecker secret add --name "openai-prod" --type openai
teckochecker secret add --name "keboola-prod" --type keboola

# Create a polling job
teckochecker job create \
  --name "My Batch Job" \
  --batch-id "batch_abc123" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.keboola.com" \
  --config-id "123456"

# Start the daemon
teckochecker start --daemon
```

## Documentation

- [USER_GUIDE.md](docs/USER_GUIDE.md) - Comprehensive usage guide with detailed command examples
- [architecture.md](docs/architecture.md) - Technical architecture and design patterns
- [prd.md](docs/prd.md) - Product requirements and specifications
- [SETUP.md](docs/SETUP.md) - Detailed setup and configuration instructions

## Development

The project uses a standard Python development workflow with virtual environments and pip. Development commands and common tasks can be run directly using Python tooling:

```bash
# Run tests
python -m pytest tests/

# Format code
black app/

# Lint
ruff check app/

# Run API server with auto-reload
python -m uvicorn app.main:app --reload
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.