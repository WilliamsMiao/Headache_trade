#!/usr/bin/env python
"""测试策略自动切换功能"""

import pandas as pd
from headache_trade.live.bot import MultiStrategyBot
from headache_trade.ai.regime_detector import MarketRegimeDetector

# 初始化Bot
print('='*70)
print('测试策略自动切换功能')
print('='*70)
bot = MultiStrategyBot()

# 加载历史数据
data = pd.read_csv('data/binance_BTC_USDT_15m_90d.csv')
print(f'\n数据加载: {len(data)}行')

# 测试不同时间段的市场状态和策略切换
test_periods = [
    ('trending_up', 100, 300),      # 上涨趋势
    ('ranging', 1000, 1200),         # 震荡市
    ('trending_down', 2000, 2200),   # 下跌趋势
    ('volatile', 3000, 3200),        # 高波动
    ('trending_up2', 5000, 5200),    # 再次上涨
]

print('\n' + '='*70)
print('测试不同市场状态下的策略切换')
print('='*70)

for label, start, end in test_periods:
    print(f'\n【{label.upper()}】测试时段: 第{start}-{end}根K线')
    test_data = data.iloc[start:end].copy()
    
    # 检测市场状态
    regime_result = bot.regime_detector.detect_regime(test_data)
    
    print(f'  📊 市场状态: {regime_result.regime}')
    print(f'  📈 趋势方向: {regime_result.trend_direction}')
    print(f'  💪 趋势强度: {regime_result.trend_strength:.2f}')
    print(f'  📉 波动率: {regime_result.volatility:.4f}')
    
    # 获取推荐策略
    if regime_result.regime == 'trending':
        if regime_result.trend_direction == 'up':
            recommended = 'momentum'
        else:
            recommended = 'trend_following'
    elif regime_result.regime == 'ranging':
        recommended = 'mean_reversion'
    elif regime_result.regime == 'volatile':
        recommended = 'breakout'
    else:
        recommended = 'grid'
    
    print(f'  🎯 推荐策略: {recommended}')
    
    # 使用Bot的select_best_strategy方法（会自动切换）
    old_strategy = bot.active_strategy_name
    selected = bot.select_best_strategy(test_data)
    
    if old_strategy != selected:
        print(f'  ✅ 策略切换: {old_strategy} → {selected}')
    else:
        print(f'  ✓ 保持策略: {selected}')

print('\n' + '='*70)
print('策略自动切换测试完成')
print('='*70)

# 再次完整测试Bot的generate_signal方法（包含自动切换逻辑）
print('\n\n' + '='*70)
print('测试Bot完整信号生成流程（含自动切换）')
print('='*70)

# 重置Bot
bot = MultiStrategyBot()
print(f'\n初始策略: {bot.active_strategy_name}')

# 使用不同时段数据测试
for i, (label, start, end) in enumerate(test_periods[:3], 1):
    print(f'\n--- 测试 {i}: {label.upper()} ---')
    test_data = data.iloc[:end].copy()  # 使用累计数据
    
    # 调用generate_trading_signal（会自动检测市场并切换策略）
    signal = bot.generate_trading_signal(test_data)
    
    if signal:
        print(f'  信号: {signal.signal_type.value}')
        print(f'  当前策略: {bot.active_strategy_name}')
        if hasattr(signal, 'reason'):
            print(f'  理由: {signal.reason}')
    else:
        print(f'  无信号')
        print(f'  当前策略: {bot.active_strategy_name}')

print('\n' + '='*70)
print('完整测试结束')
print('='*70)
