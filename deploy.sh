#!/bin/bash

# ============================================
# Crypto DeepSeek 交易系统一键部署脚本
# ============================================

echo "🚀 Crypto DeepSeek 交易系统 - 一键部署"
echo "========================================"

# 检查是否在正确的目录
if [ ! -f "requirements.txt" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    echo "   当前目录: $(pwd)"
    echo "   请切换到包含 requirements.txt 的目录"
    exit 1
fi

PROJECT_DIR=$(pwd)
echo "✓ 项目目录: $PROJECT_DIR"

# 检查 Python3 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3"
    echo "   请先安装 Python3: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

echo "✓ Python3 版本: $(python3 --version)"

# 删除旧的虚拟环境
echo ""
echo "🧹 清理旧的虚拟环境..."
if [ -d "myenv" ]; then
    echo "   删除 myenv 目录..."
    rm -rf myenv
fi

if [ -d "venv" ]; then
    echo "   删除 venv 目录..."
    rm -rf venv
fi

echo "✓ 旧虚拟环境已清理"

# 创建新的虚拟环境
echo ""
echo "📦 创建新的虚拟环境..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ 创建虚拟环境失败"
    exit 1
fi

echo "✓ 虚拟环境创建成功"

# 激活虚拟环境
echo ""
echo "🔧 激活虚拟环境并安装依赖..."
source venv/bin/activate

# 升级 pip
echo "   升级 pip..."
pip install --upgrade pip -q

# 安装依赖
echo "   安装项目依赖..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    echo "   请检查 requirements.txt 文件"
    exit 1
fi

echo "✓ 依赖安装完成"

# 创建必要的目录
echo ""
echo "📁 创建必要的目录..."
mkdir -p data logs static/css static/js templates

echo "✓ 目录创建完成"

# 检查 .env 文件
echo ""
echo "🔐 检查环境配置文件..."
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 配置文件"
    echo ""
    echo "📋 请按以下步骤配置:"
    echo "   1. 复制配置模板: cp .env.example .env"
    echo "   2. 编辑配置文件: nano .env"
    echo "   3. 填写你的 API 密钥:"
    echo "      - DEEPSEEK_API_KEY (从 https://platform.deepseek.com/ 获取)"
    echo "      - OKX_API_KEY (从 https://www.okx.com/account/my-api 获取)"
    echo "      - OKX_SECRET"
    echo "      - OKX_PASSWORD"
    echo ""
    echo "💡 配置完成后，运行 ./run.sh 启动系统"
else
    echo "✓ 找到 .env 配置文件"
    
    # 简单验证配置
    if grep -q "DEEPSEEK_API_KEY=sk-" .env && grep -q "OKX_API_KEY=" .env; then
        echo "✓ API 密钥配置检查通过"
    else
        echo "⚠️  警告: .env 文件中的 API 密钥可能未正确配置"
        echo "   请确保已填写所有必需的 API 密钥"
    fi
fi

# 验证安装
echo ""
echo "🔍 验证安装..."
python -c "
import sys
try:
    import ccxt, openai, flask, pandas, schedule
    print('✓ 所有依赖包导入成功')
except ImportError as e:
    print(f'❌ 依赖包导入失败: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 部署完成！"
    echo "========================================"
    echo ""
    echo "📋 下一步操作:"
    echo "   1. 配置 API 密钥: nano .env"
    echo "   2. 启动系统: ./run.sh"
    echo ""
    echo "🌐 启动后访问地址:"
    echo "   本地: http://localhost:5000"
    echo "   外网: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):5000"
    echo ""
    echo "📚 更多信息请查看 README.md"
else
    echo "❌ 部署验证失败"
    exit 1
fi

