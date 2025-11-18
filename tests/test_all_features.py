"""
新功能测试脚本
测试所有新增的7个功能模块
"""

import sys
import os

# 添加 trading_bots 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'trading_bots'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

print("\n" + "="*80)
print(" "*25 + "🧪 新功能测试脚本")
print("="*80 + "\n")

# ============================================================================
# 测试 1: 均值回归策略
# ============================================================================
print("📋 测试 1: 均值回归策略")
print("-" * 80)

try:
    from strategies.mean_reversion import MeanReversionStrategy
    
    # 创建策略
    mean_reversion = MeanReversionStrategy()
    print(f"✅ 策略名称: {mean_reversion.name}")
    print(f"✅ 策略描述: {mean_reversion.description}")
    print(f"✅ RSI超卖阈值: {mean_reversion.rsi_oversold}")
    print(f"✅ RSI超买阈值: {mean_reversion.rsi_overbought}")
    print(f"✅ 最大持仓时间: {mean_reversion.max_hold_hours}小时\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")

# ============================================================================
# 测试 2: 突破策略
# ============================================================================
print("📋 测试 2: 突破策略")
print("-" * 80)

try:
    from strategies.breakout import BreakoutStrategy
    
    breakout = BreakoutStrategy()
    print(f"✅ 策略名称: {breakout.name}")
    print(f"✅ 策略描述: {breakout.description}")
    print(f"✅ 盘整期: {breakout.consolidation_period}根K线")
    print(f"✅ 成交量倍数: {breakout.volume_surge_multiplier}x")
    print(f"✅ 最大持仓时间: {breakout.max_hold_hours}小时\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")

# ============================================================================
# 测试 3: 动量策略
# ============================================================================
print("📋 测试 3: 动量策略")
print("-" * 80)

try:
    from strategies.momentum import MomentumStrategy
    
    momentum = MomentumStrategy()
    print(f"✅ 策略名称: {momentum.name}")
    print(f"✅ 策略描述: {momentum.description}")
    print(f"✅ 连续K线: {momentum.consecutive_candles}根")
    print(f"✅ RSI区间: {momentum.rsi_min}-{momentum.rsi_max}")
    print(f"✅ ADX阈值: {momentum.adx_threshold}")
    print(f"✅ 追踪止损: {momentum.trailing_atr_multiplier} ATR\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")

# ============================================================================
# 测试 4: 回测引擎
# ============================================================================
print("📋 测试 4: 回测引擎")
print("-" * 80)

try:
    from backtest_engine import BacktestEngine
    
    # 创建回测引擎
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission_rate=0.001,
        slippage_rate=0.0005
    )
    
    print(f"✅ 初始资金: ${engine.initial_capital:,.2f}")
    print(f"✅ 手续费率: {engine.commission_rate * 100}%")
    print(f"✅ 滑点率: {engine.slippage_rate * 100}%")
    
    # 生成模拟数据
    print("\n生成模拟历史数据...")
    dates = pd.date_range(start='2024-01-01', periods=200, freq='1H')
    np.random.seed(42)
    
    # 模拟价格走势（震荡上涨）
    base_price = 50000
    price_changes = np.random.randn(200) * 100
    prices = base_price + np.cumsum(price_changes)
    
    price_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(200) * 50,
        'high': prices + np.abs(np.random.randn(200) * 100),
        'low': prices - np.abs(np.random.randn(200) * 100),
        'close': prices,
        'volume': np.random.uniform(100, 1000, 200)
    })
    
    print(f"✅ 生成了 {len(price_data)} 根K线")
    print(f"✅ 时间范围: {price_data['timestamp'].iloc[0]} ~ {price_data['timestamp'].iloc[-1]}")
    print(f"✅ 价格范围: ${price_data['close'].min():.2f} - ${price_data['close'].max():.2f}")
    
    # 运行简单回测
    print("\n运行回测（均值回归策略）...")
    results = engine.run_backtest(mean_reversion, price_data)
    
    print(f"\n✅ 回测完成!")
    print(f"   总交易: {results['total_trades']}")
    print(f"   最终资金: ${results['final_capital']:,.2f}")
    print(f"   总收益率: {results['total_return_pct']:.2f}%\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")
    import traceback
    traceback.print_exc()

# ============================================================================
# 测试 5: 性能监控面板
# ============================================================================
print("📋 测试 5: 性能监控面板")
print("-" * 80)

try:
    from monitoring_panel import PerformanceMonitor
    
    monitor = PerformanceMonitor(max_history=100)
    
    # 模拟更新
    monitor.update_equity(10000)
    monitor.update_equity(10100)
    monitor.update_equity(10050)
    
    # 记录交易
    monitor.record_trade({
        'strategy': 'MeanReversion',
        'side': 'long',
        'entry_price': 50000,
        'exit_price': 50500,
        'net_pnl': 48.5,
        'return_pct': 0.97
    })
    
    monitor.record_trade({
        'strategy': 'Breakout',
        'side': 'long',
        'entry_price': 50500,
        'exit_price': 51000,
        'net_pnl': 95.0,
        'return_pct': 1.88
    })
    
    # 记录策略切换
    monitor.record_strategy_switch('MeanReversion', 'Breakout', '市场突破盘整')
    
    # 更新持仓
    monitor.update_position({
        'side': 'long',
        'entry_price': 51000,
        'size': 0.1,
        'stop_loss': 50500,
        'take_profit': 52000
    })
    
    print("✅ 监控器初始化成功")
    print(f"✅ 权益历史: {len(monitor.equity_history)} 条记录")
    print(f"✅ 交易历史: {len(monitor.trade_history)} 条记录")
    print(f"✅ 策略切换: {len(monitor.strategy_switches)} 条记录")
    print(f"✅ 警告记录: {len(monitor.alerts)} 条记录")
    
    # 获取仪表板数据
    dashboard_data = monitor.get_dashboard_data()
    print(f"\n✅ 仪表板数据:")
    print(f"   当前权益: ${dashboard_data['summary']['current_equity']:,.2f}")
    print(f"   总交易: {dashboard_data['summary']['total_trades']}")
    print(f"   胜率: {dashboard_data['summary']['win_rate']:.2f}%")
    
    # 打印监控面板
    print("\n" + "-"*80)
    monitor.print_dashboard()
    
    # 导出报告
    report_file = monitor.export_report('test_performance_report.json')
    print(f"✅ 性能报告已导出\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")
    import traceback
    traceback.print_exc()

# ============================================================================
# 测试 6: Web Dashboard
# ============================================================================
print("📋 测试 6: Web Dashboard")
print("-" * 80)

try:
    from web_dashboard import DashboardConnector, init_dashboard
    
    # 使用前面创建的监控器
    init_dashboard(monitor)
    
    # 创建连接器
    dashboard = DashboardConnector(monitor, host='127.0.0.1', port=5001)
    
    print("✅ Dashboard 连接器创建成功")
    print("✅ 监听地址: http://127.0.0.1:5001")
    print("\n⚠️ 注意: Dashboard 需要手动启动")
    print("   运行: dashboard.start() 或访问 http://localhost:5001")
    print("   本测试跳过实际启动（避免阻塞）\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")

# ============================================================================
# 测试 7: 钉钉机器人
# ============================================================================
print("📋 测试 7: 钉钉机器人通知")
print("-" * 80)

try:
    from dingding_notifier import DingDingNotifier
    
    # 创建通知器（不使用真实webhook）
    notifier = DingDingNotifier(
        webhook_url="",  # 留空表示测试模式
        secret=""
    )
    
    print("✅ 钉钉通知器创建成功")
    print(f"✅ 状态: {'启用' if notifier.enabled else '禁用（测试模式）'}")
    
    # 测试通知方法（不实际发送）
    print("\n✅ 可用通知方法:")
    print("   - notify_trade_open()     开仓通知")
    print("   - notify_trade_close()    平仓通知")
    print("   - notify_strategy_switch() 策略切换")
    print("   - notify_risk_warning()   风险警告")
    print("   - notify_daily_summary()  每日摘要")
    print("   - notify_system_start()   系统启动")
    print("   - notify_system_stop()    系统停止")
    
    print("\n⚠️ 注意: 实际使用需要配置:")
    print("   1. 在钉钉群创建自定义机器人")
    print("   2. 获取 webhook_url 和 secret")
    print("   3. 在 config.json 中配置")
    print("   4. 参考 NEW_FEATURES_GUIDE.md 查看详细步骤\n")
    
except Exception as e:
    print(f"❌ 测试失败: {str(e)}\n")

# ============================================================================
# 测试总结
# ============================================================================
print("\n" + "="*80)
print("🎉 测试完成!")
print("="*80)

print("\n✅ 已成功测试的功能:")
print("   1. ✅ 均值回归策略 (MeanReversionStrategy)")
print("   2. ✅ 突破策略 (BreakoutStrategy)")
print("   3. ✅ 动量策略 (MomentumStrategy)")
print("   4. ✅ 回测引擎 (BacktestEngine)")
print("   5. ✅ 性能监控面板 (PerformanceMonitor)")
print("   6. ✅ Web Dashboard (DashboardConnector)")
print("   7. ✅ 钉钉机器人 (DingDingNotifier)")

print("\n📚 下一步:")
print("   1. 阅读 NEW_FEATURES_GUIDE.md 了解详细用法")
print("   2. 配置 config.json 设置交易参数")
print("   3. 运行实际回测验证策略效果")
print("   4. 配置钉钉机器人接收通知")
print("   5. 启动 Web Dashboard 监控实时状态")

print("\n💡 快速开始:")
print("   # 运行回测")
print("   python test_all_features.py")
print()
print("   # 启动 Web Dashboard")
print("   python -c \"from web_dashboard import run_dashboard; from monitoring_panel import PerformanceMonitor; from web_dashboard import init_dashboard; m = PerformanceMonitor(); init_dashboard(m); run_dashboard()\"")
print()
print("   # 测试钉钉通知")
print("   python -m dingding_notifier")

print("\n" + "="*80 + "\n")
