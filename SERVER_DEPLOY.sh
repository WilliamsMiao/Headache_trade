#!/bin/bash
# 服务器快速部署脚本（复制这些命令到服务器执行）

echo "🚀 开始部署修复..."

# 1. 停止现有服务
echo "1️⃣  停止现有服务..."
pkill -f "trading_dashboard.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

# 2. 拉取最新代码
echo "2️⃣  拉取最新代码..."
cd ~/Headache_trade-1
git pull origin main

# 3. 检查前端依赖
echo "3️⃣  检查前端依赖..."
cd frontend_dashboard
if [ ! -d "node_modules" ]; then
    echo "   📦 安装 npm 依赖..."
    npm install
else
    echo "   ✅ npm 依赖已存在"
fi
cd ..

# 4. 启动服务
echo "4️⃣  启动前后端服务..."
chmod +x scripts/diagnose_frontend.sh
./start_services.sh

echo ""
echo "✅ 部署完成！"
echo ""
echo "接下来检查:"
echo "1. 运行诊断脚本: ./scripts/diagnose_frontend.sh"
echo "2. 在浏览器访问你的服务器公网IP:3000"
