# TeckoChecker

A lightweight polling orchestration system that monitors asynchronous job statuses and triggers downstream workflows. TeckoChecker bridges the gap between OpenAI's batch processing capabilities and Keboola's data pipeline execution, automating the workflow from batch job completion to data processing.

## Key Features

- **Web UI** - Terminal-style web interface for managing secrets, jobs, and monitoring
- **Automated Monitoring** - Continuous polling of OpenAI batch job completion status
- **Workflow Automation** - Automatic triggering of Keboola workflows when jobs complete
- **Secure Credentials** - AES-256 encrypted credential management
- **Flexible Polling** - Configurable intervals (30s - 1 hour) per job
- **REST API** - Full-featured API for programmatic access
- **Rich CLI** - Command-line interface with shell completion support

*This project was inspired by the idea of Tomáš Trnka (tomas.trnka@live.com), who is the spiritual father of this repository.*

## Quick Start

```bash
# Clone and install
git clone https://github.com/padak/teckochecker.git
cd teckochecker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup (interactive wizard)
python teckochecker.py setup

# Start the service
python teckochecker.py start

# Open Web UI
open http://127.0.0.1:8000/web
```

**See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions and configuration options.**

## Web Interface

TeckoChecker includes a terminal-style web UI for managing the system:

```bash
# Start the server
python teckochecker.py start

# Access the Web UI
open http://127.0.0.1:8000/web
```

The Web UI provides:
- 🔐 **Secrets Management** - Add, list, and delete encrypted credentials
- 📋 **Jobs Dashboard** - Create, monitor, pause/resume polling jobs
- 📊 **Real-time Monitoring** - System stats and activity feed
- 📜 **Log Viewer** - Tail-like log display with auto-refresh
- ⚙️ **System Info** - Health checks and API documentation

See [docs/prd.md](docs/prd.md) Web UI Requirements section for detailed documentation.

## Documentation

- [docs/prd.md](docs/prd.md) - Product requirements, specifications, and Web UI documentation
- [docs/SETUP.md](docs/SETUP.md) - Detailed setup and configuration instructions
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - Comprehensive usage guide with command examples
- [docs/architecture/](docs/architecture/) - Technical architecture and design patterns

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
python teckochecker.py start --reload
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.