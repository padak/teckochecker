# Release Guide for v0.9.0

This guide will help you release TeckoChecker v0.9.0.

## Pre-Release Checklist

✅ Version numbers updated:
- [x] `pyproject.toml` → 0.9.0
- [x] `app/config.py` → 0.9.0

✅ Documentation created:
- [x] `CHANGELOG.md`
- [x] `docs/RELEASE_NOTES_v0.9.0.md`
- [x] `scripts/RELEASE_v0.9.0.sh`

✅ Code ready:
- [x] All features implemented
- [x] Web UI tested and working
- [x] Documentation complete

## Release Steps

### Option 1: Using Release Script (Recommended)

```bash
# Make script executable
chmod +x scripts/RELEASE_v0.9.0.sh

# Run release script
./scripts/RELEASE_v0.9.0.sh

# Follow on-screen instructions
```

The script will:
1. Check git status
2. Stage all changes
3. Create commit with detailed message
4. Create git tag v0.9.0
5. Show next steps

### Option 2: Manual Release

#### Step 1: Review Changes

```bash
# Check what will be committed
git status

# View changes
git diff
```

#### Step 2: Commit Changes

```bash
# Stage all changes
git add .

# Create commit
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
```

#### Step 3: Create Tag

```bash
# Create annotated tag
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
```

#### Step 4: Push to Remote

```bash
# Push commit
git push origin main

# Push tag
git push origin v0.9.0

# Or push everything at once
git push origin main --tags
```

#### Step 5: Create GitHub Release (Optional)

If you have GitHub CLI installed:

```bash
gh release create v0.9.0 \
  --title "TeckoChecker v0.9.0 - Terminal UI" \
  --notes-file RELEASE_NOTES_v0.9.0.md
```

Or create release manually on GitHub:
1. Go to: https://github.com/padak/teckochecker/releases/new
2. Select tag: `v0.9.0`
3. Title: `TeckoChecker v0.9.0 - Terminal UI`
4. Copy content from `RELEASE_NOTES_v0.9.0.md`
5. Click "Publish release"

## Post-Release Tasks

### 1. Verify Release

```bash
# Check tag exists
git tag -l v0.9.0

# View tag details
git show v0.9.0

# Verify on GitHub
open https://github.com/padak/teckochecker/releases
```

### 2. Test Installation

```bash
# Clone fresh copy
cd /tmp
git clone https://github.com/padak/teckochecker.git test-install
cd test-install

# Checkout release tag
git checkout v0.9.0

# Setup and test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python teckochecker.py setup
python teckochecker.py start

# Test Web UI
open http://127.0.0.1:8000/web
```

### 3. Update Documentation

If you have a docs site or wiki:
- Update installation instructions
- Add Web UI screenshots
- Update feature list
- Link to release notes

### 4. Announce Release

Consider announcing on:
- GitHub Discussions
- Project README
- Team communication channels
- Social media (if applicable)

**Example Announcement:**

```
🎉 TeckoChecker v0.9.0 is now available!

This release introduces a complete web-based administration
interface with a unique terminal/hacker aesthetic.

Key highlights:
🔐 Secrets management UI
📋 Interactive jobs dashboard
📊 Real-time monitoring
📜 Live log viewer

Get started:
https://github.com/padak/teckochecker

Release notes:
https://github.com/padak/teckochecker/releases/tag/v0.9.0
```

## Rollback (If Needed)

If something goes wrong:

```bash
# Delete local tag
git tag -d v0.9.0

# Delete remote tag (if pushed)
git push origin :refs/tags/v0.9.0

# Revert commit (if needed)
git revert HEAD

# Or hard reset (be careful!)
git reset --hard HEAD~1
```

## Troubleshooting

### Issue: "Tag already exists"

```bash
# Delete existing tag
git tag -d v0.9.0
git push origin :refs/tags/v0.9.0

# Recreate tag
git tag -a v0.9.0 -m "Version 0.9.0"
```

### Issue: "Nothing to commit"

```bash
# Check if files are staged
git status

# Add files if needed
git add .
```

### Issue: "Permission denied"

```bash
# Make script executable
chmod +x scripts/RELEASE_v0.9.0.sh
```

## Files Included in Release

### New Files (11)
```
✅ app/web/__init__.py
✅ app/web/routes.py
✅ app/web/static/index.html
✅ app/web/static/css/terminal.css
✅ app/web/static/js/api.js
✅ app/web/static/js/app.js
✅ docs/WEB_UI.md
✅ docs/architecture/web-ui-design.md
✅ docs/WEB_UI_IMPLEMENTATION.md
✅ CHANGELOG.md
✅ RELEASE_NOTES_v0.9.0.md
```

### Modified Files (3)
```
✅ app/main.py (web router integration)
✅ app/config.py (version update)
✅ README.md (Web UI section, simplified Quick Start)
✅ pyproject.toml (version update)
```

## Version History

- **v0.9.0** (2025-01-22) - Terminal UI release
- **v0.1.0** (2025-01-22) - Initial release

---

**Ready to release? Run the script or follow the manual steps above!**

```bash
chmod +x scripts/RELEASE_v0.9.0.sh
./scripts/RELEASE_v0.9.0.sh
```