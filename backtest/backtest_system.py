"""
生产级回测系统 - 统一的策略回测入口
职责：协调数据管理、回测执行、报告生成

使用示例：
    from backtest_system import BacktestSystem
    
    # 创建回测系统
    system = BacktestSystem()
    
    # 运行单个策略回测
    system.run_strategy('momentum', days=90, timeframe='15m')
    
    # 对比多个策略
    system.compare_strategies(['momentum', 'mean_reversion'], days=90)
"""

import sys
from pathlib import Path

# 添加trading_bots到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'trading_bots'))

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from data_manager import DataManager
from report_generator import BacktestReport
from backtest_engine import BacktestEngine

# 导入策略
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.momentum import MomentumStrategy
from strategies.grid_strategy import GridTradingStrategy
from strategies.trend_following import TrendFollowingStrategy


class BacktestSystem:
    """
    生产级回测系统
    
    设计原则：
    1. 低耦合：各组件独立，通过接口交互
    2. 高内聚：每个组件职责单一
    3. 可扩展：新增策略只需继承基类
    4. 标准化：统一的输入输出格式
    """
    
    # 策略注册表
    STRATEGIES = {
        'mean_reversion': {
            'class': MeanReversionStrategy,
            'name': 'Mean Reversion',
            'default_params': {}
        },
        'breakout': {
            'class': BreakoutStrategy,
            'name': 'Breakout',
            'default_params': {}
        },
        'momentum': {
            'class': MomentumStrategy,
            'name': 'Momentum',
            'default_params': {}
        },
        'grid': {
            'class': GridTradingStrategy,
            'name': 'Grid Trading',
            'default_params': {
                'grid_count': 7,
                'grid_spacing_atr': 0.5
            }
        },
        'trend': {
            'class': TrendFollowingStrategy,
            'name': 'Trend Following',
            'default_params': {}
        }
    }
    
    def __init__(
        self,
        data_dir: str = 'data',
        output_dir: str = 'backtest_results'
    ):
        """
        初始化回测系统
        
        Args:
            data_dir: 数据目录
            output_dir: 输出目录
        """
        self.data_manager = DataManager(data_dir)
        self.report_generator = BacktestReport(output_dir)
        
        print("\n" + "="*80)
        print(" "*25 + "BACKTEST SYSTEM v1.0")
        print("="*80)
        print(f"\nData Directory:    {data_dir}/")
        print(f"Output Directory:  {output_dir}/")
        print(f"Registered Strategies: {len(self.STRATEGIES)}")
        print("="*80 + "\n")
    
    def list_strategies(self):
        """列出所有可用策略"""
        print("\nAvailable Strategies:")
        print("-"*60)
        for key, info in self.STRATEGIES.items():
            print(f"  {key:20s} - {info['name']}")
        print("-"*60 + "\n")
    
    def run_strategy(
        self,
        strategy_key: str,
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT',
        timeframe: str = '15m',
        days: int = 90,
        initial_capital: float = 10000,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        custom_params: Optional[Dict] = None,
        save_report: bool = True
    ) -> Dict[str, Any]:
        """
        运行单个策略回测
        
        Args:
            strategy_key: 策略键名
            exchange: 交易所
            symbol: 交易对
            timeframe: 时间周期
            days: 天数
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage_rate: 滑点率
            custom_params: 自定义参数
            save_report: 是否保存报告
        
        Returns:
            包含results和report的字典
        """
        
        if strategy_key not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy_key}. Use list_strategies() to see available strategies.")
        
        strategy_info = self.STRATEGIES[strategy_key]
        
        print(f"\n{'='*80}")
        print(f"RUNNING BACKTEST: {strategy_info['name']}")
        print(f"{'='*80}\n")
        
        # 1. 获取数据
        print("[Step 1/4] Loading data...")
        price_data = self.data_manager.fetch_data(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            days=days
        )
        
        data_info = {
            'exchange': exchange,
            'symbol': symbol,
            'timeframe': timeframe,
            'days': days,
            'candles': len(price_data),
            'period': f"{price_data['timestamp'].iloc[0]} to {price_data['timestamp'].iloc[-1]}"
        }
        
        print(f"[Data] Loaded {len(price_data)} candles")
        print(f"[Data] Period: {data_info['period']}\n")
        
        # 2. 创建策略实例
        print("[Step 2/4] Initializing strategy...")
        
        # 合并默认参数和自定义参数
        params = strategy_info['default_params'].copy()
        if custom_params:
            params.update(custom_params)
        
        strategy = strategy_info['class'](**params)
        print(f"[Strategy] {strategy_info['name']}")
        if params:
            print(f"[Params] {params}\n")
        
        # 3. 运行回测
        print("[Step 3/4] Running backtest...")
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate
        )
        
        results = engine.run_backtest(strategy, price_data)
        
        print(f"[Results] Completed {results.get('total_trades', 0)} trades")
        print(f"[Results] Return: {results.get('total_return', 0):+.2f}%\n")
        
        # 4. 生成报告
        print("[Step 4/4] Generating report...")
        
        report_text = self.report_generator.generate_report(
            strategy_name=strategy_info['name'],
            results=results,
            params=params,
            data_info=data_info,
            save=save_report
        )
        
        print("\n" + "="*80)
        print(report_text)
        
        return {
            'strategy': strategy_info['name'],
            'results': results,
            'params': params,
            'data_info': data_info,
            'report': report_text
        }
    
    def compare_strategies(
        self,
        strategy_keys: List[str],
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT',
        timeframe: str = '15m',
        days: int = 90,
        initial_capital: float = 10000,
        save_report: bool = True
    ) -> List[Dict]:
        """
        对比多个策略
        
        Args:
            strategy_keys: 策略键名列表
            其他参数同run_strategy
        
        Returns:
            策略结果列表
        """
        
        print(f"\n{'='*80}")
        print(f"COMPARING {len(strategy_keys)} STRATEGIES")
        print(f"{'='*80}\n")
        
        # 运行所有策略
        all_results = []
        
        for i, key in enumerate(strategy_keys, 1):
            print(f"\n[{i}/{len(strategy_keys)}] Testing {key}...")
            
            try:
                result = self.run_strategy(
                    strategy_key=key,
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    days=days,
                    initial_capital=initial_capital,
                    save_report=False  # 先不保存单个报告
                )
                all_results.append(result)
            except Exception as e:
                print(f"[Error] Failed to test {key}: {e}")
                continue
        
        # 生成对比报告
        if all_results and save_report:
            print(f"\n{'='*80}")
            print("GENERATING COMPARISON REPORT")
            print(f"{'='*80}\n")
            
            comparison_text = self.report_generator.compare_strategies(
                all_results,
                save=True
            )
            
            print("\n" + comparison_text)
        
        return all_results
    
    def optimize_parameters(
        self,
        strategy_key: str,
        param_grid: Dict[str, List],
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT',
        timeframe: str = '15m',
        days: int = 90,
        initial_capital: float = 10000,
        metric: str = 'total_return'
    ) -> Dict[str, Any]:
        """
        参数优化
        
        Args:
            strategy_key: 策略键名
            param_grid: 参数网格，格式：{'param_name': [value1, value2, ...]}
            metric: 优化目标指标
        
        Returns:
            最佳参数和结果
        """
        
        print(f"\n{'='*80}")
        print(f"PARAMETER OPTIMIZATION: {self.STRATEGIES[strategy_key]['name']}")
        print(f"{'='*80}\n")
        
        # 加载数据（只加载一次）
        print("[Setup] Loading data...")
        price_data = self.data_manager.fetch_data(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            days=days
        )
        
        # 生成参数组合
        import itertools
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))
        
        print(f"[Setup] Testing {len(param_combinations)} parameter combinations")
        print(f"[Setup] Optimizing for: {metric}\n")
        
        best_result = None
        best_params = None
        best_score = float('-inf')
        
        # 测试每个参数组合
        for i, combination in enumerate(param_combinations, 1):
            params = dict(zip(param_names, combination))
            
            print(f"[{i}/{len(param_combinations)}] Testing: {params}", end=' ')
            
            try:
                # 创建策略
                strategy = self.STRATEGIES[strategy_key]['class'](**params)
                
                # 运行回测
                engine = BacktestEngine(
                    initial_capital=initial_capital,
                    commission_rate=0.001,
                    slippage_rate=0.0005
                )
                
                results = engine.run_backtest(strategy, price_data)
                score = results.get(metric, float('-inf'))
                
                print(f"-> {metric}: {score:.2f}")
                
                # 更新最佳结果
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_result = results.copy()
                
            except Exception as e:
                print(f"-> Error: {e}")
                continue
        
        # 输出最佳结果
        print(f"\n{'='*80}")
        print("OPTIMIZATION COMPLETE")
        print(f"{'='*80}\n")
        print(f"Best Parameters: {best_params}")
        print(f"Best {metric}: {best_score:.2f}")
        print(f"Total Return: {best_result.get('total_return', 0):+.2f}%")
        print(f"Win Rate: {best_result.get('win_rate', 0):.1f}%")
        print(f"{'='*80}\n")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_result': best_result,
            'all_combinations_tested': len(param_combinations)
        }


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Production-grade Backtest System')
    parser.add_argument('--action', choices=['run', 'compare', 'optimize', 'list'], default='list',
                       help='Action to perform')
    parser.add_argument('--strategy', type=str, help='Strategy key (for run/optimize)')
    parser.add_argument('--strategies', nargs='+', help='Strategy keys (for compare)')
    parser.add_argument('--days', type=int, default=90, help='Number of days')
    parser.add_argument('--timeframe', type=str, default='15m', help='Timeframe')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Trading pair')
    
    args = parser.parse_args()
    
    # 创建系统
    system = BacktestSystem()
    
    if args.action == 'list':
        system.list_strategies()
    
    elif args.action == 'run':
        if not args.strategy:
            print("Error: --strategy required for run action")
            return
        
        system.run_strategy(
            strategy_key=args.strategy,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days
        )
    
    elif args.action == 'compare':
        if not args.strategies:
            print("Error: --strategies required for compare action")
            return
        
        system.compare_strategies(
            strategy_keys=args.strategies,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days
        )
    
    elif args.action == 'optimize':
        if not args.strategy:
            print("Error: --strategy required for optimize action")
            return
        
        # 示例参数网格
        param_grid = {
            'rsi_oversold': [30, 35, 40],
            'rsi_overbought': [60, 65, 70]
        }
        
        system.optimize_parameters(
            strategy_key=args.strategy,
            param_grid=param_grid,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days
        )


if __name__ == '__main__':
    # 如果没有命令行参数，运行交互模式
    if len(sys.argv) == 1:
        system = BacktestSystem()
        
        print("\nInteractive Mode")
        print("1. List strategies")
        print("2. Run single strategy")
        print("3. Compare strategies")
        print("4. Exit")
        
        choice = input("\nSelect action (1-4): ").strip()
        
        if choice == '1':
            system.list_strategies()
        
        elif choice == '2':
            system.list_strategies()
            strategy = input("Enter strategy key: ").strip()
            system.run_strategy(strategy)
        
        elif choice == '3':
            system.list_strategies()
            strategies = input("Enter strategy keys (space-separated): ").strip().split()
            system.compare_strategies(strategies)
        
        else:
            print("Exiting...")
    else:
        main()
