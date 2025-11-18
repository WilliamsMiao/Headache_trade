"""
快速开始脚本
演示如何使用所有新功能
"""

print("\n" + "="*80)
print(" "*20 + "🚀 多策略交易系统 - 快速开始指南")
print("="*80 + "\n")

print("本系统包含以下7大功能:\n")
print("1. ✅ 均值回归策略 - 捕捉超卖超买反弹")
print("2. ✅ 突破策略 - 盘整后的突破行情")
print("3. ✅ 动量策略 - 强势趋势追踪")
print("4. ✅ 回测引擎 - 历史数据验证")
print("5. ✅ 性能监控面板 - 实时指标显示")
print("6. ✅ Web Dashboard - 可视化监控界面")
print("7. ✅ 钉钉机器人 - 移动端推送通知")

print("\n" + "="*80)
print("📋 快速开始步骤")
print("="*80 + "\n")

print("步骤 1: 安装依赖")
print("-" * 80)
print("pip install -r requirements.txt")
print()

print("步骤 2: 配置系统")
print("-" * 80)
print("cp config_full_example.json config.json")
print("# 编辑 config.json，填写:")
print("#   - 交易所 API Key")
print("#   - DeepSeek API Key (可选，用于AI决策)")
print("#   - 钉钉 Webhook (可选，用于通知)")
print()

print("步骤 3: 测试功能")
print("-" * 80)
print("python test_all_features.py")
print()

print("步骤 4: 运行回测")
print("-" * 80)
print("""
# 准备历史数据
import pandas as pd
from backtest_engine import BacktestEngine
from strategies.mean_reversion import MeanReversionStrategy

# 加载数据（CSV格式，包含 timestamp, open, high, low, close, volume）
price_data = pd.read_csv('your_historical_data.csv')

# 创建回测引擎
engine = BacktestEngine(
    initial_capital=10000.0,
    commission_rate=0.001,
    slippage_rate=0.0005
)

# 运行回测
strategy = MeanReversionStrategy()
results = engine.run_backtest(strategy, price_data)

# 导出结果
engine.export_results(results)
""")
print()

print("步骤 5: 启动 Web Dashboard")
print("-" * 80)
print("""
# 方式1: 独立运行
python web_dashboard.py
# 然后访问 http://localhost:5000

# 方式2: 集成到交易机器人
from web_dashboard import DashboardConnector
from monitoring_panel import PerformanceMonitor

monitor = PerformanceMonitor()
dashboard = DashboardConnector(monitor, host='0.0.0.0', port=5000)
dashboard.start()  # 后台运行
""")
print()

print("步骤 6: 配置钉钉通知")
print("-" * 80)
print("""
1. 打开钉钉群 → 群设置 → 智能群助手
2. 添加机器人 → 自定义机器人
3. 安全设置选择"加签"
4. 复制 webhook_url 和 secret
5. 在 config.json 中配置:
   {
       "dingding": {
           "enabled": true,
           "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=...",
           "secret": "SEC..."
       }
   }
6. 测试: python -m dingding_notifier
""")
print()

print("步骤 7: 运行完整系统")
print("-" * 80)
print("""
# 创建主程序（或修改 multi_strategy_bot.py）
import ccxt
import json
from monitoring_panel import PerformanceMonitor
from web_dashboard import DashboardConnector
from dingding_notifier import create_notifier_from_config
from strategy_scheduler import StrategyScheduler

# 导入所有策略
from strategies.grid_strategy import GridStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.momentum import MomentumStrategy

# 加载配置
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 创建交易所
exchange = ccxt.binance({
    'apiKey': config['exchange']['api_key'],
    'secret': config['exchange']['api_secret']
})

# 创建监控器
monitor = PerformanceMonitor()

# 启动 Dashboard
dashboard = DashboardConnector(monitor, port=5000)
dashboard.start()

# 创建钉钉通知器
notifier = create_notifier_from_config(config)
if notifier:
    notifier.notify_system_start()

# 创建调度器（包含AI）
scheduler = StrategyScheduler(
    exchange=exchange,
    symbol=config['trading']['symbol'],
    ai_api_key=config.get('ai', {}).get('deepseek_api_key'),
    use_ai=config.get('ai', {}).get('enabled', False)
)

# 注册所有策略
scheduler.strategy_pool['grid'] = GridStrategy()
scheduler.strategy_pool['trend'] = TrendFollowingStrategy()
scheduler.strategy_pool['mean_reversion'] = MeanReversionStrategy()
scheduler.strategy_pool['breakout'] = BreakoutStrategy()
scheduler.strategy_pool['momentum'] = MomentumStrategy()

print("✅ 系统启动成功!")
print(f"📊 Web面板: http://localhost:5000")
print(f"🤖 启用策略: {len(scheduler.strategy_pool)}")
print(f"🧠 AI辅助: {'✅' if scheduler.use_ai else '❌'}")
print(f"📱 钉钉通知: {'✅' if notifier else '❌'}")

# 主循环...
# (参考 NEW_FEATURES_GUIDE.md 中的完整示例)
""")
print()

print("="*80)
print("📚 详细文档")
print("="*80 + "\n")
print("NEW_FEATURES_GUIDE.md      - 新功能完整使用指南")
print("CHANGELOG.md               - 更新日志")
print("PROJECT_COMPLETION_v2.md   - 项目完成总结")
print("config_full_example.json   - 完整配置示例")
print()

print("="*80)
print("💡 有用的命令")
print("="*80 + "\n")
print("# 测试所有功能")
print("python test_all_features.py")
print()
print("# 启动 Web Dashboard")
print("python web_dashboard.py")
print()
print("# 测试钉钉通知")
print("python -m dingding_notifier")
print()
print("# 查看策略列表")
print("ls trading_bots/strategies/")
print()

print("="*80)
print("❓ 常见问题")
print("="*80 + "\n")

print("Q1: 如何选择合适的策略?")
print("A1: 系统会自动根据市场状态选择:")
print("    - 震荡市场 → 均值回归/网格")
print("    - 盘整突破 → 突破策略")
print("    - 强势趋势 → 动量/趋势跟随")
print()

print("Q2: 回测结果可靠吗?")
print("A2: 回测已考虑手续费(0.1%)和滑点(0.05%)")
print("    但历史表现≠未来收益，建议小资金测试")
print()

print("Q3: Web Dashboard 无法访问?")
print("A3: 检查:")
print("    1. 是否已启动: python web_dashboard.py")
print("    2. 端口是否被占用: netstat -ano | findstr :5000")
print("    3. 防火墙是否放行")
print()

print("Q4: 钉钉消息发送失败?")
print("A4: 检查:")
print("    1. webhook_url 是否正确")
print("    2. secret 是否匹配")
print("    3. 是否超过频率限制(20条/分钟)")
print()

print("="*80)
print("🎯 下一步建议")
print("="*80 + "\n")
print("1. ✅ 运行 test_all_features.py 验证功能")
print("2. ✅ 使用历史数据进行回测")
print("3. ✅ 配置 Web Dashboard 实时监控")
print("4. ✅ 设置钉钉通知接收提醒")
print("5. ✅ 小资金实盘测试")
print("6. ✅ 根据结果优化参数")
print()

print("="*80)
print("⚠️ 风险提示")
print("="*80 + "\n")
print("⚠️ 加密货币交易存在高风险，可能导致本金全部损失")
print("⚠️ 本系统仅供学习研究，不构成投资建议")
print("⚠️ 请务必在充分测试后再使用实盘，建议从小资金开始")
print("⚠️ 设置严格的风控参数（止损、最大回撤、日亏限制等）")
print()

print("="*80)
print("🎉 祝您交易顺利!")
print("="*80 + "\n")

print("如有问题，请参考:")
print("  - NEW_FEATURES_GUIDE.md")
print("  - ARCHITECTURE.md")
print("  - AI_INTEGRATION_GUIDE.md")
print()
print("开始您的量化交易之旅吧！ 🚀\n")
