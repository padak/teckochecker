#!/bin/bash

# TeckoChecker API Quick Start Script

set -e

echo "============================================"
echo "TeckoChecker API Quick Start"
echo "============================================"
echo

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    
    if [ ! -f .env.example ]; then
        echo "❌ .env.example not found. Please create one first."
        exit 1
    fi
    
    cp .env.example .env
    
    # Generate a random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Update SECRET_KEY in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    else
        # Linux
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    fi
    
    echo "✓ Created .env with randomly generated SECRET_KEY"
    echo
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo

# Run the API
echo "🚀 Starting TeckoChecker API..."
echo
echo "API will be available at:"
echo "  - Main: http://localhost:8000"
echo "  - Docs: http://localhost:8000/docs"
echo "  - Health: http://localhost:8000/api/health"
echo
echo "Press Ctrl+C to stop the server"
echo "============================================"
echo

python teckochecker.py start --reload
