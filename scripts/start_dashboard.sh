#!/bin/bash

# 交易仪表板启动脚本

echo "🚀 启动交易仪表板..."

# 检查是否在正确的环境中
if [[ "$CONDA_DEFAULT_ENV" != "crypto_deepseek" ]]; then
    echo "⚠️  请先激活 crypto_deepseek 环境:"
    echo "   conda activate crypto_deepseek"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
pip install -r requirements.txt

# 检查环境变量
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 文件，请先配置环境变量"
    exit 1
fi

echo "✅ 环境检查完成"
echo "🌐 启动 Web 仪表板..."
echo "📊 访问地址: http://localhost:5000"
echo "🔄 数据更新频率: 每30秒"
echo ""
echo "按 Ctrl+C 停止服务"

# 启动仪表板
python trading_dashboard.py
