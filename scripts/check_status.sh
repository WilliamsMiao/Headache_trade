#!/bin/bash

# 交易系统状态检查脚本 (前后端分离架构)

echo "🔍 检查交易系统状态..."
echo "=========================================="

# 检查进程
echo "📊 检查进程状态:"
echo ""

echo "1️⃣ 后端服务 (Flask API):"
if pgrep -f "dashboard/app.py" > /dev/null; then
    echo "   ✅ 后端进程正在运行"
    ps aux | grep "dashboard/app.py" | grep -v grep | head -1
else
    echo "   ❌ 后端进程未运行"
fi

echo ""
echo "2️⃣ 前端服务 (Next.js):"
if pgrep -f "next dev" > /dev/null; then
    echo "   ✅ 前端进程正在运行"
    ps aux | grep "next dev" | grep -v grep | head -1
else
    echo "   ❌ 前端进程未运行"
fi

echo ""
echo "3️⃣ 交易Bot (可选):"
if pgrep -f "main_bot.py" > /dev/null; then
    echo "   ✅ 交易Bot正在运行"
    ps aux | grep main_bot.py | grep -v grep | head -1
else
    echo "   ℹ️  交易Bot未运行 (仅查看数据时不需要)"
fi

echo ""
echo "=========================================="

# 检查端口
echo "🌐 检查端口状态:"
echo ""

if command -v netstat > /dev/null; then
    if netstat -an 2>/dev/null | grep -q ":5001.*LISTEN"; then
        echo "   ✅ 端口 5001 (后端API) 正在监听"
    else
        echo "   ❌ 端口 5001 (后端API) 未监听"
    fi
    
    if netstat -an 2>/dev/null | grep -q ":3000.*LISTEN"; then
        echo "   ✅ 端口 3000 (前端Web) 正在监听"
    else
        echo "   ❌ 端口 3000 (前端Web) 未监听"
    fi
else
    # macOS 使用 lsof
    if lsof -i :5001 > /dev/null 2>&1; then
        echo "   ✅ 端口 5001 (后端API) 正在监听"
    else
        echo "   ❌ 端口 5001 (后端API) 未监听"
    fi
    
    if lsof -i :3000 > /dev/null 2>&1; then
        echo "   ✅ 端口 3000 (前端Web) 正在监听"
    else
        echo "   ❌ 端口 3000 (前端Web) 未监听"
    fi
fi

echo ""
echo "=========================================="

# 检查网络连接
echo "🔗 检查本地连接:"
echo ""

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ 前端 (http://localhost:3000) 连接正常"
else
    echo "   ❌ 前端连接失败"
fi

if curl -s http://localhost:5001/api/health > /dev/null 2>&1; then
    echo "   ✅ 后端 (http://localhost:5001) 连接正常"
else
    echo "   ⚠️  后端连接失败或无健康检查接口"
fi

echo ""
echo "=========================================="

# 检查外网访问
echo "🌍 检查外网访问:"
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "未知")
echo "   服务器 IP: $SERVER_IP"
echo ""

if [ "$SERVER_IP" != "未知" ]; then
    echo "   📱 访问地址:"
    echo "      前端界面: http://$SERVER_IP:3000"
    echo "      后端API:  http://$SERVER_IP:5001"
    echo ""
    echo "   💡 如无法访问，请检查:"
    echo "      1. 防火墙是否开放端口 3000 和 5001"
    echo "      2. 云服务商安全组是否允许这些端口"
fi

echo ""
echo "=========================================="

# 检查环境
echo "🐍 Python 环境:"
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "   ✅ 虚拟环境已激活: $(basename $VIRTUAL_ENV)"
else
    if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
        echo "   ⚠️  Conda 环境: $CONDA_DEFAULT_ENV"
    else
        echo "   ⚠️  使用系统 Python"
    fi
    echo "   💡 建议激活虚拟环境: source venv/bin/activate"
fi

echo ""

# 检查Node.js
echo "📦 Node.js 环境:"
if command -v node > /dev/null; then
    echo "   ✅ Node.js: $(node --version)"
    echo "   ✅ npm: $(npm --version)"
else
    echo "   ❌ Node.js 未安装 (前端需要)"
fi

echo ""
echo "=========================================="

# 快速操作提示
echo "🔧 快速操作:"
echo ""
echo "   启动前后端: ./start_services.sh"
echo "   启动交易Bot: ./run.sh"
echo "   安全重启Bot: ./restart_bot_safe.sh"
echo "   查看后端日志: tail -f logs/dashboard.log"
echo "   查看前端日志: tail -f logs/frontend.log"
echo "   查看Bot日志:  tail -f logs/bot_*.log"
echo ""
echo "=========================================="
echo "✅ 状态检查完成！"
