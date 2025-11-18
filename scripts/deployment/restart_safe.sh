#!/bin/bash

# ============================================
# 安全重启 TradingBot 脚本
# 在两次交易执行之间安全重启
# ============================================

echo "🔄 安全重启 TradingBot..."
echo "========================================"

# 获取当前分钟数
current_minute=$(date "+%M")
minute_in_period=$((current_minute % 15))

# 判断是否在安全窗口（执行后5分钟内，即 00-05, 15-20, 30-35, 45-50）
if [ $minute_in_period -ge 0 ] && [ $minute_in_period -le 5 ]; then
    echo "✅ 当前在安全重启窗口内（执行后5分钟内）"
    echo "   距离下次执行还有: $((15 - minute_in_period)) 分钟"
else
    echo "⚠️  警告: 当前不在最佳重启窗口"
    echo "   建议在每次执行后的前5分钟内重启（00-05, 15-20, 30-35, 45-50）"
    echo "   当前时间: $(date '+%H:%M')"
    echo "   距离下次执行还有: $((15 - minute_in_period)) 分钟"
    read -p "是否继续重启? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消重启"
        exit 0
    fi
fi

echo ""
echo "📋 重启前检查..."
echo "========================================"

# 检查PM2进程
pm2 list | grep crypto-trading-bot

# 保存当前日志
echo ""
echo "💾 保存当前日志..."
log_file="/root/crypto_deepseek/logs/bot.log"
if [ -f "$log_file" ]; then
    backup_file="/root/crypto_deepseek/logs/bot_$(date +%Y%m%d_%H%M%S).log"
    cp "$log_file" "$backup_file"
    echo "✅ 日志已备份到: $backup_file"
fi

# 重启PM2进程
echo ""
echo "🔄 重启 trading bot..."
pm2 restart crypto-trading-bot

# 等待几秒检查状态
sleep 3

# 检查重启状态
echo ""
echo "📊 检查重启状态..."
pm2 status crypto-trading-bot

# 显示最新日志
echo ""
echo "📋 最新日志（最后20行）..."
echo "========================================"
pm2 logs crypto-trading-bot --lines 20 --nostream

echo ""
echo "✅ 重启完成！"
echo "========================================"
echo "💡 提示:"
echo "   - 查看实时日志: pm2 logs crypto-trading-bot"
echo "   - 查看完整日志: tail -f logs/bot.log"
echo "   - 检查状态: pm2 status"



