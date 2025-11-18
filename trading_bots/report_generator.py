"""
回测报告生成器 - 标准化的回测报告
职责：生成统一格式的回测报告（文本、JSON、HTML）
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


class BacktestReport:
    """回测报告生成器"""
    
    def __init__(self, output_dir: str = 'backtest_results'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_report(
        self,
        strategy_name: str,
        results: Dict[str, Any],
        params: Dict[str, Any],
        data_info: Dict[str, Any],
        save: bool = True
    ) -> str:
        """
        生成完整的回测报告
        
        Args:
            strategy_name: 策略名称
            results: 回测结果
            params: 策略参数
            data_info: 数据信息
            save: 是否保存到文件
        
        Returns:
            报告文本
        """
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 生成文本报告
        report_lines = [
            "="*80,
            f"BACKTEST REPORT - {strategy_name}",
            "="*80,
            "",
            "STRATEGY INFORMATION",
            "-"*80,
            f"Strategy:        {strategy_name}",
            f"Test Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "DATA INFORMATION",
            "-"*80,
            f"Symbol:          {data_info.get('symbol', 'N/A')}",
            f"Timeframe:       {data_info.get('timeframe', 'N/A')}",
            f"Period:          {data_info.get('period', 'N/A')}",
            f"Total Candles:   {data_info.get('candles', 0):,}",
            "",
            "STRATEGY PARAMETERS",
            "-"*80,
        ]
        
        for key, value in params.items():
            report_lines.append(f"{key:20s} = {value}")
        
        report_lines.extend([
            "",
            "PERFORMANCE METRICS",
            "-"*80,
            f"Initial Capital:     ${results.get('initial_capital', 10000):,.2f}",
            f"Final Capital:       ${results.get('final_capital', 0):,.2f}",
            f"Total P&L:           ${results.get('total_pnl', 0):,.2f}",
            f"Total Return:        {results.get('total_return_pct', 0):+.2f}%",
            "",
            "TRADE STATISTICS",
            "-"*80,
            f"Total Trades:        {results.get('total_trades', 0)}",
            f"Winning Trades:      {results.get('winning_trades', 0)}",
            f"Losing Trades:       {results.get('losing_trades', 0)}",
            f"Win Rate:            {results.get('win_rate', 0):.2f}%",
            "",
            "PROFIT/LOSS ANALYSIS",
            "-"*80,
            f"Average Win:         ${results.get('avg_win', 0):,.2f}",
            f"Average Loss:        ${results.get('avg_loss', 0):,.2f}",
            f"Largest Win:         ${results.get('max_win', 0):,.2f}",
            f"Largest Loss:        ${results.get('max_loss', 0):,.2f}",
            f"Profit Factor:       {results.get('profit_factor', 0):.2f}",
            "",
            "RISK METRICS",
            "-"*80,
            f"Max Drawdown:        {results.get('max_drawdown_pct', 0):.2f}%",
            f"Sharpe Ratio:        {results.get('sharpe_ratio', 0):.2f}",
            f"Sortino Ratio:       {results.get('sortino_ratio', 0):.2f}",
            "",
            "TRADE EXECUTION",
            "-"*80,
            f"Avg Hold Time:       {results.get('avg_hold_hours', 0):.1f} hours",
            f"Total Commissions:   ${results.get('total_commissions', 0):,.2f}",
            f"Commission Rate:     {results.get('commission_rate', 0)*100:.3f}%",
            "",
        ])
        
        # 止盈止损统计
        if 'tp_count' in results or 'sl_count' in results:
            report_lines.extend([
                "STOP LOSS / TAKE PROFIT",
                "-"*80,
                f"Take Profit Hits:    {results.get('tp_count', 0)}",
                f"Stop Loss Hits:      {results.get('sl_count', 0)}",
                f"Strategy Exits:      {results.get('strategy_exit_count', 0)}",
                "",
            ])
        
        # 评级
        rating = self._calculate_rating(results)
        report_lines.extend([
            "OVERALL RATING",
            "-"*80,
            f"Rating:              {rating['grade']} ({rating['score']}/100)",
            f"Assessment:          {rating['assessment']}",
            "",
            "="*80,
            ""
        ])
        
        report_text = "\n".join(report_lines)
        
        # 保存文件
        if save:
            # 保存文本报告
            text_file = self.output_dir / f"{strategy_name}_{timestamp}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            
            # 保存JSON报告
            json_file = self.output_dir / f"{strategy_name}_{timestamp}.json"
            
            # 转换results中的特殊类型为JSON可序列化格式
            def convert_to_json_serializable(obj):
                """递归转换对象为JSON可序列化格式"""
                if isinstance(obj, dict):
                    return {k: convert_to_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_json_serializable(item) for item in obj]
                elif isinstance(obj, (pd.Timestamp, datetime)):
                    return obj.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(obj, (np.integer, np.floating)):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                else:
                    return obj
            
            report_data = {
                'strategy': strategy_name,
                'timestamp': timestamp,
                'data_info': convert_to_json_serializable(data_info),
                'parameters': convert_to_json_serializable(params),
                'results': convert_to_json_serializable(results),
                'rating': rating
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n[Report] Saved to:")
            print(f"  Text: {text_file.name}")
            print(f"  JSON: {json_file.name}")
        
        return report_text
    
    def _calculate_rating(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算策略评分"""
        score = 0
        
        # 收益率 (0-30分)
        total_return = results.get('total_return_pct', 0)
        if total_return > 20:
            score += 30
        elif total_return > 10:
            score += 25
        elif total_return > 5:
            score += 20
        elif total_return > 0:
            score += 15
        elif total_return > -5:
            score += 10
        elif total_return > -10:
            score += 5
        
        # 胜率 (0-20分)
        win_rate = results.get('win_rate', 0)
        if win_rate > 60:
            score += 20
        elif win_rate > 50:
            score += 15
        elif win_rate > 40:
            score += 10
        elif win_rate > 30:
            score += 5
        
        # 盈亏比 (0-20分)
        profit_factor = results.get('profit_factor', 0)
        if profit_factor > 2.0:
            score += 20
        elif profit_factor > 1.5:
            score += 15
        elif profit_factor > 1.0:
            score += 10
        elif profit_factor > 0.8:
            score += 5
        
        # 夏普比率 (0-15分)
        sharpe = results.get('sharpe_ratio', 0)
        if sharpe > 2.0:
            score += 15
        elif sharpe > 1.0:
            score += 10
        elif sharpe > 0.5:
            score += 5
        
        # 最大回撤 (0-15分)
        max_dd = abs(results.get('max_drawdown', 100))
        if max_dd < 5:
            score += 15
        elif max_dd < 10:
            score += 10
        elif max_dd < 20:
            score += 5
        
        # 评级
        if score >= 80:
            grade = 'A (Excellent)'
            assessment = 'Strong strategy, suitable for live trading'
        elif score >= 60:
            grade = 'B (Good)'
            assessment = 'Promising strategy, needs optimization'
        elif score >= 40:
            grade = 'C (Average)'
            assessment = 'Needs significant improvement'
        elif score >= 20:
            grade = 'D (Poor)'
            assessment = 'Not recommended for live trading'
        else:
            grade = 'F (Failed)'
            assessment = 'Strategy is not profitable'
        
        return {
            'score': score,
            'grade': grade,
            'assessment': assessment
        }
    
    def compare_strategies(
        self,
        reports: List[Dict[str, Any]],
        save: bool = True
    ) -> str:
        """
        对比多个策略
        
        Args:
            reports: 策略报告列表
            save: 是否保存
        
        Returns:
            对比报告文本
        """
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        report_lines = [
            "="*100,
            "STRATEGY COMPARISON REPORT",
            "="*100,
            "",
            f"Comparison Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Strategies Compared: {len(reports)}",
            "",
            "="*100,
        ]
        
        # 创建对比表格
        headers = ['Strategy', 'Initial $', 'Final $', 'P&L $', 'Return%', 'Trades', 'Win%', 'P.Factor', 'Sharpe', 'MaxDD%', 'Rating']
        
        # 计算列宽
        col_widths = [20, 12, 12, 12, 10, 8, 8, 10, 8, 10, 15]
        
        # 表头
        report_lines.append(' | '.join(h.ljust(w) for h, w in zip(headers, col_widths)))
        report_lines.append('-' * 100)
        
        # 数据行
        for report in sorted(reports, key=lambda x: x['results'].get('total_return_pct', -999), reverse=True):
            strategy = report['strategy']
            r = report['results']
            rating = report.get('rating', {})
            
            row = [
                strategy[:20],
                f"${r.get('initial_capital', 10000):,.0f}",
                f"${r.get('final_capital', 0):,.0f}",
                f"{r.get('total_pnl', 0):+,.0f}",
                f"{r.get('total_return_pct', 0):+.2f}",
                str(r.get('total_trades', 0)),
                f"{r.get('win_rate', 0):.1f}",
                f"{r.get('profit_factor', 0):.2f}",
                f"{r.get('sharpe_ratio', 0):.2f}",
                f"{r.get('max_drawdown_pct', 0):.2f}",
                rating.get('grade', 'N/A')
            ]
            
            report_lines.append(' | '.join(str(v).ljust(w) for v, w in zip(row, col_widths)))
        
        report_lines.extend([
            "",
            "="*100,
            ""
        ])
        
        report_text = "\n".join(report_lines)
        
        if save:
            file_path = self.output_dir / f"comparison_{timestamp}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"\n[Comparison] Saved to: {file_path.name}")
        
        return report_text


if __name__ == '__main__':
    # 测试
    reporter = BacktestReport()
    
    # 模拟结果
    results = {
        'initial_capital': 10000,
        'final_capital': 10500,
        'total_profit': 500,
        'total_return': 5.0,
        'total_trades': 100,
        'winning_trades': 55,
        'losing_trades': 45,
        'win_rate': 55.0,
        'avg_win': 15.0,
        'avg_loss': -10.0,
        'profit_factor': 1.2,
        'max_drawdown': 8.5,
        'sharpe_ratio': 1.5,
        'sortino_ratio': 2.0,
        'tp_count': 20,
        'sl_count': 15
    }
    
    report = reporter.generate_report(
        strategy_name='TestStrategy',
        results=results,
        params={'stop_loss': 0.01, 'take_profit': 0.02},
        data_info={'symbol': 'BTC/USDT', 'timeframe': '15m', 'candles': 8640}
    )
    
    print(report)
