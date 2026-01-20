"""
测试AI回测参数优化功能
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
from strategies import get_optimizer, StrategyRegistry
from trading_bots.config import deepseek_client

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
            days=7,
            save_path=DATA_FILE
        )
        return df


def test_ai_suggestions(strategy_name: str):
    """测试AI参数建议功能"""
    print(f"\n{'='*60}")
    print(f"🤖 测试AI参数建议: {strategy_name}策略")
    print(f"{'='*60}")
    
    # 检查AI客户端
    if deepseek_client is None or not hasattr(deepseek_client, 'chat'):
        print("⚠️  DeepSeek客户端未配置，跳过AI建议测试")
        return False, None
    
    try:
        # 获取策略类
        strategy_class = StrategyRegistry.get_strategy_class(strategy_name)
        
        # 使用默认参数运行初始回测
        print("📊 步骤1: 运行初始回测（使用默认参数）...")
        df = ensure_test_data()
        
        initial_params = strategy_class().get_parameters()
        print(f"   初始参数: {initial_params}")
        
        backtest_config = {
            'initial_balance': 100,
            'leverage': 6,
            'fee_rate': 0.001,
            'slippage': 0.0001,
            'funding_rate': 0.0001,
            'verbose': False
        }
        
        initial_results = run_backtest_with_strategy(
            df=df,
            strategy_name=strategy_name,
            strategy_params=initial_params,
            backtest_config=backtest_config
        )
        
        print(f"   初始结果:")
        print(f"     总收益率: {initial_results.get('total_return_pct', 0):.2f}%")
        print(f"     胜率: {initial_results.get('win_rate', 0):.2f}%")
        print(f"     交易次数: {initial_results.get('total_trades', 0)}")
        
        # 使用AI优化器
        print("\n🤖 步骤2: 获取AI参数优化建议...")
        optimizer = get_optimizer(ai_client=deepseek_client)
        
        ai_result = optimizer.optimize_with_ai(
            strategy_class=strategy_class,
            backtest_results=initial_results,
            current_params=initial_params
        )
        
        if ai_result.get('success'):
            print("✅ AI建议获取成功!")
            print(f"   置信度: {ai_result.get('confidence', 0):.2f}")
            print(f"   整体评估: {ai_result.get('overall_assessment', 'N/A')}")
            
            suggestions = ai_result.get('suggestions', [])
            print(f"\n   参数建议 ({len(suggestions)} 条):")
            for i, suggestion in enumerate(suggestions, 1):
                param = suggestion.get('parameter', 'N/A')
                current = suggestion.get('current_value', 'N/A')
                suggested = suggestion.get('suggested_value', 'N/A')
                reason = suggestion.get('reason', 'N/A')
                print(f"     {i}. {param}:")
                print(f"        当前值: {current}")
                print(f"        建议值: {suggested}")
                print(f"        原因: {reason}")
            
            return True, ai_result
        else:
            error = ai_result.get('error', '未知错误')
            print(f"❌ AI建议获取失败: {error}")
            return False, ai_result
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_hybrid_optimization(strategy_name: str):
    """测试混合优化功能（AI建议 + 网格搜索）"""
    print(f"\n{'='*60}")
    print(f"🔬 测试混合优化: {strategy_name}策略")
    print(f"{'='*60}")
    
    # 检查AI客户端
    if deepseek_client is None or not hasattr(deepseek_client, 'chat'):
        print("⚠️  DeepSeek客户端未配置，跳过混合优化测试")
        return False, None
    
    try:
        # 获取策略类
        strategy_class = StrategyRegistry.get_strategy_class(strategy_name)
        
        # 加载数据
        print("📊 步骤1: 加载测试数据...")
        df = ensure_test_data()
        print(f"   数据量: {len(df)} 根K线")
        
        # 设置初始参数（使用较简单的参数以便测试）
        initial_params = strategy_class().get_parameters()
        # 只保留可优化的参数
        optimizable_params = {
            k: v for k, v in initial_params.items()
            if k in ['rsi_long_min', 'rsi_long_max', 'default_size', 'trend_strength_threshold']
        }
        if not optimizable_params:
            # 如果没有这些参数，使用所有参数
            optimizable_params = initial_params
        
        print(f"   初始参数: {optimizable_params}")
        
        # 运行混合优化
        print("\n🔬 步骤2: 运行混合优化（AI建议 + 局部网格搜索）...")
        optimizer = get_optimizer(ai_client=deepseek_client)
        
        backtest_config = {
            'initial_balance': 100,
            'leverage': 6,
            'fee_rate': 0.001,
            'slippage': 0.0001,
            'funding_rate': 0.0001,
            'verbose': False
        }
        
        # 注意：混合优化可能需要较长时间，这里使用较小的数据量
        result = optimizer.hybrid_optimize(
            strategy_class=strategy_class,
            df=df.iloc[:300],  # 使用前300根K线以加快测试
            initial_params=optimizable_params,
            backtest_config=backtest_config,
            ai_enabled=True
        )
        
        print("\n✅ 混合优化完成!")
        print(f"\n📊 优化结果对比:")
        print(f"   初始参数:")
        print(f"     收益率: {result['initial_results'].get('total_return_pct', 0):.2f}%")
        print(f"     胜率: {result['initial_results'].get('win_rate', 0):.2f}%")
        print(f"     交易次数: {result['initial_results'].get('total_trades', 0)}")
        
        print(f"\n   优化后参数:")
        print(f"     收益率: {result['best_results'].get('total_return_pct', 0):.2f}%")
        print(f"     胜率: {result['best_results'].get('win_rate', 0):.2f}%")
        print(f"     交易次数: {result['best_results'].get('total_trades', 0)}")
        
        improvement = result.get('improvement', {})
        print(f"\n   改进:")
        print(f"     收益率变化: {improvement.get('return', 0):+.2f}%")
        print(f"     胜率变化: {improvement.get('win_rate', 0):+.2f}%")
        
        if result.get('ai_suggestions'):
            print(f"\n   AI建议数量: {len(result['ai_suggestions'])}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_grid_search(strategy_name: str):
    """测试网格搜索功能"""
    print(f"\n{'='*60}")
    print(f"🔍 测试网格搜索: {strategy_name}策略")
    print(f"{'='*60}")
    
    try:
        # 获取策略类
        strategy_class = StrategyRegistry.get_strategy_class(strategy_name)
        
        # 加载数据
        print("📊 步骤1: 加载测试数据...")
        df = ensure_test_data()
        print(f"   数据量: {len(df)} 根K线")
        
        # 设置参数搜索范围（使用较小的范围以加快测试）
        if strategy_name == 'signal':
            param_ranges = {
                'rsi_long_min': [40, 45, 50],
                'rsi_long_max': [70, 75, 80]
            }
        elif strategy_name == 'trend':
            param_ranges = {
                'trend_strength_threshold': [55, 60, 65],
                'default_size': [0.04, 0.05, 0.06]
            }
        else:
            # 对于其他策略，使用通用参数
            param_ranges = {
                'default_size': [0.04, 0.05, 0.06]
            }
        
        print(f"   参数搜索范围: {param_ranges}")
        
        # 运行网格搜索
        print("\n🔍 步骤2: 运行网格搜索...")
        optimizer = get_optimizer()
        
        backtest_config = {
            'initial_balance': 100,
            'leverage': 6,
            'fee_rate': 0.001,
            'slippage': 0.0001,
            'funding_rate': 0.0001,
            'verbose': False
        }
        
        result = optimizer.grid_search(
            strategy_class=strategy_class,
            param_ranges=param_ranges,
            df=df.iloc[:300],  # 使用前300根K线以加快测试
            backtest_config=backtest_config,
            metric='total_return',
            max_iterations=20  # 限制迭代次数
        )
        
        print("\n✅ 网格搜索完成!")
        print(f"   总组合数: {result.get('total_combinations', 0)}")
        print(f"   最佳参数: {result.get('best_params', {})}")
        print(f"   最佳分数: {result.get('best_score', 0):.4f}")
        
        if result.get('best_results'):
            best_results = result['best_results']
            print(f"\n   最佳结果:")
            print(f"     收益率: {best_results.get('total_return_pct', 0):.2f}%")
            print(f"     胜率: {best_results.get('win_rate', 0):.2f}%")
            print(f"     交易次数: {best_results.get('total_trades', 0)}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🚀 开始测试AI回测参数优化功能")
    print("="*60)
    
    # 检查AI客户端
    if deepseek_client is None or not hasattr(deepseek_client, 'chat'):
        print("\n⚠️  警告: DeepSeek客户端未配置")
        print("   将跳过需要AI的功能测试，仅测试网格搜索功能")
        ai_available = False
    else:
        print("\n✅ DeepSeek客户端已配置")
        ai_available = True
    
    test_results = {}
    
    # 测试策略（选择信号策略和趋势策略进行测试）
    test_strategies = ['signal', 'trend']
    
    for strategy_name in test_strategies:
        print(f"\n{'='*60}")
        print(f"📋 测试策略: {strategy_name}")
        print(f"{'='*60}")
        
        strategy_results = {}
        
        # 1. 测试AI建议（如果AI可用）
        if ai_available:
            success, result = test_ai_suggestions(strategy_name)
            strategy_results['ai_suggestions'] = {'success': success, 'result': result}
        else:
            print("\n⏭️  跳过AI建议测试（AI客户端未配置）")
            strategy_results['ai_suggestions'] = {'success': False, 'reason': 'AI未配置'}
        
        # 2. 测试网格搜索
        success, result = test_grid_search(strategy_name)
        strategy_results['grid_search'] = {'success': success, 'result': result}
        
        # 3. 测试混合优化（如果AI可用）
        if ai_available:
            success, result = test_hybrid_optimization(strategy_name)
            strategy_results['hybrid_optimization'] = {'success': success, 'result': result}
        else:
            print("\n⏭️  跳过混合优化测试（AI客户端未配置）")
            strategy_results['hybrid_optimization'] = {'success': False, 'reason': 'AI未配置'}
        
        test_results[strategy_name] = strategy_results
    
    # 总结
    print(f"\n{'='*60}")
    print("📊 测试总结")
    print(f"{'='*60}")
    
    for strategy_name, results in test_results.items():
        print(f"\n{strategy_name}策略:")
        
        # AI建议
        ai_result = results.get('ai_suggestions', {})
        if ai_result.get('success'):
            print("  ✅ AI建议: 通过")
        elif ai_result.get('reason') == 'AI未配置':
            print("  ⏭️  AI建议: 跳过（AI未配置）")
        else:
            print("  ❌ AI建议: 失败")
        
        # 网格搜索
        grid_result = results.get('grid_search', {})
        if grid_result.get('success'):
            print("  ✅ 网格搜索: 通过")
        else:
            print("  ❌ 网格搜索: 失败")
        
        # 混合优化
        hybrid_result = results.get('hybrid_optimization', {})
        if hybrid_result.get('success'):
            print("  ✅ 混合优化: 通过")
        elif hybrid_result.get('reason') == 'AI未配置':
            print("  ⏭️  混合优化: 跳过（AI未配置）")
        else:
            print("  ❌ 混合优化: 失败")
    
    # 统计
    total_tests = 0
    passed_tests = 0
    
    for results in test_results.values():
        for test_name, test_result in results.items():
            if test_result.get('reason') != 'AI未配置':
                total_tests += 1
                if test_result.get('success'):
                    passed_tests += 1
    
    print(f"\n总计: {passed_tests}/{total_tests} 个测试通过")
    
    if passed_tests == total_tests:
        print("🎉 所有优化功能测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查错误信息")
        return 1


if __name__ == '__main__':
    exit(main())
