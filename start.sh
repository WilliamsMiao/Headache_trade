#!/bin/bash

# ============================================
# Crypto DeepSeek 交易系统一键启动脚本
# ============================================

echo "🚀 正在启动 Crypto DeepSeek 交易系统..."
echo "========================================"

# 切换到项目目录
cd /root/crypto_deepseek || exit 1

# 检查虚拟环境
if [ -d "myenv" ]; then
    VENV_PATH="myenv"
elif [ -d "venv" ]; then
    VENV_PATH="venv"
else
    echo "❌ 未找到虚拟环境目录 (myenv 或 venv)"
    echo "请先创建虚拟环境: python3 -m venv myenv"
    exit 1
fi

echo "✓ 找到虚拟环境: $VENV_PATH"

# 激活虚拟环境
source $VENV_PATH/bin/activate

# 检查依赖
echo ""
echo "📦 检查依赖包..."
if ! python -c "import ccxt, openai, flask" 2>/dev/null; then
    echo "⚠️  缺少依赖包，正在安装..."
    pip install -q -r requirements.txt
    echo "✓ 依赖包安装完成"
else
    echo "✓ 依赖包已安装"
fi

# 检查.env配置文件
echo ""
echo "🔐 检查配置文件..."
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 配置文件"
    echo "请复制 .env.example 并填写你的API密钥:"
    echo "   cp .env.example .env"
    echo "   nano .env"
    exit 1
fi

# 验证必要的环境变量
if ! grep -q "DEEPSEEK_API_KEY=sk-" .env || ! grep -q "OKX_API_KEY=" .env; then
    echo "⚠️  警告: .env 文件中的API密钥可能未配置"
    echo "请确保已正确配置以下内容:"
    echo "  - DEEPSEEK_API_KEY"
    echo "  - OKX_API_KEY"
    echo "  - OKX_SECRET"
    echo "  - OKX_PASSWORD"
    read -p "是否继续启动? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✓ 配置文件检查完成"

# 创建必要的目录
mkdir -p data logs

# 停止旧进程
echo ""
echo "🔄 检查并停止旧进程..."
pkill -f "deepseek_trading_bot.py" 2>/dev/null && echo "✓ 已停止旧的交易机器人进程"
pkill -f "trading_dashboard.py" 2>/dev/null && echo "✓ 已停止旧的仪表板进程"

# 启动交易机器人（后台运行）
echo ""
echo "🤖 启动交易机器人..."
nohup python trading_bots/deepseek_trading_bot.py > logs/bot.log 2>&1 &
BOT_PID=$!
echo "✓ 交易机器人已启动 (PID: $BOT_PID)"
echo "  日志文件: logs/bot.log"

# 等待机器人初始化
sleep 2

# 检查机器人是否正常运行
if ! ps -p $BOT_PID > /dev/null; then
    echo "❌ 交易机器人启动失败，请查看日志: logs/bot.log"
    tail -n 20 logs/bot.log
    exit 1
fi

# 启动交易仪表板（前台运行）
echo ""
echo "📊 启动交易仪表板..."
echo "========================================"
echo ""
echo "✅ 系统启动成功！"
echo ""
echo "📍 访问地址:"
echo "   本地: http://localhost:5000"
echo "   外网: http://$(curl -s ifconfig.me):5000"
echo ""
echo "📂 日志文件:"
echo "   交易机器人: logs/bot.log"
echo "   仪表板: 当前终端"
echo ""
echo "⚠️  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 启动仪表板
python trading_dashboard.py

# 如果仪表板退出，停止机器人
echo ""
echo "🛑 正在停止交易机器人..."
kill $BOT_PID 2>/dev/null
echo "✓ 系统已完全停止"

