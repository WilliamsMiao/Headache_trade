#!/usr/bin/env python
"""
集成测试
测试整个系统的集成工作流程
"""

import sys
import pandas as pd
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from headache_trade.live.bot import MultiStrategyBot
from headache_trade.backtest.engine import BacktestEngine
from headache_trade.strategies import (
    MomentumStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    TrendFollowingStrategy,
    GridTradingStrategy
)
from headache_trade.ai.regime_detector import MarketRegimeDetector


def test_bot_initialization():
    """测试1: Bot初始化"""
    print("\n" + "="*70)
    print("测试1: Bot初始化")
    print("="*70)
    
    try:
        bot = MultiStrategyBot()
        
        # 验证Bot属性
        assert hasattr(bot, 'strategies')
        assert hasattr(bot, 'regime_detector')
        assert hasattr(bot, 'active_strategy')
        assert len(bot.strategies) == 5
        
        print("[OK] Bot初始化成功")
        print(f"   策略数量: {len(bot.strategies)}")
        print(f"   当前策略: {bot.active_strategy_name}")
        return True
    except Exception as e:
        print(f"[FAIL] Bot初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_activation():
    """测试2: 策略激活"""
    print("\n" + "="*70)
    print("测试2: 策略激活")
    print("="*70)
    
    strategies = [
        MomentumStrategy(),
        MeanReversionStrategy(),
        BreakoutStrategy(),
        TrendFollowingStrategy(),
        GridTradingStrategy()
    ]
    
    success_count = 0
    for strategy in strategies:
        try:
            strategy.activate()
            assert strategy.is_active
            print(f"[OK] {strategy.name} 激活成功")
            success_count += 1
        except Exception as e:
            print(f"[FAIL] {strategy.name} 激活失败: {e}")
    
    print(f"\n总计: {success_count}/{len(strategies)} 策略激活成功")
    return success_count == len(strategies)


def test_market_regime_detection():
    """测试3: 市场状态检测"""
    print("\n" + "="*70)
    print("测试3: 市场状态检测")
    print("="*70)
    
    data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
    
    if not data_file.exists():
        print("[WARN] 数据文件不存在，跳过测试")
        return True
    
    try:
        data = pd.read_csv(data_file)
        detector = MarketRegimeDetector()
        
        # 测试不同时间段
        test_ranges = [
            (0, 200),
            (1000, 1200),
            (2000, 2200),
        ]
        
        for start, end in test_ranges:
            segment = data.iloc[start:end]
            regime_result = detector.detect_regime(segment)
            
            print(f"[OK] 时间段 {start}-{end}:")
            print(f"   市场状态: {regime_result.regime}")
            print(f"   趋势方向: {regime_result.trend_direction}")
            print(f"   趋势强度: {regime_result.trend_strength:.2f}")
            print(f"   波动率: {regime_result.volatility:.4f}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 市场状态检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_generation():
    """测试4: 信号生成"""
    print("\n" + "="*70)
    print("测试4: 信号生成")
    print("="*70)
    
    data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
    
    if not data_file.exists():
        print("[WARN] 数据文件不存在，跳过测试")
        return True
    
    try:
        data = pd.read_csv(data_file)
        bot = MultiStrategyBot()
        
        # 测试信号生成
        test_data = data.iloc[:500]
        signal = bot.generate_trading_signal(test_data)
        
        if signal:
            print(f"[OK] 信号生成成功:")
            print(f"   信号类型: {signal.signal_type.value}")
            print(f"   当前策略: {bot.active_strategy_name}")
            print(f"   信心度: {signal.confidence}")
        else:
            print("[OK] 无信号（正常情况）")
            print(f"   当前策略: {bot.active_strategy_name}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 信号生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_switching():
    """测试5: 策略自动切换"""
    print("\n" + "="*70)
    print("测试5: 策略自动切换")
    print("="*70)
    
    data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
    
    if not data_file.exists():
        print("[WARN] 数据文件不存在，跳过测试")
        return True
    
    try:
        data = pd.read_csv(data_file)
        bot = MultiStrategyBot()
        
        initial_strategy = bot.active_strategy_name
        print(f"初始策略: {initial_strategy}")
        
        # 测试不同时间段，看是否触发策略切换
        test_periods = [
            (100, 300),
            (1000, 1200),
            (2000, 2200),
        ]
        
        switch_count = 0
        for start, end in test_periods:
            test_data = data.iloc[start:end]
            old_strategy = bot.active_strategy_name
            
            # 选择策略（可能触发切换）
            bot.select_best_strategy(test_data)
            
            if bot.active_strategy_name != old_strategy:
                print(f"[OK] 策略切换: {old_strategy} → {bot.active_strategy_name}")
                switch_count += 1
            else:
                print(f"   保持策略: {bot.active_strategy_name}")
        
        print(f"\n总计: 检测到 {switch_count} 次策略切换")
        return True
    except Exception as e:
        print(f"[FAIL] 策略切换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_engine():
    """测试6: 回测引擎"""
    print("\n" + "="*70)
    print("测试6: 回测引擎")
    print("="*70)
    
    data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
    
    if not data_file.exists():
        print("[WARN] 数据文件不存在，跳过测试")
        return True
    
    try:
        data = pd.read_csv(data_file)
        test_data = data.head(300)  # 使用少量数据快速测试
        
        # 测试单策略回测
        strategy = MomentumStrategy()
        strategy.activate()
        
        engine = BacktestEngine()
        result = engine.run_backtest(strategy, test_data)
        
        print(f"[OK] 回测完成:")
        print(f"   总收益: {result.get('total_return', 0)*100:.2f}%")
        print(f"   交易次数: {result.get('total_trades', 0)}")
        print(f"   胜率: {result.get('win_rate', 0)*100:.2f}%")
        
        return True
    except Exception as e:
        print(f"[FAIL] 回测引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end_workflow():
    """测试7: 端到端工作流"""
    print("\n" + "="*70)
    print("测试7: 端到端工作流")
    print("="*70)
    
    data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
    
    if not data_file.exists():
        print("[WARN] 数据文件不存在，跳过测试")
        return True
    
    try:
        # 1. 初始化Bot
        bot = MultiStrategyBot()
        print("[OK] 步骤1: Bot初始化完成")
        
        # 2. 加载数据
        data = pd.read_csv(data_file)
        print(f"[OK] 步骤2: 数据加载完成 ({len(data)}行)")
        
        # 3. 市场状态检测
        regime_result = bot.regime_detector.detect_regime(data.iloc[:500])
        print(f"[OK] 步骤3: 市场状态检测完成 ({regime_result.regime})")
        
        # 4. 策略选择
        bot.select_best_strategy(data.iloc[:500])
        print(f"[OK] 步骤4: 策略选择完成 ({bot.active_strategy_name})")
        
        # 5. 信号生成
        signal = bot.generate_trading_signal(data.iloc[:500])
        print(f"[OK] 步骤5: 信号生成完成 ({'有信号' if signal else '无信号'})")
        
        # 6. 仓位计算
        if signal:
            position_size = bot.calculate_position_size(10000, signal)
            print(f"[OK] 步骤6: 仓位计算完成 ({position_size:.4f} BTC)")
        else:
            print("[OK] 步骤6: 无需计算仓位（无信号）")
        
        # 7. 回测验证
        engine = BacktestEngine()
        result = engine.run_backtest(bot.active_strategy, data.head(300))
        print(f"[OK] 步骤7: 回测验证完成 (收益: {result.get('total_return', 0)*100:.2f}%)")
        
        print("\n[OK] 端到端工作流测试通过!")
        return True
    except Exception as e:
        print(f"\n[FAIL] 端到端工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """测试8: 错误处理"""
    print("\n" + "="*70)
    print("测试8: 错误处理")
    print("="*70)
    
    # 测试空数据
    try:
        empty_data = pd.DataFrame()
        detector = MarketRegimeDetector()
        
        # 应该抛出异常或返回默认值
        try:
            result = detector.detect_regime(empty_data)
            print("[WARN] 空数据未抛出异常（可能有默认处理）")
        except Exception:
            print("[OK] 空数据正确抛出异常")
    except Exception as e:
        print(f"[FAIL] 错误处理测试失败: {e}")
        return False
    
    # 测试无效策略
    try:
        bot = MultiStrategyBot()
        old_strategies = bot.strategies
        bot.strategies = {}  # 清空策略
        
        # 尝试选择策略
        try:
            bot.active_strategy_name = 'invalid_strategy'
            bot.active_strategy = bot.strategies.get('invalid_strategy')
            print("[WARN] 无效策略未被正确处理")
        except:
            print("[OK] 无效策略正确处理")
        finally:
            bot.strategies = old_strategies
    except Exception as e:
        print(f"[FAIL] 错误处理测试失败: {e}")
        return False
    
    print("[OK] 错误处理测试通过")
    return True


def main():
    """运行所有集成测试"""
    print("\n" + "="*70)
    print("集成测试套件")
    print("="*70)
    
    tests = [
        ("Bot初始化", test_bot_initialization),
        ("策略激活", test_strategy_activation),
        ("市场状态检测", test_market_regime_detection),
        ("信号生成", test_signal_generation),
        ("策略自动切换", test_strategy_switching),
        ("回测引擎", test_backtest_engine),
        ("端到端工作流", test_end_to_end_workflow),
        ("错误处理", test_error_handling),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[FAIL] 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*70)
    print("集成测试总结")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "[OK] 通过" if success else "[FAIL] 失败"
        print(f"   {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有集成测试通过!")
        return 0
    else:
        print(f"\n[WARN] {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    exit(main())
