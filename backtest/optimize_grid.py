"""
网格策略参数优化器
测试不同参数组合，寻找最优配置

Author: AI Assistant
Date: 2025-11-18
"""

import sys
sys.path.append('c:/Users/cair1/Desktop/HT/Headache_trade')

from backtest.backtest_system import BacktestSystem
from trading_bots.market_regime_detector import MarketRegimeDetector
from trading_bots.data_manager import DataManager
import pandas as pd


def optimize_grid_params():
    """优化网格策略参数"""
    
    print("\n" + "="*80)
    print("GRID STRATEGY PARAMETER OPTIMIZATION")
    print("="*80)
    
    # 1. 获取数据并检测市场状态
    print("\n[Step 1] Fetching data and detecting market regime...")
    data_mgr = DataManager()
    df = data_mgr.fetch_data('binance', 'BTC/USDT', '15m', days=7)
    
    detector = MarketRegimeDetector()
    regime = detector.detect_regime(df)
    
    print(f"\nMarket Regime: {regime.regime.upper()}")
    print(f"Trend Direction: {regime.trend_direction.upper()}")
    print(f"ADX: {regime.adx_value:.2f}")
    print(f"Range Strength: {regime.range_strength:.2f}")
    
    # 2. 定义参数组合
    print("\n[Step 2] Testing parameter combinations...")
    
    param_combinations = [
        # (grid_count, grid_spacing_atr, description)
        (5, 0.3, "少网格+窄间距"),
        (5, 0.5, "少网格+中间距"),
        (5, 0.8, "少网格+宽间距"),
        (7, 0.3, "中网格+窄间距 (快速)"),
        (7, 0.5, "中网格+中间距 (默认)"),
        (7, 0.8, "中网格+宽间距"),
        (10, 0.3, "多网格+窄间距 (密集)"),
        (10, 0.5, "多网格+中间距"),
        (10, 0.8, "多网格+宽间距 (保守)"),
        (15, 0.5, "超多网格+中间距"),
    ]
    
    results = []
    
    for grid_count, grid_spacing, desc in param_combinations:
        print(f"\n  Testing: {desc} (grid={grid_count}, spacing={grid_spacing})")
        
        # 运行回测
        system = BacktestSystem()
        result_dict = system.run_strategy(
            strategy_key='grid',
            symbol='BTC/USDT',
            timeframe='15m',
            days=7,
            initial_capital=10000,
            custom_params={
                'grid_count': grid_count,
                'grid_spacing_atr': grid_spacing
            },
            save_report=False  # 不保存报告
        )
        
        result = result_dict['results']
        
        # 记录结果
        results.append({
            'grid_count': grid_count,
            'grid_spacing_atr': grid_spacing,
            'description': desc,
            'return_pct': result['total_return_pct'],
            'total_pnl': result['total_pnl'],
            'total_trades': result['total_trades'],
            'win_rate': result['win_rate'],
            'profit_factor': result.get('profit_factor', 0),
            'max_drawdown_pct': result['max_drawdown_pct'],
            'sharpe_ratio': result.get('sharpe_ratio', 0)
        })
        
        print(f"    Return: {result['total_return_pct']:.2f}%")
        print(f"    Trades: {result['total_trades']}")
        print(f"    Win Rate: {result['win_rate']:.2f}%")
    
    # 3. 生成优化报告
    print("\n" + "="*80)
    print("OPTIMIZATION RESULTS")
    print("="*80)
    
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('return_pct', ascending=False)
    
    print("\n[Top 5 Configurations by Return]")
    print("-" * 80)
    for i, row in df_results.head(5).iterrows():
        print(f"\n{row['description']}")
        print(f"  Grid Count: {row['grid_count']}, Spacing: {row['grid_spacing_atr']}")
        print(f"  Return: {row['return_pct']:.2f}%")
        print(f"  P&L: ${row['total_pnl']:.2f}")
        print(f"  Trades: {row['total_trades']}")
        print(f"  Win Rate: {row['win_rate']:.2f}%")
        print(f"  Profit Factor: {row['profit_factor']:.2f}")
        print(f"  Max Drawdown: {row['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe: {row['sharpe_ratio']:.2f}")
    
    # 4. 推荐最优参数
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    best_return = df_results.iloc[0]
    best_winrate = df_results.nlargest(1, 'win_rate').iloc[0]
    best_sharpe = df_results.nlargest(1, 'sharpe_ratio').iloc[0]
    
    print(f"\n[Best Return]")
    print(f"  {best_return['description']}")
    print(f"  Config: grid_count={best_return['grid_count']}, grid_spacing_atr={best_return['grid_spacing_atr']}")
    print(f"  Return: {best_return['return_pct']:.2f}%")
    
    print(f"\n[Best Win Rate]")
    print(f"  {best_winrate['description']}")
    print(f"  Config: grid_count={best_winrate['grid_count']}, grid_spacing_atr={best_winrate['grid_spacing_atr']}")
    print(f"  Win Rate: {best_winrate['win_rate']:.2f}%")
    
    print(f"\n[Best Risk-Adjusted (Sharpe)]")
    print(f"  {best_sharpe['description']}")
    print(f"  Config: grid_count={best_sharpe['grid_count']}, grid_spacing_atr={best_sharpe['grid_spacing_atr']}")
    print(f"  Sharpe: {best_sharpe['sharpe_ratio']:.2f}")
    
    # 5. 保存结果
    csv_file = 'backtest/grid_optimization_results.csv'
    df_results.to_csv(csv_file, index=False)
    print(f"\n[Results] Saved to {csv_file}")
    
    print("\n" + "="*80)
    
    return df_results


if __name__ == '__main__':
    results = optimize_grid_params()
