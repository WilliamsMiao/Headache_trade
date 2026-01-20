"""
测试四个策略的回测功能
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backtest_runner import (
    fetch_historical_data,
    load_historical_data,
    run_backtest_with_strategy
)

# 数据文件路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data/backtest/data')
DATA_FILE = os.path.join(DATA_DIR, 'test_data_15m_7d.json')


def ensure_test_data():
    """确保有测试数据"""
    if os.path.exists(DATA_FILE):
        print(f"✅ 使用现有数据文件: {DATA_FILE}")
        return load_historical_data(DATA_FILE)
    else:
        print("📥 获取测试数据（7天）...")
        os.makedirs(DATA_DIR, exist_ok=True)
        df = fetch_historical_data(
            symbol='BTC/USDT:USDT',
            timeframe='15m',
            days=7,  # 使用7天数据快速测试
            save_path=DATA_FILE
        )
        return df


def test_strategy(strategy_name: str, strategy_params: dict = None):
    """测试单个策略"""
    print(f"\n{'='*60}")
    print(f"🧪 测试策略: {strategy_name}")
    print(f"{'='*60}")
    
    # 加载数据
    df = ensure_test_data()
    print(f"📊 数据量: {len(df)} 根K线")
    print(f"📅 时间范围: {df['timestamp'].iloc[0]} 至 {df['timestamp'].iloc[-1]}")
    
    # 回测配置
    backtest_config = {
        'initial_balance': 100,
        'leverage': 6,
        'fee_rate': 0.001,
        'slippage': 0.0001,
        'funding_rate': 0.0001,
        'verbose': False  # 减少输出
    }
    
    try:
        # 运行回测
        results = run_backtest_with_strategy(
            df=df,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            backtest_config=backtest_config
        )
        
        # 显示结果
        print(f"\n✅ 回测完成!")
        print(f"   策略名称: {results.get('strategy_name', strategy_name)}")
        print(f"   初始资金: {results.get('initial_balance', 100):.2f} USDT")
        print(f"   最终资金: {results.get('final_balance', 100):.2f} USDT")
        print(f"   总收益率: {results.get('total_return_pct', 0):.2f}%")
        print(f"   总交易次数: {results.get('total_trades', 0)}")
        print(f"   盈利交易: {results.get('winning_trades', 0)}")
        print(f"   亏损交易: {results.get('losing_trades', 0)}")
        print(f"   胜率: {results.get('win_rate', 0):.2f}%")
        
        if results.get('trades'):
            print(f"   交易记录: {len(results['trades'])} 笔")
            # 显示前3笔交易
            for i, trade in enumerate(results['trades'][:3]):
                print(f"     交易{i+1}: {trade.get('side', 'N/A')} | "
                      f"入场: {trade.get('entry_price', 0):.2f} | "
                      f"盈亏: {trade.get('pnl_pct', 0):.2f}%")
        
        return True, results
        
    except Exception as e:
        print(f"\n❌ 回测失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 开始测试四个策略的回测功能")
    print("="*60)
    
    # 测试结果
    test_results = {}
    
    # 1. 测试信号策略
    success, results = test_strategy('signal', {
        'rsi_long_min': 45,
        'rsi_long_max': 75,
        'default_size': 0.05
    })
    test_results['signal'] = {'success': success, 'results': results}
    
    # 2. 测试趋势策略
    success, results = test_strategy('trend', {
        'trend_strength_threshold': 60,
        'default_size': 0.05
    })
    test_results['trend'] = {'success': success, 'results': results}
    
    # 3. 测试区间网格策略
    success, results = test_strategy('grid', {
        'grid_count': 10,  # 减少网格数量以加快测试
        'price_range_lower': -0.03,
        'price_range_upper': 0.03,
        'position_size_per_grid': 0.01
    })
    test_results['grid'] = {'success': success, 'results': results}
    
    # 4. 测试马丁格尔策略
    success, results = test_strategy('martingale', {
        'initial_size': 0.01,
        'max_iterations': 3,  # 减少最大加仓次数以加快测试
        'entry_interval_pct': 0.01
    })
    test_results['martingale'] = {'success': success, 'results': results}
    
    # 总结
    print(f"\n{'='*60}")
    print("📊 测试总结")
    print(f"{'='*60}")
    
    for strategy_name, result in test_results.items():
        status = "✅ 通过" if result['success'] else "❌ 失败"
        print(f"{status} - {strategy_name}策略")
        if result['success'] and result['results']:
            ret = result['results'].get('total_return_pct', 0)
            trades = result['results'].get('total_trades', 0)
            print(f"     收益率: {ret:.2f}% | 交易次数: {trades}")
    
    # 统计
    passed = sum(1 for r in test_results.values() if r['success'])
    total = len(test_results)
    print(f"\n总计: {passed}/{total} 个策略测试通过")
    
    if passed == total:
        print("🎉 所有策略测试通过！")
        return 0
    else:
        print("⚠️  部分策略测试失败，请检查错误信息")
        return 1


if __name__ == '__main__':
    exit(main())
