"""
自适应回测系统 - Adaptive Backtest System（实验性工具）

⚠️ 重要提示：
这是一个实验性工具，用于测试独立的自适应策略逻辑。

生产环境验证请使用：
- trading_bots/backtest_engine.py 的 run_production_backtest()
- 生产级回测会调用真实的 StrategyScheduler 逻辑
- 确保回测结果能反映实际运行表现

实验性功能：
- 实时检测市场状态（趋势市/震荡市/高波动市）
- 动态切换策略（Trend Following / Grid Trading / Mean Reversion）
- 对比固定策略 vs 自适应策略的表现

生产级回测使用方法：
参见 scripts/test_production_backtest.py 获取完整示例

Author: AI Assistant
Date: 2025-11-18
Updated: 2025-11-19 (标记为实验性工具)
"""

import sys
sys.path.append('c:/Users/cair1/Desktop/HT/Headache_trade')

from typing import Dict, Optional, List
import pandas as pd
import numpy as np

from headache_trade.ai.regime_detector import MarketRegimeDetector, MarketRegime
from headache_trade.core.data_manager import DataManager
from headache_trade.backtest.report import BacktestReport

# 导入策略
from ..strategies import (
    MeanReversionStrategy,
    MomentumStrategy,
    GridTradingStrategy,
    TrendFollowingStrategy
)


class AdaptiveBacktestSystem:
    """
    自适应回测系统
    
    核心逻辑：
    1. 滚动窗口检测市场状态（每N根K线）
    2. 根据状态选择最优策略：
       - Trending + UP   → Trend Following (LONG)
       - Trending + DOWN → Trend Following (SHORT)
       - Ranging         → Grid Trading
       - Volatile        → Mean Reversion (快进快出)
    3. 策略切换时平掉现有持仓
    """
    
    def __init__(
        self,
        regime_detection_window: int = 100,  # 市场状态检测窗口
        regime_update_interval: int = 50,    # 多少根K线更新一次状态（从20增加到50）
        confirmation_window: int = 3,        # 需要连续N次确认才切换策略
        switch_cooldown: int = 50,           # 策略切换冷却期（根K线数）
        trend_lock_threshold: float = 50.0   # ADX超过此值时锁定策略不切换
    ):
        """
        初始化自适应回测系统
        
        Args:
            regime_detection_window: 用于检测市场状态的K线数量
            regime_update_interval: 每隔多少根K线重新检测市场状态
            confirmation_window: 连续N次检测到相同策略才切换
            switch_cooldown: 策略切换后的冷却期（K线数）
            trend_lock_threshold: ADX超过此值时锁定当前策略
        """
        self.regime_detector = MarketRegimeDetector()
        self.data_manager = DataManager()
        self.report_generator = BacktestReport()
        
        self.regime_detection_window = regime_detection_window
        self.regime_update_interval = regime_update_interval
        self.confirmation_window = confirmation_window
        self.switch_cooldown = switch_cooldown
        self.trend_lock_threshold = trend_lock_threshold
        
        self.regime_history = []  # 记录历史市场状态
        self.strategy_switches = []  # 记录策略切换历史
        self.strategy_confirmations = []  # 记录策略确认历史（用于确认机制）
        self.last_switch_candle = -switch_cooldown  # 上次切换的K线索引
    
    def _select_strategy(self, regime: MarketRegime) -> str:
        """
        根据市场状态选择策略
        
        Args:
            regime: MarketRegime对象
            
        Returns:
            策略名称
        """
        if regime.regime == 'trending':
            if regime.adx_value >= 50:  # 超强趋势
                return 'trend_following'
            elif regime.trend_direction in ['up', 'down']:
                return 'trend_following'
            else:
                return 'momentum'
        
        elif regime.regime == 'ranging':
            if regime.range_strength > 0.7:
                return 'grid'
            else:
                return 'mean_reversion'
        
        elif regime.regime == 'volatile':
            return 'mean_reversion'  # 高波动用均值回归快进快出
        
        else:  # neutral
            return 'trend_following'  # 默认使用趋势跟随
    
    def run_adaptive_backtest(
        self,
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT',
        timeframe: str = '15m',
        days: int = 7,
        initial_capital: float = 10000,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005
    ) -> Dict:
        """
        运行自适应回测
        
        Args:
            exchange: 交易所
            symbol: 交易对
            timeframe: 时间周期
            days: 天数
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage_rate: 滑点率
            
        Returns:
            回测结果字典
        """
        
        print("\n" + "="*80)
        print(" "*25 + "ADAPTIVE BACKTEST SYSTEM")
        print("="*80)
        
        # 1. 获取数据
        print("\n[Step 1/5] Loading historical data...")
        df = self.data_manager.fetch_data(exchange, symbol, timeframe, days)
        print(f"  Loaded {len(df)} candles from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        
        # 2. 初始化回测引擎（用于计算持仓和P&L）
        print("\n[Step 2/5] Initializing backtest engine...")
        
        capital = initial_capital
        position = None
        trades = []
        equity_curve = []
        
        current_strategy = None
        current_strategy_instance = None
        
        # 3. 逐K线回测
        print("\n[Step 3/5] Running adaptive backtest...")
        print(f"  Configuration: update_interval={self.regime_update_interval}, "
              f"confirmation_window={self.confirmation_window}, "
              f"cooldown={self.switch_cooldown}")
        
        for i in range(self.regime_detection_window, len(df)):
            # 检查是否需要更新市场状态
            if i % self.regime_update_interval == 0 or current_strategy is None:
                # 使用过去N根K线检测市场状态
                window_data = df.iloc[i - self.regime_detection_window:i].copy()
                regime = self.regime_detector.detect_regime(window_data)
                
                # 选择策略
                selected_strategy = self._select_strategy(regime)
                
                # 记录市场状态
                self.regime_history.append({
                    'timestamp': df['timestamp'].iloc[i],
                    'index': i,
                    'regime': regime.regime,
                    'trend_direction': regime.trend_direction,
                    'adx': regime.adx_value,
                    'confidence': regime.confidence,
                    'selected_strategy': selected_strategy
                })
                
                # 添加到确认列表
                self.strategy_confirmations.append(selected_strategy)
                # 只保留最近confirmation_window个确认
                if len(self.strategy_confirmations) > self.confirmation_window:
                    self.strategy_confirmations.pop(0)
                
                # === 新增：策略切换决策逻辑 ===
                should_switch = False
                switch_reason = None
                
                if current_strategy is None:
                    # 首次初始化
                    should_switch = True
                    switch_reason = "Initial Setup"
                    
                elif current_strategy != selected_strategy:
                    # 1. 检查冷却期
                    candles_since_last_switch = i - self.last_switch_candle
                    if candles_since_last_switch < self.switch_cooldown:
                        switch_reason = f"Cooldown ({candles_since_last_switch}/{self.switch_cooldown})"
                        should_switch = False
                    
                    # 2. 检查趋势锁定（强趋势时不切换）
                    elif regime.adx_value >= self.trend_lock_threshold:
                        switch_reason = f"Trend Lock (ADX={regime.adx_value:.1f})"
                        should_switch = False
                    
                    # 3. 检查确认窗口（需要连续N次推荐相同策略）
                    elif len(self.strategy_confirmations) >= self.confirmation_window:
                        # 检查最近N次是否都推荐同一个策略
                        if all(s == selected_strategy for s in self.strategy_confirmations[-self.confirmation_window:]):
                            should_switch = True
                            switch_reason = f"Confirmed ({self.confirmation_window}x)"
                        else:
                            unique_strategies = set(self.strategy_confirmations[-self.confirmation_window:])
                            switch_reason = f"Not Confirmed ({len(unique_strategies)} strategies)"
                            should_switch = False
                    else:
                        switch_reason = f"Insufficient Confirmations ({len(self.strategy_confirmations)}/{self.confirmation_window})"
                        should_switch = False
                
                # 执行策略切换
                if should_switch and current_strategy != selected_strategy:
                    # 平掉现有持仓
                    if position is not None:
                        close_price = df['close'].iloc[i]
                        close_time = df['timestamp'].iloc[i]
                        
                        # 计算P&L
                        if position['side'] == 'LONG':
                            pnl = (close_price - position['entry_price']) * position['size']
                        else:  # SHORT
                            pnl = (position['entry_price'] - close_price) * position['size']
                        
                        # 扣除手续费
                        commission = close_price * position['size'] * commission_rate
                        pnl -= commission
                        pnl -= position['entry_commission']
                        
                        capital += pnl
                        
                        trades.append({
                            'entry_time': position['entry_time'],
                            'exit_time': close_time,
                            'side': position['side'],
                            'entry_price': position['entry_price'],
                            'exit_price': close_price,
                            'size': position['size'],
                            'pnl': pnl,
                            'return_pct': (pnl / (position['entry_price'] * position['size'])) * 100,
                            'strategy': position['strategy'],
                            'exit_reason': 'Strategy Switch'
                        })
                        
                        position = None
                    
                    # 记录策略切换
                    self.strategy_switches.append({
                        'timestamp': df['timestamp'].iloc[i],
                        'index': i,
                        'from_strategy': current_strategy,
                        'to_strategy': selected_strategy,
                        'regime': regime.regime,
                        'adx': regime.adx_value,
                        'reason': switch_reason
                    })
                    
                    # 更新当前策略
                    current_strategy = selected_strategy
                    self.last_switch_candle = i
                    
                    # 每次切换时创建新实例
                    if selected_strategy == 'trend_following':
                        current_strategy_instance = TrendFollowingStrategy()
                    elif selected_strategy == 'grid':
                        current_strategy_instance = GridTradingStrategy(grid_count=15, grid_spacing_atr=0.5)
                    elif selected_strategy == 'mean_reversion':
                        current_strategy_instance = MeanReversionStrategy()
                    else:
                        current_strategy_instance = MomentumStrategy()
                    
                    print(f"  [{i}/{len(df)}] SWITCH: {regime.regime.upper():8s} | "
                          f"ADX: {regime.adx_value:5.1f} | "
                          f"{current_strategy:20s} | Reason: {switch_reason}")
                
                elif not should_switch and switch_reason and current_strategy:
                    # 输出未切换原因（每50根K线输出一次，避免刷屏）
                    if i % 50 == 0:
                        print(f"  [{i}/{len(df)}] HOLD:   {regime.regime.upper():8s} | "
                              f"ADX: {regime.adx_value:5.1f} | "
                              f"{current_strategy:20s} | "
                              f"Blocked: {switch_reason}")
            
            # 生成交易信号
            current_price_data = df.iloc[:i+1].copy()
            signal = current_strategy_instance.generate_signal(current_price_data, position)
            
            # 执行交易
            current_price = df['close'].iloc[i]
            current_time = df['timestamp'].iloc[i]
            
            signal_type_str = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
            
            if position is None and signal_type_str in ['LONG', 'SHORT']:
                # 开仓
                position_value = capital * 0.95  # 使用95%资金
                position_size = position_value / current_price
                entry_commission = current_price * position_size * commission_rate
                
                position = {
                    'side': signal_type_str,
                    'entry_price': current_price * (1 + slippage_rate if signal_type_str == 'LONG' else 1 - slippage_rate),
                    'entry_time': current_time,
                    'size': position_size,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'strategy': current_strategy,
                    'entry_commission': entry_commission
                }
            
            elif position is not None:
                # 检查止损止盈
                should_close = False
                exit_reason = None
                
                if position['side'] == 'LONG':
                    if position['stop_loss'] and current_price <= position['stop_loss']:
                        should_close = True
                        exit_reason = 'Stop Loss'
                    elif position['take_profit'] and current_price >= position['take_profit']:
                        should_close = True
                        exit_reason = 'Take Profit'
                else:  # SHORT
                    if position['stop_loss'] and current_price >= position['stop_loss']:
                        should_close = True
                        exit_reason = 'Stop Loss'
                    elif position['take_profit'] and current_price <= position['take_profit']:
                        should_close = True
                        exit_reason = 'Take Profit'
                
                # 检查策略退出信号
                if signal_type_str == 'CLOSE':
                    should_close = True
                    exit_reason = 'Strategy Exit'
                
                if should_close:
                    # 平仓
                    close_price = current_price
                    
                    if position['side'] == 'LONG':
                        pnl = (close_price - position['entry_price']) * position['size']
                    else:
                        pnl = (position['entry_price'] - close_price) * position['size']
                    
                    commission = close_price * position['size'] * commission_rate
                    pnl -= commission
                    pnl -= position['entry_commission']
                    
                    capital += pnl
                    
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': current_time,
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': close_price,
                        'size': position['size'],
                        'pnl': pnl,
                        'return_pct': (pnl / (position['entry_price'] * position['size'])) * 100,
                        'strategy': position['strategy'],
                        'exit_reason': exit_reason
                    })
                    
                    position = None
            
            # 记录权益曲线
            current_equity = capital
            if position is not None:
                if position['side'] == 'LONG':
                    unrealized_pnl = (current_price - position['entry_price']) * position['size']
                else:
                    unrealized_pnl = (position['entry_price'] - current_price) * position['size']
                current_equity += unrealized_pnl
            
            equity_curve.append({
                'timestamp': current_time,
                'equity': current_equity,
                'strategy': current_strategy
            })
        
        # 4. 计算统计指标
        print("\n[Step 4/5] Calculating performance metrics...")
        
        df_trades = pd.DataFrame(trades)
        total_return_pct = ((capital - initial_capital) / initial_capital) * 100
        
        if len(trades) > 0:
            winning_trades = df_trades[df_trades['pnl'] > 0]
            losing_trades = df_trades[df_trades['pnl'] <= 0]
            
            win_rate = (len(winning_trades) / len(trades)) * 100
            avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
            avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
            
            total_wins = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
            total_losses = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        # 计算最大回撤
        df_equity = pd.DataFrame(equity_curve)
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['peak']) / df_equity['peak'] * 100
        max_drawdown_pct = df_equity['drawdown'].min()
        
        # 5. 生成报告
        print("\n[Step 5/5] Generating adaptive strategy report...")
        
        results = {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_pnl': capital - initial_capital,
            'total_return_pct': total_return_pct,
            'total_trades': len(trades),
            'winning_trades': len(df_trades[df_trades['pnl'] > 0]) if len(trades) > 0 else 0,
            'losing_trades': len(df_trades[df_trades['pnl'] <= 0]) if len(trades) > 0 else 0,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown_pct,
            'trades': df_trades,
            'equity_curve': df_equity,
            'regime_history': pd.DataFrame(self.regime_history),
            'strategy_switches': pd.DataFrame(self.strategy_switches),
            'strategy_distribution': df_trades.groupby('strategy').size().to_dict() if len(trades) > 0 else {}
        }
        
        self._print_report(results)
        
        return results
    
    def _print_report(self, results: Dict):
        """打印自适应策略报告"""
        
        print("\n" + "="*80)
        print("ADAPTIVE STRATEGY BACKTEST RESULTS")
        print("="*80)
        
        print(f"\n[Performance Metrics]")
        print(f"  Initial Capital:     ${results['initial_capital']:,.2f}")
        print(f"  Final Capital:       ${results['final_capital']:,.2f}")
        print(f"  Total P&L:           ${results['total_pnl']:,.2f}")
        print(f"  Total Return:        {results['total_return_pct']:.2f}%")
        
        print(f"\n[Trading Statistics]")
        print(f"  Total Trades:        {results['total_trades']}")
        print(f"  Winning Trades:      {results['winning_trades']}")
        print(f"  Losing Trades:       {results['losing_trades']}")
        print(f"  Win Rate:            {results['win_rate']:.2f}%")
        print(f"  Profit Factor:       {results['profit_factor']:.2f}")
        
        print(f"\n[Risk Metrics]")
        print(f"  Max Drawdown:        {results['max_drawdown_pct']:.2f}%")
        print(f"  Avg Win:             ${results['avg_win']:.2f}")
        print(f"  Avg Loss:            ${results['avg_loss']:.2f}")
        
        print(f"\n[Strategy Distribution]")
        for strategy, count in results['strategy_distribution'].items():
            pct = (count / results['total_trades']) * 100 if results['total_trades'] > 0 else 0
            print(f"  {strategy:20s}: {count:3d} trades ({pct:5.1f}%)")
        
        print(f"\n[Strategy Switches]")
        print(f"  Total Switches:      {len(self.strategy_switches)}")
        
        print("\n" + "="*80)
    
    def compare_with_fixed_strategy(
        self,
        fixed_strategy: str = 'trend_following',
        **backtest_params
    ):
        """
        对比自适应策略 vs 固定策略
        
        Args:
            fixed_strategy: 固定策略名称
            **backtest_params: 回测参数
        """
        
        print("\n" + "="*80)
        print("ADAPTIVE vs FIXED STRATEGY COMPARISON")
        print("="*80)
        
        # 运行自适应回测
        print("\n>>> Running ADAPTIVE strategy backtest...")
        adaptive_results = self.run_adaptive_backtest(**backtest_params)
        
        # 运行固定策略回测
        print(f"\n>>> Running FIXED strategy backtest ({fixed_strategy})...")
        
        from backtest.backtest_system import BacktestSystem
        system = BacktestSystem()
        fixed_result_dict = system.run_strategy(
            strategy_key=fixed_strategy,
            exchange=backtest_params.get('exchange', 'binance'),
            symbol=backtest_params.get('symbol', 'BTC/USDT'),
            timeframe=backtest_params.get('timeframe', '15m'),
            days=backtest_params.get('days', 7),
            initial_capital=backtest_params.get('initial_capital', 10000),
            save_report=False
        )
        
        fixed_results = fixed_result_dict['results']
        
        # 对比结果
        print("\n" + "="*80)
        print("COMPARISON RESULTS")
        print("="*80)
        
        print(f"\n{'Metric':<25} {'Adaptive':>15} {'Fixed':>15} {'Difference':>15}")
        print("-" * 80)
        
        metrics = [
            ('Total Return', 'total_return_pct', '%'),
            ('Total P&L', 'total_pnl', '$'),
            ('Total Trades', 'total_trades', ''),
            ('Win Rate', 'win_rate', '%'),
            ('Profit Factor', 'profit_factor', ''),
            ('Max Drawdown', 'max_drawdown_pct', '%')
        ]
        
        for label, key, unit in metrics:
            adaptive_val = adaptive_results[key]
            fixed_val = fixed_results[key]
            diff = adaptive_val - fixed_val
            
            if unit == '%':
                print(f"{label:<25} {adaptive_val:>14.2f}% {fixed_val:>14.2f}% {diff:>+14.2f}%")
            elif unit == '$':
                print(f"{label:<25} ${adaptive_val:>13,.2f} ${fixed_val:>13,.2f} ${diff:>+13,.2f}")
            else:
                print(f"{label:<25} {adaptive_val:>15.0f} {fixed_val:>15.0f} {diff:>+15.0f}")
        
        print("\n" + "="*80)
        
        # 判断优胜者
        if adaptive_results['total_return_pct'] > fixed_results['total_return_pct']:
            winner = "ADAPTIVE"
            improvement = adaptive_results['total_return_pct'] - fixed_results['total_return_pct']
            print(f"\n[Winner] {winner} Strategy (improved by {improvement:.2f}%)")
        else:
            winner = "FIXED"
            improvement = fixed_results['total_return_pct'] - adaptive_results['total_return_pct']
            print(f"\n[Winner] {winner} Strategy ({fixed_strategy}) (better by {improvement:.2f}%)")
        
        print("="*80 + "\n")


def main():
    """主测试函数"""
    
    # 创建自适应回测系统（使用优化后的参数）
    adaptive_system = AdaptiveBacktestSystem(
        regime_detection_window=100,      # 检测窗口
        regime_update_interval=50,        # 更新间隔：20 → 50（减少检测频率）
        confirmation_window=3,            # 确认窗口：需要3次连续确认
        switch_cooldown=50,               # 冷却期：50根K线
        trend_lock_threshold=50.0         # 趋势锁定：ADX>50时不切换
    )
    
    # 运行对比测试
    adaptive_system.compare_with_fixed_strategy(
        fixed_strategy='trend',  # 使用Trend Following作为基准
        exchange='binance',
        symbol='BTC/USDT',
        timeframe='15m',
        days=7,
        initial_capital=10000
    )


if __name__ == '__main__':
    main()
