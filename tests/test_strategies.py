"""
策略信号生成测试脚本
测试所有策略的基本功能和信号生成
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from headache_trade.strategies import (
    BreakoutStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    TrendFollowingStrategy,
    GridTradingStrategy,
    SignalType
)


def generate_sample_data(rows: int = 200, price_start: float = 50000.0) -> pd.DataFrame:
    """
    生成示例价格数据用于测试
    
    Args:
        rows: 生成的数据行数
        price_start: 起始价格
    
    Returns:
        pd.DataFrame: OHLCV数据
    """
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=rows, freq='15min')
    
    # 生成带趋势和波动的价格数据
    trend = np.linspace(0, rows * 0.5, rows)
    noise = np.random.randn(rows) * 100
    price = price_start + trend + noise
    
    # 生成OHLCV
    data = []
    for i, p in enumerate(price):
        high = p + abs(np.random.randn() * 50)
        low = p - abs(np.random.randn() * 50)
        open_price = p + np.random.randn() * 30
        close_price = p + np.random.randn() * 30
        volume = abs(np.random.randn() * 1000000)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    return df


def test_strategy(strategy, strategy_name: str, price_data: pd.DataFrame):
    """
    测试单个策略
    
    Args:
        strategy: 策略实例
        strategy_name: 策略名称
        price_data: 价格数据
    """
    print(f"\n{'='*60}")
    print(f"测试策略: {strategy_name}")
    print(f"{'='*60}")
    
    try:
        # 激活策略
        strategy.activate()
        print(f"✓ 策略已激活")
        
        # 生成信号
        signal = strategy.generate_signal(price_data, current_position=None)
        
        if signal is None:
            print(f"✓ 信号生成成功 (无信号)")
        else:
            print(f"✓ 信号生成成功:")
            print(f"  - 信号类型: {signal.signal_type.value}")
            print(f"  - 置信度: {signal.confidence:.2f}%")
            print(f"  - 入场价格: ${signal.entry_price:.2f}")
            if signal.stop_loss:
                print(f"  - 止损价格: ${signal.stop_loss:.2f}")
            if signal.take_profit:
                print(f"  - 止盈价格: ${signal.take_profit:.2f}")
            if signal.metadata:
                print(f"  - 元数据: {signal.metadata.get('reason', 'N/A')}")
        
        # 测试仓位计算
        if signal and signal.signal_type != SignalType.HOLD:
            position_size = strategy.calculate_position_size(
                account_balance=10000.0,
                signal=signal
            )
            print(f"✓ 仓位计算成功: {position_size:.4f}")
        
        # 测试退出条件
        should_exit = strategy.should_exit(
            price_data=price_data,
            entry_price=price_data['close'].iloc[-10],
            position_side='long'
        )
        print(f"✓ 退出条件检查成功: {should_exit}")
        
        # 测试性能摘要
        summary = strategy.get_performance_summary()
        print(f"✓ 性能摘要获取成功:")
        print(f"  - 总交易数: {summary['total_trades']}")
        print(f"  - 胜率: {summary['win_rate']:.2f}%")
        
        print(f"\n✅ {strategy_name} 测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ {strategy_name} 测试失败!")
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("策略信号生成测试")
    print("="*60)
    
    # 生成测试数据
    print("\n生成测试数据...")
    price_data = generate_sample_data(rows=200, price_start=50000.0)
    print(f"✓ 生成了 {len(price_data)} 行测试数据")
    print(f"  价格范围: ${price_data['close'].min():.2f} - ${price_data['close'].max():.2f}")
    
    # 定义所有策略
    strategies = [
        (BreakoutStrategy(), "突破策略 (BreakoutStrategy)"),
        (MeanReversionStrategy(), "均值回归策略 (MeanReversionStrategy)"),
        (MomentumStrategy(), "动量策略 (MomentumStrategy)"),
        (TrendFollowingStrategy(), "趋势跟随策略 (TrendFollowingStrategy)"),
        (GridTradingStrategy(), "网格交易策略 (GridTradingStrategy)"),
    ]
    
    # 测试所有策略
    results = []
    for strategy, name in strategies:
        result = test_strategy(strategy, name, price_data)
        results.append((name, result))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 个策略测试通过")
    
    if passed == total:
        print("\n🎉 所有策略测试通过!")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个策略测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
