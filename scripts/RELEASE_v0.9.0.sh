#!/bin/bash
# TeckoChecker v0.9.0 Release Script
# This script will commit all changes and create a release tag

set -e  # Exit on error

echo "🚀 TeckoChecker v0.9.0 Release Script"
echo "======================================"
echo ""

# Check if we're in the right directory
if [ ! -f "teckochecker.py" ]; then
    echo "❌ Error: Must be run from teckochecker project root"
    exit 1
fi

# Check git status
echo "📋 Checking git status..."
git status

echo ""
echo "Files to be committed:"
git status --short

echo ""
read -p "Continue with commit? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted"
    exit 1
fi

# Add all changes
echo ""
echo "📦 Staging changes..."
git add .

# Create commit
echo ""
echo "💾 Creating commit..."
git commit -m "Release v0.9.0: Add terminal-style Web UI

Major Features:
- Complete web-based administration interface at /web
- Terminal/hacker aesthetic matching CLI design
- Secrets management UI with encryption
- Jobs dashboard with real-time status indicators
- Monitoring dashboard with system stats
- Log viewer with auto-refresh and color-coding
- System information panel

Technical:
- Pure HTML/CSS/JavaScript (~1,590 lines)
- FastAPI static file serving
- No build process required
- ~37 KB bundle size, <100ms load time

Documentation:
- Added docs/WEB_UI.md
- Added docs/architecture/web-ui-design.md
- Added docs/WEB_UI_IMPLEMENTATION.md
- Updated README.md with simplified Quick Start
- Added CHANGELOG.md
- Added RELEASE_NOTES_v0.9.0.md

Version: 0.1.0 → 0.9.0"

# Create tag
echo ""
echo "🏷️  Creating git tag v0.9.0..."
git tag -a v0.9.0 -m "Version 0.9.0 - Terminal UI

Complete web-based administration interface with terminal/hacker aesthetic.

Key Features:
- Web UI at /web
- Secrets management
- Jobs dashboard
- Real-time monitoring
- Log viewer
- System information

See RELEASE_NOTES_v0.9.0.md for details."

echo ""
echo "✅ Release v0.9.0 prepared!"
echo ""
echo "Next steps:"
echo "  1. Review commit: git show HEAD"
echo "  2. Push to remote: git push origin main"
echo "  3. Push tag: git push origin v0.9.0"
echo ""
echo "Or push everything at once:"
echo "  git push origin main --tags"
echo ""
echo "To create GitHub release:"
echo "  gh release create v0.9.0 --title \"TeckoChecker v0.9.0 - Terminal UI\" --notes-file RELEASE_NOTES_v0.9.0.md"
echo ""