#!/bin/bash

# 前端访问问题诊断和修复脚本

echo "🔍 Next.js 前端访问问题诊断..."
echo "=========================================="
echo ""

# 1. 检查 Node.js
echo "1️⃣  检查 Node.js:"
if command -v node > /dev/null; then
    echo "   ✅ Node.js 已安装: $(node --version)"
    echo "   ✅ npm 已安装: $(npm --version)"
else
    echo "   ❌ Node.js 未安装！"
    echo "   📦 安装 Node.js:"
    echo "   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
    echo "   sudo apt-get install -y nodejs"
    exit 1
fi

echo ""

# 2. 检查前端依赖
echo "2️⃣  检查前端依赖:"
if [ -d "frontend_dashboard/node_modules" ]; then
    echo "   ✅ node_modules 目录存在"
    if [ -f "frontend_dashboard/node_modules/.bin/next" ]; then
        echo "   ✅ Next.js 已安装"
    else
        echo "   ⚠️  node_modules 不完整，需要重新安装"
        echo "   运行: cd frontend_dashboard && npm install && cd .."
    fi
else
    echo "   ❌ node_modules 目录不存在，需要安装"
    echo "   运行: cd frontend_dashboard && npm install && cd .."
    exit 1
fi

echo ""

# 3. 检查 Next.js 配置
echo "3️⃣  检查 Next.js 配置:"
if [ -f "frontend_dashboard/next.config.mjs" ]; then
    echo "   ✅ next.config.mjs 存在"
else
    echo "   ⚠️  next.config.mjs 不存在"
fi

if [ -f "frontend_dashboard/package.json" ]; then
    echo "   ✅ package.json 存在"
    if grep -q '"next"' frontend_dashboard/package.json; then
        echo "   ✅ Next.js 在 package.json 中"
    fi
else
    echo "   ❌ package.json 不存在"
fi

echo ""

# 4. 检查端口占用
echo "4️⃣  检查端口状态:"
if command -v netstat > /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -q ":3000"; then
        echo "   ✅ 端口 3000 正在监听"
        netstat -tlnp 2>/dev/null | grep ":3000"
    else
        echo "   ❌ 端口 3000 未监听 (前端未运行)"
    fi
    
    if netstat -tlnp 2>/dev/null | grep -q ":5001"; then
        echo "   ✅ 端口 5001 正在监听"
    else
        echo "   ❌ 端口 5001 未监听 (后端未运行)"
    fi
elif command -v lsof > /dev/null; then
    if lsof -i :3000 > /dev/null 2>&1; then
        echo "   ✅ 端口 3000 正在监听"
        lsof -i :3000
    else
        echo "   ❌ 端口 3000 未监听"
    fi
    
    if lsof -i :5001 > /dev/null 2>&1; then
        echo "   ✅ 端口 5001 正在监听"
    else
        echo "   ❌ 端口 5001 未监听"
    fi
fi

echo ""

# 5. 检查防火墙
echo "5️⃣  检查防火墙状态:"
if command -v ufw > /dev/null; then
    if sudo ufw status 2>/dev/null | grep -q "inactive"; then
        echo "   ℹ️  UFW 防火墙已禁用"
    else
        echo "   ⚠️  UFW 防火墙已启用，检查规则..."
        if sudo ufw status numbered 2>/dev/null | grep -q "3000"; then
            echo "   ✅ 端口 3000 在防火墙中已允许"
        else
            echo "   ❌ 端口 3000 未在防火墙中允许"
            echo "   修复: sudo ufw allow 3000/tcp"
        fi
        
        if sudo ufw status numbered 2>/dev/null | grep -q "5001"; then
            echo "   ✅ 端口 5001 在防火墙中已允许"
        else
            echo "   ❌ 端口 5001 未在防火墙中允许"
            echo "   修复: sudo ufw allow 5001/tcp"
        fi
    fi
else
    echo "   ℹ️  未检测到 ufw，检查 iptables..."
    if command -v iptables > /dev/null; then
        if sudo iptables -L -n 2>/dev/null | grep -q "3000"; then
            echo "   ✅ 端口 3000 可能已允许"
        else
            echo "   ⚠️  无法确认端口 3000 是否允许"
        fi
    fi
fi

echo ""

# 6. 检查网络连接
echo "6️⃣  检查网络连接:"
if curl -s http://127.0.0.1:3000 > /dev/null 2>&1; then
    echo "   ✅ 本地连接正常 (http://127.0.0.1:3000)"
else
    echo "   ❌ 本地连接失败 (http://127.0.0.1:3000)"
fi

if curl -s http://127.0.0.1:5001 > /dev/null 2>&1; then
    echo "   ✅ 本地连接正常 (http://127.0.0.1:5001)"
else
    echo "   ❌ 本地连接失败 (http://127.0.0.1:5001)"
fi

echo ""

# 7. 显示当前进程
echo "7️⃣  运行中的进程:"
if pgrep -f "next dev" > /dev/null; then
    echo "   ✅ Next.js 开发服务器正在运行"
else
    echo "   ❌ Next.js 开发服务器未运行"
fi

if pgrep -f "trading_dashboard.py" > /dev/null; then
    echo "   ✅ Flask 后端服务正在运行"
else
    echo "   ❌ Flask 后端服务未运行"
fi

echo ""

# 8. 显示公网 IP
echo "8️⃣  公网访问信息:"
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")
echo "   📍 服务器公网 IP: $SERVER_IP"
echo "   🌐 前端访问地址: http://$SERVER_IP:3000"
echo "   🌐 后端访问地址: http://$SERVER_IP:5001"

echo ""
echo "=========================================="
echo ""
echo "✨ 问题排查完成！"
echo ""
echo "🔧 常见解决方案:"
echo "   1. 如果 Node.js 未安装，执行上面的安装命令"
echo "   2. 如果 node_modules 不完整:"
echo "      cd frontend_dashboard && npm install && cd .."
echo "   3. 如果 3000/5001 端口未开放:"
echo "      sudo ufw allow 3000/tcp"
echo "      sudo ufw allow 5001/tcp"
echo "   4. 如果服务未运行:"
echo "      ./start_services.sh"
echo "   5. 查看完整日志:"
echo "      tail -f logs/frontend.log"
echo "      tail -f logs/dashboard.log"
echo ""
