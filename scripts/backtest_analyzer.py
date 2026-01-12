"""
回测性能分析工具
计算各种性能指标并生成详细报告
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List
import json


class BacktestAnalyzer:
    """回测性能分析器"""
    
    def __init__(self, results: Dict):
        """
        初始化分析器
        
        Args:
            results: 回测结果字典（来自BacktestEngine.get_results()）
        """
        self.results = results
        self.trades_df = pd.DataFrame(results['trades']) if results['trades'] else pd.DataFrame()
        self.equity_df = pd.DataFrame(results['equity_curve']) if results['equity_curve'] else pd.DataFrame()
        
    def calculate_metrics(self) -> Dict:
        """计算所有性能指标"""
        if self.trades_df.empty:
            return self._empty_metrics()
        
        metrics = {}
        
        # 基础指标
        metrics.update(self._calculate_basic_metrics())
        
        # 收益指标
        metrics.update(self._calculate_return_metrics())
        
        # 交易质量指标
        metrics.update(self._calculate_quality_metrics())
        
        # 风险指标
        metrics.update(self._calculate_risk_metrics())
        
        return metrics
    
    def _empty_metrics(self) -> Dict:
        """返回空指标"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'profit_loss_ratio': 0,
            'expectancy': 0,
            'total_return_pct': 0,
            'total_return_usdt': 0,
            'max_profit_pct': 0,
            'max_loss_pct': 0,
            'max_profit_usdt': 0,
            'max_loss_usdt': 0,
            'total_profit_usdt': 0,
            'total_loss_usdt': 0,
            'profit_factor': 0,
            'avg_holding_time_min': 0,
            'avg_holding_time_hours': 0,
            'avg_trades_per_day': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'max_drawdown_pct': 0,
            'max_drawdown_usdt': 0,
            'sharpe_ratio': 0,
            'calmar_ratio': 0,
            'stop_loss_rate': 0
        }
    
    def _calculate_basic_metrics(self) -> Dict:
        """计算基础指标"""
        winning_trades = self.trades_df[self.trades_df['pnl_pct'] > 0]
        losing_trades = self.trades_df[self.trades_df['pnl_pct'] <= 0]
        
        avg_profit = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
        avg_loss = abs(losing_trades['pnl_pct'].mean()) if len(losing_trades) > 0 else 0
        
        total_wins = len(winning_trades)
        total_losses = len(losing_trades)
        total_trades = len(self.trades_df)
        
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        # 盈亏比
        profit_loss_ratio = (avg_profit / avg_loss) if avg_loss > 0 else 0
        
        # 期望值 = 胜率 × 平均盈利 - 败率 × 平均亏损
        expectancy = (win_rate / 100) * avg_profit - ((100 - win_rate) / 100) * avg_loss
        
        return {
            'total_trades': total_trades,
            'winning_trades': total_wins,
            'losing_trades': total_losses,
            'win_rate': round(win_rate, 2),
            'avg_profit': round(avg_profit, 4),
            'avg_loss': round(avg_loss, 4),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'expectancy': round(expectancy, 4)
        }
    
    def _calculate_return_metrics(self) -> Dict:
        """计算收益指标"""
        initial = self.results['initial_balance']
        final = self.results['final_balance']
        total_return = ((final - initial) / initial) * 100
        
        # 最大单笔盈利/亏损
        max_profit_pct = self.trades_df['pnl_pct'].max() if not self.trades_df.empty else 0
        max_loss_pct = self.trades_df['pnl_pct'].min() if not self.trades_df.empty else 0
        
        max_profit_usdt = self.trades_df['pnl_usdt'].max() if not self.trades_df.empty else 0
        max_loss_usdt = self.trades_df['pnl_usdt'].min() if not self.trades_df.empty else 0
        
        # 盈利因子 = 总盈利 / 总亏损
        total_profit = self.trades_df[self.trades_df['pnl_usdt'] > 0]['pnl_usdt'].sum() if not self.trades_df.empty else 0
        total_loss = abs(self.trades_df[self.trades_df['pnl_usdt'] < 0]['pnl_usdt'].sum()) if not self.trades_df.empty else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        # 计算总资金费率成本
        total_funding_fee_pct = 0
        if 'funding_fee_pct' in self.trades_df.columns:
            total_funding_fee_pct = self.trades_df['funding_fee_pct'].sum()
        
        return {
            'total_return_pct': round(total_return, 2),
            'total_return_usdt': round(final - initial, 2),
            'max_profit_pct': round(max_profit_pct, 2),
            'max_loss_pct': round(max_loss_pct, 2),
            'max_profit_usdt': round(max_profit_usdt, 2),
            'max_loss_usdt': round(max_loss_usdt, 2),
            'total_profit_usdt': round(total_profit, 2),
            'total_loss_usdt': round(total_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'total_funding_fee_pct': round(total_funding_fee_pct, 4)
        }
    
    def _calculate_quality_metrics(self) -> Dict:
        """计算交易质量指标"""
        if self.trades_df.empty or self.equity_df.empty:
            return {
                'avg_holding_time_min': 0,
                'avg_trades_per_day': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0
            }
        
        # 平均持仓时间
        avg_holding_time = self.trades_df['holding_time_min'].mean()
        
        # 交易频率（笔/天）
        if len(self.equity_df) > 0:
            start_time = pd.to_datetime(self.equity_df['timestamp'].iloc[0])
            end_time = pd.to_datetime(self.equity_df['timestamp'].iloc[-1])
            days = (end_time - start_time).total_seconds() / 86400
            avg_trades_per_day = len(self.trades_df) / days if days > 0 else 0
        else:
            avg_trades_per_day = 0
        
        # 连续盈亏
        win_streak = 0
        loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for pnl in self.trades_df['pnl_pct']:
            if pnl > 0:
                win_streak += 1
                loss_streak = 0
                max_win_streak = max(max_win_streak, win_streak)
            else:
                loss_streak += 1
                win_streak = 0
                max_loss_streak = max(max_loss_streak, loss_streak)
        
        return {
            'avg_holding_time_min': round(avg_holding_time, 1),
            'avg_holding_time_hours': round(avg_holding_time / 60, 1),
            'avg_trades_per_day': round(avg_trades_per_day, 2),
            'max_consecutive_wins': max_win_streak,
            'max_consecutive_losses': max_loss_streak
        }
    
    def _calculate_risk_metrics(self) -> Dict:
        """计算风险指标"""
        if self.equity_df.empty:
            return {
                'max_drawdown_pct': 0,
                'max_drawdown_usdt': 0,
                'sharpe_ratio': 0,
                'calmar_ratio': 0
            }
        
        # 最大回撤
        equity_series = pd.Series(self.equity_df['equity'].values)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown_pct = abs(drawdown.min())
        max_drawdown_usdt = (equity_series - running_max).min()
        
        # 夏普比率（简化版，假设无风险利率=0）
        if len(self.trades_df) > 1:
            returns = self.trades_df['pnl_pct'].values
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 卡玛比率 = 年化收益率 / 最大回撤
        annual_return = self.results['total_return_pct']  # 简化，实际应该年化
        calmar_ratio = (annual_return / max_drawdown_pct) if max_drawdown_pct > 0 else 0
        
        # 止损触发率
        stop_loss_trades = len(self.trades_df[self.trades_df['exit_reason'] == '止损'])
        stop_loss_rate = (stop_loss_trades / len(self.trades_df) * 100) if len(self.trades_df) > 0 else 0
        
        return {
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'max_drawdown_usdt': round(max_drawdown_usdt, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'calmar_ratio': round(calmar_ratio, 2),
            'stop_loss_rate': round(stop_loss_rate, 2)
        }
    
    def generate_report(self, filepath: str = None) -> str:
        """
        生成回测报告
        
        Args:
            filepath: 如果指定，将报告保存到文件
            
        Returns:
            报告文本
        """
        metrics = self.calculate_metrics()
        
        report_lines = []
        
        # 标题
        report_lines.append("=" * 80)
        report_lines.append("交易策略回测报告".center(80))
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # 回测概况
        report_lines.append("📊 回测概况")
        report_lines.append("-" * 80)
        if not self.equity_df.empty:
            start_time = self.equity_df['timestamp'].iloc[0]
            end_time = self.equity_df['timestamp'].iloc[-1]
            report_lines.append(f"回测期间: {start_time} 至 {end_time}")
        report_lines.append(f"初始资金: {self.results['initial_balance']:.2f} USDT")
        report_lines.append(f"最终资金: {self.results['final_balance']:.2f} USDT")
        report_lines.append(f"总收益率: {metrics['total_return_pct']:+.2f}%")
        report_lines.append(f"总收益额: {metrics['total_return_usdt']:+.2f} USDT")
        report_lines.append(f"最大回撤: {metrics['max_drawdown_pct']:.2f}%")
        report_lines.append("")
        
        # 交易统计
        report_lines.append("📈 交易统计")
        report_lines.append("-" * 80)
        report_lines.append(f"总交易次数: {metrics['total_trades']} 笔")
        report_lines.append(f"盈利交易: {metrics['winning_trades']} 笔")
        report_lines.append(f"亏损交易: {metrics['losing_trades']} 笔")
        report_lines.append(f"胜率: {metrics['win_rate']:.2f}%")
        report_lines.append(f"平均盈利: +{metrics['avg_profit']:.2f}%")
        report_lines.append(f"平均亏损: -{metrics['avg_loss']:.2f}%")
        report_lines.append(f"盈亏比: {metrics['profit_loss_ratio']:.2f}:1")
        report_lines.append(f"期望值: {metrics['expectancy']:+.4f}%")
        report_lines.append(f"盈利因子: {metrics['profit_factor']:.2f}")
        report_lines.append("")
        
        # 收益分析
        report_lines.append("💰 收益分析")
        report_lines.append("-" * 80)
        report_lines.append(f"总盈利: +{metrics['total_profit_usdt']:.2f} USDT")
        report_lines.append(f"总亏损: -{metrics['total_loss_usdt']:.2f} USDT")
        report_lines.append(f"最大单笔盈利: +{metrics['max_profit_pct']:.2f}% ({metrics['max_profit_usdt']:+.2f} USDT)")
        report_lines.append(f"最大单笔亏损: {metrics['max_loss_pct']:.2f}% ({metrics['max_loss_usdt']:+.2f} USDT)")
        if 'total_funding_fee_pct' in metrics:
            report_lines.append(f"总资金费率成本: {metrics['total_funding_fee_pct']:.4f}%")
        report_lines.append("")
        
        # 交易质量
        report_lines.append("⚡ 交易质量")
        report_lines.append("-" * 80)
        report_lines.append(f"平均持仓时间: {metrics['avg_holding_time_hours']:.1f} 小时 ({metrics['avg_holding_time_min']:.1f} 分钟)")
        report_lines.append(f"交易频率: {metrics['avg_trades_per_day']:.2f} 笔/天")
        report_lines.append(f"最长连胜: {metrics['max_consecutive_wins']} 笔")
        report_lines.append(f"最长连败: {metrics['max_consecutive_losses']} 笔")
        report_lines.append("")
        
        # 风险指标
        report_lines.append("⚠️ 风险指标")
        report_lines.append("-" * 80)
        report_lines.append(f"最大回撤: {metrics['max_drawdown_pct']:.2f}% ({metrics['max_drawdown_usdt']:.2f} USDT)")
        report_lines.append(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
        report_lines.append(f"卡玛比率: {metrics['calmar_ratio']:.2f}")
        report_lines.append(f"止损触发率: {metrics['stop_loss_rate']:.2f}%")
        report_lines.append("")
        
        # 交易明细（最近10笔）
        if not self.trades_df.empty:
            report_lines.append("📋 交易明细（最近10笔）")
            report_lines.append("-" * 80)
            report_lines.append(f"{'序号':<6}{'开仓时间':<20}{'平仓时间':<20}{'方向':<6}{'入场价':<12}{'出场价':<12}{'收益率':<10}{'原因':<10}")
            report_lines.append("-" * 80)
            
            recent_trades = self.trades_df.tail(10)
            for idx, trade in enumerate(recent_trades.to_dict('records'), 1):
                side_cn = '多' if trade['side'] == 'long' else '空'
                pnl_str = f"{trade['pnl_pct']:+.2f}%"
                report_lines.append(
                    f"{idx:<6}"
                    f"{trade['entry_time']:<20}"
                    f"{trade['exit_time']:<20}"
                    f"{side_cn:<6}"
                    f"{trade['entry_price']:<12.2f}"
                    f"{trade['exit_price']:<12.2f}"
                    f"{pnl_str:<10}"
                    f"{trade['exit_reason']:<10}"
                )
            report_lines.append("")
        
        # 结论
        report_lines.append("=" * 80)
        report_lines.append("🎯 总结")
        report_lines.append("-" * 80)
        
        # 评估策略质量
        if metrics['expectancy'] > 0.1:
            verdict = "✅ 策略具有正期望值，值得考虑"
        elif metrics['expectancy'] > 0:
            verdict = "⚠️ 策略期望值接近盈亏平衡，需要优化"
        else:
            verdict = "❌ 策略期望值为负，需要重大调整"
        
        report_lines.append(verdict)
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        # 保存到文件
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"\n✅ 报告已保存至: {filepath}")
        
        return report_text
    
    def compare_with_baseline(self, baseline_metrics: Dict) -> str:
        """
        与基准策略对比
        
        Args:
            baseline_metrics: 基准策略的性能指标
            
        Returns:
            对比报告文本
        """
        current_metrics = self.calculate_metrics()
        
        comparison = []
        comparison.append("\n" + "=" * 80)
        comparison.append("策略对比分析".center(80))
        comparison.append("=" * 80)
        comparison.append("")
        comparison.append(f"{'指标':<25}{'基准策略':<20}{'当前策略':<20}{'变化':<15}")
        comparison.append("-" * 80)
        
        # 定义要对比的指标
        metrics_to_compare = [
            ('avg_trades_per_day', '交易频率 (笔/天)'),
            ('win_rate', '胜率 (%)'),
            ('profit_loss_ratio', '盈亏比'),
            ('expectancy', '期望值 (%)'),
            ('total_return_pct', '总收益率 (%)'),
            ('max_drawdown_pct', '最大回撤 (%)'),
            ('sharpe_ratio', '夏普比率'),
        ]
        
        for key, label in metrics_to_compare:
            baseline_val = baseline_metrics.get(key, 0)
            current_val = current_metrics.get(key, 0)
            
            # 计算变化
            if baseline_val != 0:
                change_pct = ((current_val - baseline_val) / abs(baseline_val)) * 100
                change_str = f"{change_pct:+.1f}%"
            else:
                change_str = "N/A"
            
            comparison.append(
                f"{label:<25}"
                f"{baseline_val:<20.2f}"
                f"{current_val:<20.2f}"
                f"{change_str:<15}"
            )
        
        comparison.append("=" * 80)
        
        return "\n".join(comparison)


if __name__ == '__main__':
    print("回测性能分析工具")
    print("请使用 backtest_runner.py 运行回测")
