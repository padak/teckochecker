# Changelog

All notable changes to TeckoChecker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2025-01-22

### Added - Web UI 🎉

**Terminal-Style Web Interface**
- Complete web-based administration interface at `/web`
- Terminal/hacker aesthetic matching CLI design (green-on-black theme)
- ASCII art header with monospace fonts and glowing effects
- No build process required - pure HTML/CSS/JavaScript

**Secrets Management**
- Add, list, and delete encrypted secrets via web UI
- Modal forms with validation
- Secret values never displayed for security
- Support for OpenAI and Keboola credential types

**Jobs Dashboard**
- Create polling jobs with full configuration
- Real-time status indicators with animations:
  - 🟢 Active (pulsing green dot)
  - ⚪ Paused
  - ✓ Completed
  - 🔴 Failed
- Pause/resume job execution
- Delete jobs with confirmation dialogs
- Next check countdown display

**Monitoring & Logs**
- System health dashboard
- Active/total jobs statistics
- Recent activity feed
- Log viewer with color-coded messages:
  - Green: Info/Success
  - Yellow: Warning
  - Red: Error
- Auto-refresh toggle (5-second intervals)
- Manual refresh and clear functions

**System Information**
- Health check integration
- API endpoints reference
- System configuration display

**Technical Implementation**
- FastAPI static file serving
- REST API client with error handling
- Responsive modal dialogs
- Custom terminal CSS theme (~600 lines)
- Tab-based navigation
- Keyboard-friendly command input

### Enhanced

**Documentation**
- Added `docs/WEB_UI.md` - Complete web UI user guide
- Reorganized architecture docs into `docs/architecture/` directory
  - Moved `docs/architecture.md` → `docs/architecture/README.md`
  - Added `docs/architecture/web-ui-design.md` - Technical architecture
- Added `docs/WEB_UI_IMPLEMENTATION.md` - Implementation summary
- Updated `README.md` with Web UI section and simplified Quick Start
- Updated `docs/SETUP.md` references

**Setup Process**
- Simplified Quick Start in README to 4 steps
- Moved detailed setup instructions to `docs/SETUP.md`
- Improved setup workflow documentation

### Changed

**API Enhancements**
- Root endpoint (`/`) now includes `web_ui` link
- Static files served at `/web/static`
- Web UI routes at `/web`

**Project Structure**
```
app/web/               # New web UI module
├── routes.py         # FastAPI integration
└── static/
    ├── css/          # Terminal theme styles
    ├── js/           # API client and app logic
    └── index.html    # Single-page application
```

### Security

- All secrets encrypted at rest (AES-256)
- No secret values displayed in UI
- HTML escaping for user inputs
- CORS properly configured
- No authentication yet (MVP - admin-only access)

### Performance

- Bundle size: ~37 KB uncompressed
- Load time: < 100ms
- No external dependencies
- Efficient DOM updates

## [0.1.0] - 2025-01-22

### Added - Initial Release

**Core Functionality**
- Polling orchestration system for asynchronous jobs
- OpenAI batch job monitoring
- Keboola workflow triggering on completion
- Secure secrets management with AES-256 encryption

**REST API**
- Full-featured FastAPI backend
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- Health and statistics endpoints
- CRUD operations for secrets and jobs

**CLI Interface**
- Rich CLI with Typer framework
- Color-coded output
- Interactive setup wizard
- Commands for secrets, jobs, and system management
- ASCII art branding

**Polling Engine**
- Asyncio-based concurrent job processing
- Configurable polling intervals (30s - 1 hour)
- Exponential backoff retry logic
- Graceful shutdown handling
- Semaphore-based rate limiting (max 10 concurrent)

**Architecture**
- Layered architecture (Interface → Service → Integration → Data)
- SQLAlchemy 2.0 with modern syntax
- SQLite database (PostgreSQL-ready)
- Singleton encryption service
- Client caching for API efficiency

**Documentation**
- Comprehensive PRD (`docs/prd.md`)
- Setup guide (`docs/SETUP.md`)
- User guide (`docs/USER_GUIDE.md`)
- Architecture documentation (`docs/architecture/`)

**Development**
- Virtual environment setup
- Makefile for common tasks
- Testing framework with pytest
- Code formatting with Black
- Linting with Ruff

### Technical Details

**Dependencies**
- Python 3.11+
- FastAPI 0.109.0+
- SQLAlchemy 2.0.25+
- Typer 0.9.0+
- OpenAI 1.10.0+
- Cryptography 42.0.0+

**Database Schema**
- `secrets` - Encrypted credentials storage
- `polling_jobs` - Job configuration and state
- `polling_logs` - Event logging

---

## Release Notes

### What's New in 0.9.0?

This release adds a **complete web-based administration interface** that provides an alternative to the CLI for managing TeckoChecker. The Web UI features a unique terminal/hacker aesthetic with green-on-black theme, ASCII art, and glowing effects that match the CLI experience.

**Key Highlights:**
- 🎨 Beautiful terminal-style interface
- 🔐 Secure secrets management
- 📋 Interactive jobs dashboard
- 📊 Real-time monitoring
- 📜 Live log viewer
- ⚡ Zero build process - just works!

**Access the Web UI:**
```bash
python teckochecker.py start
open http://127.0.0.1:8000/web
```

### Upgrade Instructions

If upgrading from 0.1.0:

1. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

2. **No database migration needed** - Schema unchanged

3. **No breaking changes** - All CLI commands work as before

4. **Start using Web UI:**
   ```bash
   python teckochecker.py start
   # Open http://127.0.0.1:8000/web in browser
   ```

### Known Limitations

- No authentication yet (admin-only access)
- No WebSocket support (polling for updates)
- Desktop-first design (not mobile-optimized)
- No pagination for large datasets (< 100 jobs recommended)

### Coming in 1.0.0

- Multi-user authentication
- WebSocket for real-time updates
- Job history charts
- Export functionality (CSV/JSON)
- Mobile-responsive design
- Advanced filtering and search

---

**For detailed information, see:**
- [Release Notes v0.9.0](docs/RELEASE_NOTES_v0.9.0.md)
- [Web UI Documentation](docs/WEB_UI.md)
- [Setup Guide](docs/SETUP.md)
- [User Guide](docs/USER_GUIDE.md)
- [Architecture](docs/architecture/)