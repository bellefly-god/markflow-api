#!/bin/bash
# Quick start script for MarkFlow API

set -e

echo "🚀 MarkFlow API Setup"
echo "====================="

# Check Python version
PYTHON_CMD=""
for py in python3.11 python3.10 python3.12 python3; do
    if command -v $py &> /dev/null; then
        PYTHON_VERSION=$($py --version 2>&1 | awk '{print $2}')
        if [[ $(echo "$PYTHON_VERSION >= 3.10" | bc -l 2>/dev/null || echo 0) == 1 ]] || \
           [[ "${PYTHON_VERSION:0:4}" == "3.10" ]] || [[ "${PYTHON_VERSION:0:4}" == "3.11" ]] || [[ "${PYTHON_VERSION:0:4}" == "3.12" ]]; then
            PYTHON_CMD=$py
            break
        fi
    fi
done

# Fallback for known Python paths
if [ -z "$PYTHON_CMD" ]; then
    if [ -f "$HOME/.local/bin/python3.11" ]; then
        PYTHON_CMD="$HOME/.local/bin/python3.11"
    elif [ -f "/usr/local/bin/python3.11" ]; then
        PYTHON_CMD="/usr/local/bin/python3.11"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10+ is required. Please install from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENAI_API_KEY"
fi

# Create uploads directory
mkdir -p uploads

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Or with Docker:"
echo "  docker-compose up -d"
echo ""
echo "API will be available at: http://localhost:8000"
echo "Docs at: http://localhost:8000/v1/docs"
