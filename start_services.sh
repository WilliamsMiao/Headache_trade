#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_LOG="$ROOT_DIR/logs/dashboard.log"
FRONTEND_LOG="$ROOT_DIR/logs/frontend.log"
BACKEND_PORT=5001
FRONTEND_PORT=3000

mkdir -p "$ROOT_DIR/logs"

# Choose python: prefer venv if present
if [[ -d "$ROOT_DIR/venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/venv/bin/activate"
  PY_BIN="python"
else
  PY_BIN="python3"
fi

echo "🔄 Stopping existing services..."
pkill -f "trading_dashboard.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

start_backend() {
  echo "🚀 Starting Flask backend on port ${BACKEND_PORT}..."
  nohup "$PY_BIN" "$ROOT_DIR/trading_dashboard.py" > "$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  for _ in {1..30}; do
    if nc -z 127.0.0.1 "$BACKEND_PORT" 2>/dev/null; then
      echo "✅ Backend ready (PID: $BACKEND_PID)"
      return 0
    fi
    sleep 1
  done
  echo "❌ Backend failed to start. Last 20 log lines:"
  tail -n 20 "$BACKEND_LOG" || true
  exit 1
}

start_frontend() {
  echo "🚀 Starting Next dev server on port ${FRONTEND_PORT}..."
  cd "$ROOT_DIR/frontend_dashboard"
  nohup npm run dev -- --hostname 0.0.0.0 --port "$FRONTEND_PORT" > "$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!
  for _ in {1..30}; do
    if nc -z 127.0.0.1 "$FRONTEND_PORT" 2>/dev/null; then
      echo "✅ Frontend ready (PID: $FRONTEND_PID)"
      return 0
    fi
    sleep 1
  done
  echo "❌ Frontend failed to start. Last 20 log lines:"
  tail -n 20 "$FRONTEND_LOG" || true
  exit 1
}

start_backend
start_frontend

echo "\n🎉 Services started"
echo "Backend: http://127.0.0.1:${BACKEND_PORT}  (logs: $BACKEND_LOG)"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT} (logs: $FRONTEND_LOG)"
