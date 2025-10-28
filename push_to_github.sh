#!/bin/bash

# ============================================
# GitHub 推送辅助脚本
# ============================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 GitHub 推送辅助脚本"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd /root/crypto_deepseek || exit 1

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  发现未提交的更改！"
    echo ""
    git status --short
    echo ""
    read -p "是否先提交这些更改? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "请输入提交信息:"
        read commit_msg
        git add .
        git commit -m "$commit_msg"
        echo "✓ 更改已提交"
    fi
fi

echo ""
echo "请选择推送方式:"
echo ""
echo "1) 使用 Personal Access Token (推荐)"
echo "2) 使用 SSH 密钥"
echo "3) 查看详细帮助"
echo "4) 退出"
echo ""
read -p "请选择 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "使用 Personal Access Token"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "📌 步骤1: 获取 Token"
        echo "   访问: https://github.com/settings/tokens"
        echo "   生成 token (classic)，勾选 'repo' 权限"
        echo ""
        read -p "已获取token? 按回车继续..." 
        echo ""
        echo "📌 步骤2: 输入你的 Personal Access Token"
        echo "   (输入时不会显示，这是正常的)"
        echo ""
        read -sp "Token: " github_token
        echo ""
        echo ""
        
        if [ -z "$github_token" ]; then
            echo "❌ Token不能为空"
            exit 1
        fi
        
        echo "🔄 正在推送到 GitHub..."
        echo ""
        
        # 临时设置带token的URL
        git remote set-url origin "https://${github_token}@github.com/WilliamsMiao/Headache_trade.git"
        
        # 推送
        if git push -u origin main; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "✅ 推送成功！"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "🎉 你的项目已成功上传到 GitHub！"
            echo ""
            echo "📍 仓库地址:"
            echo "   https://github.com/WilliamsMiao/Headache_trade"
            echo ""
        else
            echo ""
            echo "❌ 推送失败！请检查:"
            echo "   - Token是否正确"
            echo "   - Token是否有 repo 权限"
            echo "   - 仓库是否存在"
            exit 1
        fi
        
        # 恢复原URL（安全考虑）
        git remote set-url origin "https://github.com/WilliamsMiao/Headache_trade.git"
        echo "🔒 已清除临时凭证"
        ;;
        
    2)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "使用 SSH 密钥"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # 检查SSH密钥
        if [ ! -f ~/.ssh/id_ed25519 ] && [ ! -f ~/.ssh/id_rsa ]; then
            echo "📌 未找到SSH密钥，正在生成..."
            ssh-keygen -t ed25519 -C "github@crypto_deepseek" -f ~/.ssh/id_ed25519 -N ""
            echo "✓ SSH密钥已生成"
        fi
        
        echo ""
        echo "📌 你的SSH公钥:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -f ~/.ssh/id_ed25519.pub ]; then
            cat ~/.ssh/id_ed25519.pub
        else
            cat ~/.ssh/id_rsa.pub
        fi
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "请将上面的公钥添加到 GitHub:"
        echo "1. 访问: https://github.com/settings/keys"
        echo "2. 点击 'New SSH key'"
        echo "3. 粘贴上面的公钥"
        echo "4. 保存"
        echo ""
        read -p "已添加SSH密钥? 按回车继续..." 
        
        # 更改为SSH URL
        git remote set-url origin "git@github.com:WilliamsMiao/Headache_trade.git"
        
        echo ""
        echo "🔄 正在推送到 GitHub..."
        echo ""
        
        if git push -u origin main; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "✅ 推送成功！"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "🎉 你的项目已成功上传到 GitHub！"
            echo ""
            echo "📍 仓库地址:"
            echo "   https://github.com/WilliamsMiao/Headache_trade"
            echo ""
        else
            echo ""
            echo "❌ 推送失败！请检查SSH密钥是否正确添加到GitHub"
            exit 1
        fi
        ;;
        
    3)
        echo ""
        cat GITHUB_PUSH_GUIDE.md
        ;;
        
    4)
        echo "退出"
        exit 0
        ;;
        
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎊 完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

