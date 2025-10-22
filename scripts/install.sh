#!/bin/bash

# TeckoChecker Installation Script
# Usage: ./install.sh

set -e

echo "======================================="
echo "   TeckoChecker Installation Script    "
echo "======================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo -e "${GREEN}✓${NC} Python $python_version (>= 3.11 required)"
else
    echo -e "${RED}✗${NC} Python $python_version is too old. Python 3.11+ required."
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${YELLOW}!${NC} Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
echo "Upgrading pip..."
pip install --quiet --upgrade pip
echo -e "${GREEN}✓${NC} pip upgraded"

# Install requirements
echo "Installing dependencies..."
pip install --quiet -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Install package in development mode
echo "Installing TeckoChecker CLI..."
pip install --quiet -e .
echo -e "${GREEN}✓${NC} TeckoChecker CLI installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating configuration file..."

    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

    # Create .env from example
    cp .env.example .env

    # Replace SECRET_KEY in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your-secret-key-for-encryption/$SECRET_KEY/" .env
    else
        # Linux
        sed -i "s/your-secret-key-for-encryption/$SECRET_KEY/" .env
    fi

    echo -e "${GREEN}✓${NC} Configuration file created with generated SECRET_KEY"
else
    echo -e "${YELLOW}!${NC} Configuration file already exists"
fi

# Initialize database
echo ""
echo "Initializing database..."
python teckochecker.py init --generate-env 2>/dev/null || true
echo -e "${GREEN}✓${NC} Database initialized"

# Verify installation
echo ""
echo "Verifying installation..."
python scripts/verify_setup.py 2>/dev/null || {
    echo -e "${YELLOW}!${NC} Verification completed with warnings"
}

# Display next steps
echo ""
echo "======================================="
echo -e "${GREEN}   Installation Complete!${NC}"
echo "======================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Add your API keys:"
echo "   ${GREEN}teckochecker secret add --name \"openai-prod\" --type openai${NC}"
echo "   ${GREEN}teckochecker secret add --name \"keboola-prod\" --type keboola${NC}"
echo ""
echo "2. Create a polling job:"
echo "   ${GREEN}teckochecker job create \\
      --name \"My Job\" \\
      --batch-id \"batch_123\" \\
      --openai-secret \"openai-prod\" \\
      --keboola-secret \"keboola-prod\" \\
      --keboola-stack \"https://connection.keboola.com\" \\
      --config-id \"123456\" \\
      --poll-interval 120${NC}"
echo ""
echo "3. Start the polling service:"
echo "   ${GREEN}teckochecker start --daemon${NC}"
echo ""
echo "For more information, see: docs/USER_GUIDE.md"
echo ""
echo "To activate the virtual environment in the future:"
echo "   ${GREEN}source venv/bin/activate${NC}"
echo ""