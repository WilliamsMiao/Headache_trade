"""
测试自适应参数优化功能
"""

import os
import sys
import pandas as pd

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backtest_runner import (
    load_historical_data,
    run_backtest_with_strategy
)
from strategies import MarketAnalyzer, AdaptiveOptimizer, get_optimizer, StrategyRegistry
from trading_bots.config import deepseek_client

# 数据文件路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_ROOT, 'data/backtest/data/test_data_15m_7d.json')


def test_market_analyzer():
    """测试市场分析器"""
    print("\n" + "="*60)
    print("测试市场分析器")
    print("="*60)
    
    try:
        df = load_historical_data(DATA_FILE)
        analyzer = MarketAnalyzer()
        
        # 测试单个时间点的市场分析
        test_index = len(df) - 1
        analysis = analyzer.analyze_market(df, test_index)
        
        print(f"\n市场分析结果 (索引 {test_index}):")
        print(f"  波动率水平: {analysis['volatility_level']}")
        print(f"  ATR百分比: {analysis['atr_pct']:.4f}")
        print(f"  震荡强度: {analysis['oscillation_strength']:.2f}")
        print(f"  趋势强度: {analysis['trend_strength']:.2f}")
        print(f"  成交量特征: {analysis['volume_profile']}")
        print(f"  市场状态: {analysis['market_regime']}")
        
        # 测试市场状态分布
        print("\n分析市场状态分布...")
        market_states = analyzer.analyze_market_states(df)
        for state, indices in market_states.items():
            print(f"  {state}: {len(indices)} 根K线 ({len(indices)/len(df)*100:.1f}%)")
        
        return True, analysis
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_adaptive_params():
    """测试策略的自适应参数调整"""
    print("\n" + "="*60)
    print("测试自适应参数调整")
    print("="*60)
    
    try:
        df = load_historical_data(DATA_FILE)
        analyzer = MarketAnalyzer()
        
        # 测试网格策略
        print("\n1. 测试网格策略自适应参数...")
        from strategies.grid_strategy import GridStrategy
        
        grid_strategy = GridStrategy()
        test_index = len(df) - 1
        market_analysis = analyzer.analyze_market(df, test_index)
        
        adapted_params = grid_strategy._adapt_parameters_to_market(market_analysis)
        print(f"   市场状态: {market_analysis['market_regime']}")
        print(f"   调整的参数: {list(adapted_params.keys())}")
        for param, value in adapted_params.items():
            base_value = grid_strategy.get_parameter(param)
            change = ((value - base_value) / base_value * 100) if base_value != 0 else 0
            print(f"     {param}: {base_value} -> {value} ({change:+.1f}%)")
        
        # 测试马丁格尔策略
        print("\n2. 测试马丁格尔策略自适应参数...")
        from strategies.martingale_strategy import MartingaleStrategy
        
        martingale_strategy = MartingaleStrategy()
        adapted_params = martingale_strategy._adapt_parameters_to_market(market_analysis)
        print(f"   市场状态: {market_analysis['market_regime']}")
        print(f"   调整的参数: {list(adapted_params.keys())}")
        for param, value in adapted_params.items():
            base_value = martingale_strategy.get_parameter(param)
            if isinstance(base_value, (int, float)):
                change = ((value - base_value) / base_value * 100) if base_value != 0 else 0
                print(f"     {param}: {base_value} -> {value} ({change:+.1f}%)")
            else:
                print(f"     {param}: {base_value} -> {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_adaptive_optimizer():
    """测试自适应优化器"""
    print("\n" + "="*60)
    print("测试自适应优化器")
    print("="*60)
    
    try:
        df = load_historical_data(DATA_FILE)
        
        # 使用较小的数据集以加快测试
        test_df = df.iloc[:300].reset_index(drop=True)
        
        print(f"使用 {len(test_df)} 根K线进行测试")
        
        # 创建优化器
        market_analyzer = MarketAnalyzer()
        base_optimizer = get_optimizer(ai_client=deepseek_client)
        adaptive_optimizer = AdaptiveOptimizer(market_analyzer, base_optimizer)
        
        # 测试网格策略
        print("\n测试网格策略的市场感知优化...")
        from strategies.grid_strategy import GridStrategy
        
        result = adaptive_optimizer.optimize_with_market_awareness(
            strategy_class=GridStrategy,
            df=test_df,
            backtest_config={
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'funding_rate': 0.0001,
                'verbose': False
            }
        )
        
        print(f"\n优化结果:")
        print(f"  市场状态分布: {result['state_summary']}")
        print(f"  优化后的参数:")
        for state, params in result['optimized_params_by_state'].items():
            print(f"    {state}: {len(params)} 个参数")
        
        if result.get('recommendation'):
            rec = result['recommendation']
            print(f"\n  推荐参数: {len(rec.get('recommended_params', {}))} 个")
            print(f"  推荐理由: {rec.get('reason', 'N/A')}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_multi_objective_optimization():
    """测试多目标优化"""
    print("\n" + "="*60)
    print("测试多目标优化")
    print("="*60)
    
    try:
        df = load_historical_data(DATA_FILE)
        test_df = df.iloc[:200].reset_index(drop=True)  # 使用更小的数据集
        
        optimizer = get_optimizer()
        from strategies.signal_strategy import SignalStrategy
        
        # 定义多目标
        objectives = {
            'total_return': 0.4,      # 收益率权重40%
            'win_rate': 0.3,          # 胜率权重30%
            'max_drawdown': -0.3      # 最大回撤权重-30%（越小越好）
        }
        
        print(f"优化目标: {objectives}")
        print(f"使用 {len(test_df)} 根K线")
        
        # 参数搜索范围（小范围以加快测试）
        param_ranges = {
            'rsi_long_min': [40, 45, 50],
            'rsi_long_max': [70, 75]
        }
        
        result = optimizer.multi_objective_optimize(
            strategy_class=SignalStrategy,
            param_ranges=param_ranges,
            df=test_df,
            objectives=objectives,
            max_iterations=10
        )
        
        print(f"\n多目标优化结果:")
        print(f"  最佳参数: {result.get('best_params', {})}")
        print(f"  最佳分数: {result.get('best_score', 0):.4f}")
        
        if result.get('best_results'):
            best_results = result['best_results']
            print(f"  最佳结果:")
            print(f"    收益率: {best_results.get('total_return_pct', 0):.2f}%")
            print(f"    胜率: {best_results.get('win_rate', 0):.2f}%")
            print(f"    交易次数: {best_results.get('total_trades', 0)}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_strategy_with_adaptive_params():
    """测试策略使用自适应参数运行回测"""
    print("\n" + "="*60)
    print("测试策略使用自适应参数运行回测")
    print("="*60)
    
    try:
        df = load_historical_data(DATA_FILE)
        test_df = df.iloc[:200].reset_index(drop=True)
        
        # 测试网格策略（启用自适应参数）
        print("\n1. 网格策略（启用自适应参数）...")
        results = run_backtest_with_strategy(
            df=test_df,
            strategy_name='grid',
            strategy_params={
                'grid_count': 10,
                'adaptive_params_enabled': True
            },
            backtest_config={
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'funding_rate': 0.0001,
                'verbose': False
            }
        )
        
        print(f"   收益率: {results.get('total_return_pct', 0):.2f}%")
        print(f"   交易次数: {results.get('total_trades', 0)}")
        
        # 测试马丁格尔策略（启用自适应参数）
        print("\n2. 马丁格尔策略（启用自适应参数）...")
        results = run_backtest_with_strategy(
            df=test_df,
            strategy_name='martingale',
            strategy_params={
                'initial_size': 0.01,
                'adaptive_params_enabled': True
            },
            backtest_config={
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'funding_rate': 0.0001,
                'verbose': False
            }
        )
        
        print(f"   收益率: {results.get('total_return_pct', 0):.2f}%")
        print(f"   交易次数: {results.get('total_trades', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 开始测试自适应参数优化功能")
    print("="*60)
    
    test_results = {}
    
    # 1. 测试市场分析器
    success, analysis = test_market_analyzer()
    test_results['market_analyzer'] = {'success': success, 'analysis': analysis}
    
    # 2. 测试自适应参数调整
    success = test_adaptive_params()
    test_results['adaptive_params'] = {'success': success}
    
    # 3. 测试自适应优化器
    success, result = test_adaptive_optimizer()
    test_results['adaptive_optimizer'] = {'success': success, 'result': result}
    
    # 4. 测试多目标优化
    success, result = test_multi_objective_optimization()
    test_results['multi_objective'] = {'success': success, 'result': result}
    
    # 5. 测试策略使用自适应参数
    success = test_strategy_with_adaptive_params()
    test_results['strategy_integration'] = {'success': success}
    
    # 总结
    print(f"\n{'='*60}")
    print("📊 测试总结")
    print(f"{'='*60}")
    
    for test_name, result in test_results.items():
        status = "✅ 通过" if result['success'] else "❌ 失败"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for r in test_results.values() if r['success'])
    total = len(test_results)
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有自适应优化功能测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查错误信息")
        return 1


if __name__ == '__main__':
    exit(main())
