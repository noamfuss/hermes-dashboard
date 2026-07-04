#!/usr/bin/env bash
# Start Hermes Token Dashboard
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing backend dependencies..."
cd "$ROOT/backend"
uv pip install -r requirements.txt --quiet 2>/dev/null || uv pip install --system -r requirements.txt --quiet

echo "==> Starting backend (port 8100)..."
cd "$ROOT/backend"
uv run uvicorn main:app --host 0.0.0.0 --port 8100 --reload &
BACKEND_PID=$!

echo "==> Starting frontend (port 8080)..."
cd "$ROOT/frontend"
npx vite --host 0.0.0.0 --port 8080 &
FRONTEND_PID=$!

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Hermes Token Dashboard             ║"
echo "║                                      ║"
echo "║   Frontend: http://localhost:5180    ║"
echo "║   Backend:  http://localhost:8100    ║"
echo "║   API docs: http://localhost:8100/docs ║"
echo "╚══════════════════════════════════════╝"
echo ""

cleanup() {
  echo "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  wait
}
trap cleanup EXIT INT TERM

wait
