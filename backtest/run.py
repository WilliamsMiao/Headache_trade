"""
快速回测脚本 - 命令行入口

使用示例：
    python run.py --strategy momentum --days 90
    python run.py --compare momentum mean_reversion --days 90
    python run.py --list
"""

import sys
import os
from pathlib import Path

# 设置UTF-8输出（Windows）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass

sys.path.insert(0, str(Path(__file__).parent))

from backtest_system import BacktestSystem


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backtest System - Quick Run Script',
        epilog='Examples:\n'
               '  python run.py --list\n'
               '  python run.py --strategy momentum --days 90\n'
               '  python run.py --compare momentum mean_reversion breakout\n'
               '  python run.py --all\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 动作
    parser.add_argument('--list', action='store_true', help='List all available strategies')
    parser.add_argument('--strategy', type=str, help='Run single strategy')
    parser.add_argument('--compare', nargs='+', metavar='STRATEGY', help='Compare multiple strategies')
    parser.add_argument('--all', action='store_true', help='Compare all strategies')
    
    # 参数
    parser.add_argument('--days', type=int, default=90, help='Number of days (default: 90)')
    parser.add_argument('--timeframe', type=str, default='15m', 
                       choices=['1m', '5m', '15m', '1h', '4h', '1d'],
                       help='Timeframe (default: 15m)')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Trading pair (default: BTC/USDT)')
    parser.add_argument('--capital', type=float, default=10000, help='Initial capital (default: 10000)')
    
    args = parser.parse_args()
    
    # 创建系统
    system = BacktestSystem()
    
    # 执行动作
    if args.list:
        system.list_strategies()
    
    elif args.strategy:
        system.run_strategy(
            strategy_key=args.strategy,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            initial_capital=args.capital
        )
    
    elif args.compare:
        system.compare_strategies(
            strategy_keys=args.compare,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            initial_capital=args.capital
        )
    
    elif args.all:
        all_strategies = list(BacktestSystem.STRATEGIES.keys())
        system.compare_strategies(
            strategy_keys=all_strategies,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            initial_capital=args.capital
        )
    
    else:
        parser.print_help()
