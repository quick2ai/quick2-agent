#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "======================================"
echo "  Quick2 Purchase Router"
echo "  Smart purchase routing agent"
echo "======================================"
echo ""
PORT="${PORT:-5000}"
echo "  http://localhost:$PORT"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"
