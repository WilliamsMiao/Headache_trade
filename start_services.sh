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
pkill -f "dashboard/app.py" 2>/dev/null || true
pkill -f "dashboard/app.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

start_backend() {
  echo "🚀 Starting Flask backend on port ${BACKEND_PORT}..."
  nohup "$PY_BIN" -m dashboard > "$BACKEND_LOG" 2>&1 &
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

echo ""
echo "🎉 Services started successfully!"
echo ""
echo "========================================"
echo "📍 本地访问地址 (Local):"
echo "   后端API: http://127.0.0.1:${BACKEND_PORT}"
echo "   前端界面: http://127.0.0.1:${FRONTEND_PORT}"
echo ""
echo "🌍 公网访问地址 (Public):"
echo "   查询公网IP: curl ifconfig.me"
echo "   后端API: http://<你的服务器IP>:${BACKEND_PORT}"
echo "   前端界面: http://<你的服务器IP>:${FRONTEND_PORT}"
echo ""
echo "📋 日志文件位置:"
echo "   后端日志: $BACKEND_LOG"
echo "   前端日志: $FRONTEND_LOG"
echo ""
echo "🔧 查看日志:"
echo "   后端: tail -f $BACKEND_LOG"
echo "   前端: tail -f $FRONTEND_LOG"
echo ""
echo "⚠️  故障排查:"
echo "   1. 检查端口是否被占用: netstat -tlnp | grep -E '(3000|5001)'"
echo "   2. 检查防火墙/安全组是否允许这些端口"
echo "   3. 检查 Next.js 是否正确启动: ps aux | grep 'next dev'"
echo "========================================"
echo ""
