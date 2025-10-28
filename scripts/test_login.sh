#!/bin/bash

# Alpha Arena 登录测试脚本

echo "🔐 测试 Alpha Arena 登录功能..."
echo "=" * 50

# 检查服务状态
echo "📊 检查服务状态:"
if curl -s http://localhost:5000 > /dev/null; then
    echo "✅ 服务正常运行"
else
    echo "❌ 服务未运行"
    exit 1
fi

echo ""

# 测试登录页面
echo "🔍 测试登录页面:"
if curl -s http://localhost:5000 | grep -q "Alpha Arena"; then
    echo "✅ 登录页面正常"
else
    echo "❌ 登录页面异常"
fi

echo ""

# 测试 API 接口（未登录状态）
echo "🔒 测试 API 接口（未登录）:"
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/dashboard)
if [ "$response" = "401" ]; then
    echo "✅ API 正确返回 401 未授权"
else
    echo "❌ API 返回异常: $response"
fi

echo ""

# 显示访问信息
echo "🌐 访问信息:"
echo "本地访问: http://localhost:5000"
echo "外网访问: http://8.217.194.162:5000"
echo ""

echo "📋 使用说明:"
echo "1. 访问登录页面"
echo "2. 填写您的 API 配置:"
echo "   - DeepSeek API Key"
echo "   - OKX API Key"
echo "   - OKX Secret"
echo "   - OKX Password"
echo "   - 钱包地址（可选）"
echo "3. 点击'连接并进入 Arena'"
echo "4. 验证成功后自动跳转到交易仪表板"
echo ""

echo "⚠️  注意事项:"
echo "- 请确保您的 API 密钥正确且有相应权限"
echo "- 首次连接可能需要几秒钟验证"
echo "- 如果验证失败，请检查 API 配置"
echo ""

echo "🎯 测试完成！"
