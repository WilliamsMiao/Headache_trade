#!/bin/bash

case "$1" in
    start)
        echo "启动DeepSeek交易机器人..."
        pm2 start ecosystem.config.js
        ;;
    stop)
        echo "停止DeepSeek交易机器人..."
        pm2 stop deepseek-trading-bot
        ;;
    restart)
        echo "重启DeepSeek交易机器人..."
        pm2 restart deepseek-trading-bot
        ;;
    status)
        echo "查看DeepSeek交易机器人状态..."
        pm2 status deepseek-trading-bot
        ;;
    logs)
        echo "查看DeepSeek交易机器人日志..."
        pm2 logs deepseek-trading-bot
        ;;
    *)
        echo "使用方法: $0 {start|stop|restart|status|logs}"
        echo "  start   - 启动机器人"
        echo "  stop    - 停止机器人"
        echo "  restart - 重启机器人"
        echo "  status  - 查看状态"
        echo "  logs    - 查看日志"
        exit 1
        ;;
esac
