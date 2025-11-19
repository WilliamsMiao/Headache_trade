"""
回测引擎
用于验证策略在历史数据上的表现

主要功能：
1. run_production_backtest() - 测试生产级multi_strategy_bot逻辑（主要入口）
2. run_backtest() - 测试单一实验性策略（辅助功能）
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path

from ..strategies.base import BaseStrategy, SignalType


class BacktestEngine:
    """
    策略回测引擎
    
    主要功能：
    1. run_production_backtest() - 回测生产级StrategyScheduler逻辑（推荐使用）
    2. run_backtest() - 回测单一实验性策略
    """
    
    def __init__(self,
                 initial_capital: float = 10000.0,
                 commission_rate: float = 0.001,
                 slippage_rate: float = 0.0005):
        
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        
        # 回测状态
        self.capital = initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self.current_position = None
        
        # 生产级组件（用于production backtest）
        self.scheduler = None
        self.strategy_switches = []  # 记录策略切换历史
    
    def run_production_backtest(self,
                               scheduler,  # StrategyScheduler实例
                               price_data: pd.DataFrame,
                               start_date: Optional[str] = None,
                               end_date: Optional[str] = None) -> Dict:
        """
        运行生产级回测（主要入口）
        
        测试StrategyScheduler的真实决策逻辑，包括：
        - AI + 技术分析混合决策
        - 策略动态切换
        - 信号确认机制
        - 仓位管理
        
        Args:
            scheduler: StrategyScheduler实例（生产级策略调度器）
            price_data: 历史价格数据（必须包含 timestamp, open, high, low, close, volume）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            
        Returns:
            回测结果字典
        """
        
        # 重置状态
        self._reset()
        self.scheduler = scheduler
        self.strategy_switches = []
        
        # 过滤日期范围
        if start_date:
            price_data = price_data[price_data['timestamp'] >= start_date]
        if end_date:
            price_data = price_data[price_data['timestamp'] <= end_date]
        
        if len(price_data) < 50:
            raise ValueError("数据量太少，无法进行回测")
        
        print(f"\n{'='*60}")
        print(f"[PRODUCTION] Backtest: StrategyScheduler")
        print(f"   AI Enhancement: {'Enabled' if scheduler.use_ai else 'Disabled'}")
        print(f"   Strategy Pool: {list(scheduler.strategy_pool.keys())}")
        print(f"Time Range: {price_data['timestamp'].iloc[0]} ~ {price_data['timestamp'].iloc[-1]}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"{'='*60}\n")
        
        # 逐根K线模拟交易（与生产环境一致）
        for i in range(50, len(price_data)):
            # 获取当前时间点之前的数据
            historical_data = price_data.iloc[:i+1].copy()
            current_bar = historical_data.iloc[-1]
            
            # 记录权益
            equity = self._calculate_current_equity(current_bar['close'])
            self.equity_curve.append({
                'timestamp': current_bar['timestamp'],
                'equity': equity,
                'price': current_bar['close'],
                'active_strategy': scheduler.active_strategy_name or "None"
            })
            
            # 检查是否应该退出现有持仓
            if self.current_position:
                should_exit = scheduler.should_exit_position(
                    historical_data,
                    self.current_position['entry_price'],
                    self.current_position['side']
                )
                
                if should_exit or self._check_stop_loss_take_profit(current_bar):
                    self._close_position(current_bar, 'Strategy Exit')
            
            # 如果没有持仓，尝试生成新信号（调用生产级逻辑）
            if not self.current_position:
                # 关键：调用生产级StrategyScheduler的决策逻辑
                signal = scheduler.generate_trading_signal(
                    historical_data,
                    None
                )
                
                # 记录策略切换
                current_strategy = scheduler.active_strategy_name or "None"
                if not self.strategy_switches or self.strategy_switches[-1]['to_strategy'] != current_strategy:
                    self.strategy_switches.append({
                        'timestamp': current_bar['timestamp'],
                        'candle_index': i,
                        'from_strategy': self.strategy_switches[-1]['to_strategy'] if self.strategy_switches else 'None',
                        'to_strategy': current_strategy,
                        'market_price': current_bar['close']
                    })
                
                if signal:
                    # 使用生产级仓位计算
                    position_size = scheduler.calculate_position_size(self.capital, signal)
                    
                    if position_size > 0:
                        self._open_position(current_bar, signal, position_size)
        
        # 如果最后还有持仓，平仓
        if self.current_position:
            last_bar = price_data.iloc[-1]
            self._close_position(last_bar, 'End of Backtest')
        
        # 计算回测指标
        results = self._calculate_metrics(price_data)
        
        # 添加生产级特有信息
        results['backtest_type'] = 'production'
        results['scheduler_info'] = {
            'ai_enabled': scheduler.use_ai,
            'strategy_pool': list(scheduler.strategy_pool.keys()),
            'total_switches': len(self.strategy_switches),
            'switch_history': self.strategy_switches,
            'final_strategy': scheduler.active_strategy_name or "None"
        }
        
        # 获取调度器状态
        scheduler_status = scheduler.get_scheduler_status()
        results['strategy_performance'] = scheduler_status.get('strategy_performance', {})
        
        # 打印结果
        self._print_production_results(results)
        
        return results
        
    def run_backtest(self,
                    strategy: BaseStrategy,
                    price_data: pd.DataFrame,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Dict:
        """
        运行单策略回测（实验性策略测试）
        
        用于测试实验性单一策略，不涉及策略调度逻辑。
        生产环境验证请使用 run_production_backtest()。
        
        Args:
            strategy: 策略实例
            price_data: 历史价格数据（必须包含 timestamp, open, high, low, close, volume）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            
        Returns:
            回测结果字典
        """
        
        # 重置状态
        self._reset()
        
        # 过滤日期范围
        if start_date:
            price_data = price_data[price_data['timestamp'] >= start_date]
        if end_date:
            price_data = price_data[price_data['timestamp'] <= end_date]
        
        if len(price_data) < 50:
            raise ValueError("数据量太少，无法进行回测")
        
        print(f"\n{'='*60}")
        print(f"[EXPERIMENTAL] Backtest: {strategy.name}")
        print(f"   WARNING: This is single-strategy backtest, no strategy scheduling")
        print(f"   WARNING: Use run_production_backtest() for production validation")
        print(f"Time Range: {price_data['timestamp'].iloc[0]} ~ {price_data['timestamp'].iloc[-1]}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"{'='*60}\n")
        
        # 逐根K线模拟交易
        for i in range(50, len(price_data)):
            # 获取当前时间点之前的数据
            historical_data = price_data.iloc[:i+1].copy()
            current_bar = historical_data.iloc[-1]
            
            # 记录权益
            equity = self._calculate_current_equity(current_bar['close'])
            self.equity_curve.append({
                'timestamp': current_bar['timestamp'],
                'equity': equity,
                'price': current_bar['close']
            })
            
            # 检查是否应该退出现有持仓
            if self.current_position:
                should_exit = strategy.should_exit(
                    historical_data,
                    self.current_position['entry_price'],
                    self.current_position['side']
                )
                
                if should_exit or self._check_stop_loss_take_profit(current_bar):
                    self._close_position(current_bar, 'Strategy Exit')
            
            # 如果没有持仓，尝试生成新信号
            if not self.current_position:
                signal = strategy.generate_signal(historical_data, None)
                
                if signal:
                    # 计算仓位大小
                    position_size = strategy.calculate_position_size(self.capital, signal)
                    
                    if position_size > 0:
                        self._open_position(current_bar, signal, position_size)
        
        # 如果最后还有持仓，平仓
        if self.current_position:
            last_bar = price_data.iloc[-1]
            self._close_position(last_bar, 'End of Backtest')
        
        # 计算回测指标
        results = self._calculate_metrics(price_data)
        results['backtest_type'] = 'experimental'
        results['strategy_name'] = strategy.name
        
        # 打印结果
        self._print_results(results)
        
        return results
    
    def _reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self.current_position = None
    
    def _calculate_current_equity(self, current_price: float) -> float:
        """计算当前权益"""
        equity = self.capital
        
        if self.current_position:
            pos = self.current_position
            if pos['side'] == 'long':
                pnl = (current_price - pos['entry_price']) * pos['size']
            else:
                pnl = (pos['entry_price'] - current_price) * pos['size']
            
            equity += pnl
        
        return equity
    
    def _check_stop_loss_take_profit(self, current_bar: pd.Series) -> bool:
        """检查止损/止盈"""
        if not self.current_position:
            return False
        
        pos = self.current_position
        current_price = current_bar['close']
        
        if pos['side'] == 'long':
            # 做多：检查止损和止盈
            if pos['stop_loss'] and current_price <= pos['stop_loss']:
                print(f"   [SL] Stop loss triggered: {current_price:.2f} <= {pos['stop_loss']:.2f}")
                return True
            if pos['take_profit'] and current_price >= pos['take_profit']:
                print(f"   [TP] Take profit triggered: {current_price:.2f} >= {pos['take_profit']:.2f}")
                return True
        else:
            # 做空
            if pos['stop_loss'] and current_price >= pos['stop_loss']:
                print(f"   [SL] Stop loss triggered: {current_price:.2f} >= {pos['stop_loss']:.2f}")
                return True
            if pos['take_profit'] and current_price <= pos['take_profit']:
                print(f"   [TP] Take profit triggered: {current_price:.2f} <= {pos['take_profit']:.2f}")
                return True
        
        return False
    
    def _open_position(self, bar: pd.Series, signal, position_size: float):
        """开仓"""
        entry_price = bar['close']
        
        # 考虑滑点
        if signal.signal_type == SignalType.LONG:
            entry_price *= (1 + self.slippage_rate)
        else:
            entry_price *= (1 - self.slippage_rate)
        
        # 计算手续费
        position_value = entry_price * position_size
        commission = position_value * self.commission_rate
        
        # 检查资金是否足够
        required_capital = position_value + commission
        if required_capital > self.capital:
            print(f"   [Warning] Insufficient capital: need ${required_capital:,.2f}, available ${self.capital:,.2f}")
            return
        
        # 扣除手续费
        self.capital -= commission
        
        # 记录持仓
        self.current_position = {
            'entry_time': bar['timestamp'],
            'entry_price': entry_price,
            'size': position_size,
            'side': 'long' if signal.signal_type == SignalType.LONG else 'short',
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'commission_paid': commission,
            'metadata': signal.metadata
        }
        
        side_label = "LONG" if self.current_position['side'] == 'long' else "SHORT"
        print(f"\n[Open] {side_label} position")
        print(f"   Time: {bar['timestamp']}")
        print(f"   Price: ${entry_price:.2f}")
        print(f"   Size: {position_size:.4f}")
        print(f"   Value: ${position_value:,.2f}")
        print(f"   Commission: ${commission:.2f}")
        print(f"   Reason: {signal.metadata.get('reason', 'N/A')}")
    
    def _close_position(self, bar: pd.Series, reason: str):
        """平仓"""
        if not self.current_position:
            return
        
        pos = self.current_position
        exit_price = bar['close']
        
        # 考虑滑点
        if pos['side'] == 'long':
            exit_price *= (1 - self.slippage_rate)
        else:
            exit_price *= (1 + self.slippage_rate)
        
        # 计算盈亏
        if pos['side'] == 'long':
            pnl = (exit_price - pos['entry_price']) * pos['size']
        else:
            pnl = (pos['entry_price'] - exit_price) * pos['size']
        
        # 手续费
        position_value = exit_price * pos['size']
        commission = position_value * self.commission_rate
        
        # 净盈亏
        net_pnl = pnl - commission - pos['commission_paid']
        
        # 更新资金
        self.capital += net_pnl
        
        # 持仓时长
        if isinstance(pos['entry_time'], str):
            entry_time = pd.to_datetime(pos['entry_time'])
        else:
            entry_time = pos['entry_time']
        
        if isinstance(bar['timestamp'], str):
            exit_time = pd.to_datetime(bar['timestamp'])
        else:
            exit_time = bar['timestamp']
        
        hold_duration = (exit_time - entry_time).total_seconds() / 3600
        
        # 记录交易
        trade = {
            'entry_time': pos['entry_time'],
            'exit_time': bar['timestamp'],
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'size': pos['size'],
            'side': pos['side'],
            'pnl': pnl,
            'commission': commission + pos['commission_paid'],
            'net_pnl': net_pnl,
            'return_pct': (net_pnl / (pos['entry_price'] * pos['size'])) * 100,
            'hold_hours': hold_duration,
            'exit_reason': reason,
            'metadata': pos['metadata']
        }
        
        self.trades.append(trade)
        
        # 打印平仓信息
        pnl_sign = "+" if net_pnl > 0 else ""
        print(f"\n[Close] {pos['side'].upper()} position")
        print(f"   Time: {bar['timestamp']}")
        print(f"   Price: ${exit_price:.2f}")
        print(f"   P&L: {pnl_sign}${net_pnl:,.2f} ({trade['return_pct']:+.2f}%)")
        print(f"   Duration: {hold_duration:.1f} hours")
        print(f"   Reason: {reason}")
        
        # 清除持仓
        self.current_position = None
    
    def _calculate_metrics(self, price_data: pd.DataFrame) -> Dict:
        """计算回测指标"""
        
        if not self.trades:
            return {
                'error': '没有完成的交易',
                'total_trades': 0
            }
        
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)
        
        # 基本指标
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['net_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['net_pnl'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = trades_df['net_pnl'].sum()
        total_return = (total_pnl / self.initial_capital) * 100
        
        # 盈亏统计
        avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else np.inf
        
        # 最大回撤
        equity_series = equity_df['equity']
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax * 100
        max_drawdown = drawdown.min()
        
        # 夏普比率（简化版，假设无风险利率=0）
        returns = equity_series.pct_change().dropna()
        if len(returns) > 0 and returns.std() != 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # 年化
        else:
            sharpe_ratio = 0
        
        # 持仓时长统计
        avg_hold_hours = trades_df['hold_hours'].mean()
        
        # 回测时长
        start_date = price_data['timestamp'].iloc[0]
        end_date = price_data['timestamp'].iloc[-1]
        
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        backtest_days = (end_date - start_date).days
        
        return {
            # 基本信息
            'start_date': str(start_date),
            'end_date': str(end_date),
            'backtest_days': backtest_days,
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            
            # 交易统计
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            
            # 盈亏指标
            'total_pnl': total_pnl,
            'total_return_pct': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            
            # 风险指标
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            
            # 其他
            'avg_hold_hours': avg_hold_hours,
            'commission_rate': self.commission_rate,
            'slippage_rate': self.slippage_rate,
            
            # 详细数据
            'trades': trades_df.to_dict('records'),
            'equity_curve': equity_df.to_dict('records')
        }
    
    def _print_results(self, results: Dict):
        """Print backtest results"""
        
        if 'error' in results:
            print(f"\n[Error] {results['error']}")
            return
        
        backtest_type_label = "[EXPERIMENTAL]" if results.get('backtest_type') == 'experimental' else "Backtest"
        
        print(f"\n{'='*60}")
        print(f"{backtest_type_label} Results Summary")
        print(f"{'='*60}\n")
        
        print(f"[Period]")
        print(f"   Start: {results['start_date']}")
        print(f"   End: {results['end_date']}")
        print(f"   Days: {results['backtest_days']}\n")
        
        print(f"[Capital]")
        print(f"   Initial: ${results['initial_capital']:,.2f}")
        print(f"   Final: ${results['final_capital']:,.2f}")
        print(f"   P&L: ${results['total_pnl']:,.2f}")
        print(f"   Return: {results['total_return_pct']:+.2f}%\n")
        
        print(f"[Trading Statistics]")
        print(f"   Total Trades: {results['total_trades']}")
        print(f"   Winning: {results['winning_trades']}")
        print(f"   Losing: {results['losing_trades']}")
        print(f"   Win Rate: {results['win_rate']:.2f}%\n")
        
        print(f"[P&L Analysis]")
        print(f"   Avg Win: ${results['avg_win']:,.2f}")
        print(f"   Avg Loss: ${results['avg_loss']:,.2f}")
        print(f"   Profit Factor: {results['profit_factor']:.2f}\n")
        
        print(f"[Risk Metrics]")
        print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}\n")
        
        print(f"[Other]")
        print(f"   Avg Hold Time: {results['avg_hold_hours']:.1f} hours")
        print(f"   Commission Rate: {results['commission_rate']*100:.2f}%")
        print(f"   Slippage Rate: {results['slippage_rate']*100:.3f}%\n")
        
        print(f"{'='*60}")
    
    def _print_production_results(self, results: Dict):
        """Print production backtest results (with scheduler info)"""
        
        if 'error' in results:
            print(f"\n[Error] {results['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"[PRODUCTION] Backtest Results")
        print(f"{'='*60}\n")
        
        # Scheduler info
        scheduler_info = results.get('scheduler_info', {})
        print(f"[Scheduler Info]")
        print(f"   AI Enabled: {'Yes' if scheduler_info.get('ai_enabled') else 'No'}")
        print(f"   Strategy Pool: {', '.join(scheduler_info.get('strategy_pool', []))}")
        print(f"   Total Switches: {scheduler_info.get('total_switches', 0)}")
        print(f"   Final Strategy: {scheduler_info.get('final_strategy', 'Unknown')}\n")
        
        # Strategy switching history (show first 5 and last 5)
        switch_history = scheduler_info.get('switch_history', [])
        if switch_history:
            print(f"[Strategy Switches]")
            display_switches = switch_history[:5]
            if len(switch_history) > 10:
                print(f"   (Showing first 5 and last 5 of {len(switch_history)} switches)")
                display_switches = switch_history[:5] + switch_history[-5:]
            
            for switch in display_switches:
                print(f"   {switch['timestamp']} | {switch['from_strategy']} -> {switch['to_strategy']} @ ${switch['market_price']:.2f}")
            
            if len(switch_history) > 10:
                print(f"   ... ({len(switch_history) - 10} more switches)")
            print()
        
        # Strategy performance
        strategy_perf = results.get('strategy_performance', {})
        if strategy_perf:
            print(f"[Strategy Performance]")
            for strategy_name, perf in strategy_perf.items():
                print(f"   {strategy_name}:")
                print(f"      Trades: {perf.get('total_trades', 0)} | Win Rate: {perf.get('win_rate', 0):.1f}% | P&L: ${perf.get('total_pnl', 0):.2f}")
            print()
        
        print(f"[Period]")
        print(f"   Start: {results['start_date']}")
        print(f"   End: {results['end_date']}")
        print(f"   Days: {results['backtest_days']}\n")
        
        print(f"[Capital]")
        print(f"   Initial: ${results['initial_capital']:,.2f}")
        print(f"   Final: ${results['final_capital']:,.2f}")
        print(f"   P&L: ${results['total_pnl']:,.2f}")
        print(f"   Return: {results['total_return_pct']:+.2f}%\n")
        
        print(f"[Trading Statistics]")
        print(f"   Total Trades: {results['total_trades']}")
        print(f"   Winning: {results['winning_trades']}")
        print(f"   Losing: {results['losing_trades']}")
        print(f"   Win Rate: {results['win_rate']:.2f}%\n")
        
        print(f"[P&L Analysis]")
        print(f"   Avg Win: ${results['avg_win']:,.2f}")
        print(f"   Avg Loss: ${results['avg_loss']:,.2f}")
        print(f"   Profit Factor: {results['profit_factor']:.2f}\n")
        
        print(f"[Risk Metrics]")
        print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}\n")
        
        print(f"[Other]")
        print(f"   Avg Hold Time: {results['avg_hold_hours']:.1f} hours")
        print(f"   Commission Rate: {results['commission_rate']*100:.2f}%")
        print(f"   Slippage Rate: {results['slippage_rate']*100:.3f}%\n")
        
        print(f"{'='*60}")
    
    def export_results(self, results: Dict, output_dir: str = "backtest_results"):
        """Export backtest results"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export trade records
        if 'trades' in results:
            trades_df = pd.DataFrame(results['trades'])
            trades_file = output_path / f"trades_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False)
            print(f"Trade records exported: {trades_file}")
        
        # Export equity curve
        if 'equity_curve' in results:
            equity_df = pd.DataFrame(results['equity_curve'])
            equity_file = output_path / f"equity_curve_{timestamp}.csv"
            equity_df.to_csv(equity_file, index=False)
            print(f"Equity curve exported: {equity_file}")
        
        # Export summary data
        summary = {k: v for k, v in results.items() if k not in ['trades', 'equity_curve']}
        summary_file = output_path / f"summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        print(f"Summary data exported: {summary_file}")
        
        return {
            'trades_file': str(trades_file),
            'equity_file': str(equity_file),
            'summary_file': str(summary_file)
        }


def compare_strategies(results_list: List[Dict], strategy_names: List[str]):
    """Compare multiple strategy backtest results"""
    
    print(f"\n{'='*80}")
    print(f"Strategy Comparison")
    print(f"{'='*80}\n")
    
    # Create comparison table
    comparison_data = []
    
    for results, name in zip(results_list, strategy_names):
        if 'error' not in results:
            comparison_data.append({
                'Strategy': name,
                'Total Trades': results['total_trades'],
                'Win Rate': f"{results['win_rate']:.1f}%",
                'Total Return': f"{results['total_return_pct']:.2f}%",
                'Profit Factor': f"{results['profit_factor']:.2f}",
                'Max Drawdown': f"{results['max_drawdown_pct']:.2f}%",
                'Sharpe Ratio': f"{results['sharpe_ratio']:.2f}",
                'Avg Hold': f"{results['avg_hold_hours']:.1f}h"
            })
    
    if comparison_data:
        df = pd.DataFrame(comparison_data)
        print(df.to_string(index=False))
        print(f"\n{'='*80}")
    else:
        print("No strategy results to compare")
