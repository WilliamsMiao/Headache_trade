#!/bin/bash

# 交易仪表板状态检查脚本

echo "🔍 检查交易仪表板状态..."
echo "=" * 50

# 检查进程
echo "📊 检查进程状态:"
if pgrep -f "trading_dashboard.py" > /dev/null; then
    echo "✅ 仪表板进程正在运行"
    ps aux | grep trading_dashboard.py | grep -v grep
else
    echo "❌ 仪表板进程未运行"
fi

echo ""

# 检查端口
echo "🌐 检查端口状态:"
if netstat -tlnp | grep :5000 > /dev/null; then
    echo "✅ 端口 5000 正在监听"
    netstat -tlnp | grep :5000
else
    echo "❌ 端口 5000 未监听"
fi

echo ""

# 检查网络连接
echo "🔗 检查网络连接:"
if curl -s http://localhost:5000 > /dev/null; then
    echo "✅ 本地连接正常"
else
    echo "❌ 本地连接失败"
fi

echo ""

# 检查外网访问
echo "🌍 检查外网访问:"
SERVER_IP=$(curl -s ifconfig.me)
echo "服务器 IP: $SERVER_IP"

if curl -s --connect-timeout 5 http://$SERVER_IP:5000 > /dev/null; then
    echo "✅ 外网访问正常"
    echo "🌐 访问地址: http://$SERVER_IP:5000"
else
    echo "❌ 外网访问失败"
    echo "💡 可能需要检查防火墙设置"
fi

echo ""

# 检查环境
echo "🐍 检查 Python 环境:"
if [[ "$CONDA_DEFAULT_ENV" == "crypto_deepseek" ]]; then
    echo "✅ 环境正确: $CONDA_DEFAULT_ENV"
else
    echo "⚠️  当前环境: $CONDA_DEFAULT_ENV"
    echo "💡 建议使用: conda activate crypto_deepseek"
fi

echo ""

# 检查依赖
echo "📦 检查关键依赖:"
python -c "import flask; print('✅ Flask 已安装')" 2>/dev/null || echo "❌ Flask 未安装"
python -c "import ccxt; print('✅ CCXT 已安装')" 2>/dev/null || echo "❌ CCXT 未安装"
python -c "from deepseek_trading_bot import exchange; print('✅ 交易服务导入成功')" 2>/dev/null || echo "❌ 交易服务导入失败"

echo ""
echo "=" * 50
echo "🎯 状态检查完成！"
