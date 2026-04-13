#!/bin/bash
set -e

cd "$(dirname "$0")"

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo ">>> .env created from .env.example"
    echo ">>> Set your ANTHROPIC_API_KEY in .env for live Claude responses."
    echo ">>> Running in MOCK MODE until then."
    echo ""
fi

echo ""
echo "==================================="
echo "  AI Mastery Diagnostic Engine"
echo "  Quick2Labs — Levi Webster"
echo "==================================="
echo ""
PORT="${PORT:-5150}"
echo "  Starting at http://localhost:$PORT"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"
