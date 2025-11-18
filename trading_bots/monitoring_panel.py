"""
性能监控面板
实时显示策略运行状态和关键指标
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
import json


class PerformanceMonitor:
    """性能监控面板"""
    
    def __init__(self, max_history: int = 1000):
        
        self.max_history = max_history
        
        # 数据存储
        self.trade_history = deque(maxlen=max_history)
        self.equity_history = deque(maxlen=max_history)
        self.strategy_switches = deque(maxlen=max_history)
        self.market_states = deque(maxlen=max_history)
        self.alerts = deque(maxlen=100)
        
        # 实时统计
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'current_equity': 0.0,
            'peak_equity': 0.0,
            'current_drawdown': 0.0,
            'max_drawdown': 0.0,
            'active_strategy': None,
            'current_position': None,
            'last_update': None
        }
        
        # 策略表现
        self.strategy_performance = {}
        
        # 风险指标
        self.risk_metrics = {
            'consecutive_losses': 0,
            'max_consecutive_losses': 0,
            'daily_loss': 0.0,
            'daily_loss_limit': 0.05,  # 5%
            'position_size_pct': 0.0
        }
        
    def update_equity(self, equity: float, timestamp: Optional[datetime] = None):
        """更新权益"""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.equity_history.append({
            'timestamp': timestamp,
            'equity': equity
        })
        
        # 更新统计
        self.stats['current_equity'] = equity
        self.stats['last_update'] = timestamp
        
        # 更新峰值和回撤
        if equity > self.stats['peak_equity']:
            self.stats['peak_equity'] = equity
        
        if self.stats['peak_equity'] > 0:
            drawdown = (self.stats['peak_equity'] - equity) / self.stats['peak_equity']
            self.stats['current_drawdown'] = drawdown
            self.stats['max_drawdown'] = max(self.stats['max_drawdown'], drawdown)
            
            # 检查回撤警告
            if drawdown > 0.1:  # 10%
                self._add_alert('warning', f'当前回撤 {drawdown*100:.2f}%，接近风险阈值')
    
    def record_trade(self, trade: Dict):
        """记录交易"""
        trade['timestamp'] = datetime.now()
        self.trade_history.append(trade)
        
        # 更新统计
        self.stats['total_trades'] += 1
        self.stats['total_pnl'] += trade.get('net_pnl', 0)
        
        if trade.get('net_pnl', 0) > 0:
            self.stats['winning_trades'] += 1
            self.risk_metrics['consecutive_losses'] = 0
        else:
            self.stats['losing_trades'] += 1
            self.risk_metrics['consecutive_losses'] += 1
            self.risk_metrics['max_consecutive_losses'] = max(
                self.risk_metrics['max_consecutive_losses'],
                self.risk_metrics['consecutive_losses']
            )
            
            # 检查连续亏损警告
            if self.risk_metrics['consecutive_losses'] >= 3:
                self._add_alert('error', f'连续亏损 {self.risk_metrics["consecutive_losses"]} 次')
        
        # 更新策略表现
        strategy_name = trade.get('strategy', 'Unknown')
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0.0
            }
        
        perf = self.strategy_performance[strategy_name]
        perf['trades'] += 1
        perf['total_pnl'] += trade.get('net_pnl', 0)
        if trade.get('net_pnl', 0) > 0:
            perf['wins'] += 1
        else:
            perf['losses'] += 1
    
    def record_strategy_switch(self, from_strategy: str, to_strategy: str, reason: str):
        """记录策略切换"""
        self.strategy_switches.append({
            'timestamp': datetime.now(),
            'from': from_strategy,
            'to': to_strategy,
            'reason': reason
        })
        
        self.stats['active_strategy'] = to_strategy
        self._add_alert('info', f'策略切换: {from_strategy} → {to_strategy} ({reason})')
    
    def record_market_state(self, state: str, confidence: float):
        """记录市场状态"""
        self.market_states.append({
            'timestamp': datetime.now(),
            'state': state,
            'confidence': confidence
        })
    
    def update_position(self, position: Optional[Dict]):
        """更新当前持仓"""
        self.stats['current_position'] = position
        
        if position:
            # 计算仓位占比
            if self.stats['current_equity'] > 0:
                position_value = position['entry_price'] * position['size']
                position_pct = position_value / self.stats['current_equity']
                self.risk_metrics['position_size_pct'] = position_pct
                
                # 检查仓位过大
                if position_pct > 0.5:  # 50%
                    self._add_alert('warning', f'仓位过大: {position_pct*100:.1f}%')
        else:
            self.risk_metrics['position_size_pct'] = 0.0
    
    def _add_alert(self, level: str, message: str):
        """添加警告"""
        self.alerts.append({
            'timestamp': datetime.now(),
            'level': level,  # 'info', 'warning', 'error'
            'message': message
        })
    
    def get_dashboard_data(self) -> Dict:
        """获取仪表板数据"""
        
        # 计算胜率
        win_rate = 0.0
        if self.stats['total_trades'] > 0:
            win_rate = self.stats['winning_trades'] / self.stats['total_trades'] * 100
        
        # 计算盈亏比
        avg_win = 0.0
        avg_loss = 0.0
        profit_factor = 0.0
        
        if len(self.trade_history) > 0:
            trades_df = pd.DataFrame(list(self.trade_history))
            if 'net_pnl' in trades_df.columns:
                winning_trades = trades_df[trades_df['net_pnl'] > 0]
                losing_trades = trades_df[trades_df['net_pnl'] < 0]
                
                if len(winning_trades) > 0:
                    avg_win = winning_trades['net_pnl'].mean()
                if len(losing_trades) > 0:
                    avg_loss = losing_trades['net_pnl'].mean()
                
                if avg_loss < 0:
                    profit_factor = abs(avg_win / avg_loss)
        
        # 今日交易统计
        today_trades = self._get_today_trades()
        
        # 策略表现排名
        strategy_ranking = self._get_strategy_ranking()
        
        # 最近警告
        recent_alerts = list(self.alerts)[-10:]
        
        return {
            'summary': {
                'current_equity': self.stats['current_equity'],
                'total_pnl': self.stats['total_pnl'],
                'current_drawdown': self.stats['current_drawdown'] * 100,
                'max_drawdown': self.stats['max_drawdown'] * 100,
                'total_trades': self.stats['total_trades'],
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'active_strategy': self.stats['active_strategy'],
                'last_update': self.stats['last_update']
            },
            'position': self.stats['current_position'],
            'risk': {
                'consecutive_losses': self.risk_metrics['consecutive_losses'],
                'max_consecutive_losses': self.risk_metrics['max_consecutive_losses'],
                'position_size_pct': self.risk_metrics['position_size_pct'] * 100,
                'daily_loss': self.risk_metrics['daily_loss']
            },
            'today': today_trades,
            'strategy_performance': strategy_ranking,
            'alerts': recent_alerts,
            'equity_curve': list(self.equity_history)[-100:],  # 最近100个点
            'recent_trades': list(self.trade_history)[-10:]  # 最近10笔交易
        }
    
    def _get_today_trades(self) -> Dict:
        """获取今日交易统计"""
        today = datetime.now().date()
        
        today_trades = [
            t for t in self.trade_history
            if t.get('timestamp', datetime.min).date() == today
        ]
        
        total = len(today_trades)
        wins = sum(1 for t in today_trades if t.get('net_pnl', 0) > 0)
        losses = sum(1 for t in today_trades if t.get('net_pnl', 0) < 0)
        pnl = sum(t.get('net_pnl', 0) for t in today_trades)
        
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'pnl': pnl,
            'win_rate': (wins / total * 100) if total > 0 else 0
        }
    
    def _get_strategy_ranking(self) -> List[Dict]:
        """获取策略表现排名"""
        ranking = []
        
        for strategy, perf in self.strategy_performance.items():
            if perf['trades'] > 0:
                win_rate = perf['wins'] / perf['trades'] * 100
                avg_pnl = perf['total_pnl'] / perf['trades']
                
                ranking.append({
                    'strategy': strategy,
                    'trades': perf['trades'],
                    'win_rate': win_rate,
                    'total_pnl': perf['total_pnl'],
                    'avg_pnl': avg_pnl
                })
        
        # 按总盈亏排序
        ranking.sort(key=lambda x: x['total_pnl'], reverse=True)
        
        return ranking
    
    def print_dashboard(self):
        """打印仪表板（终端版）"""
        data = self.get_dashboard_data()
        
        print("\n" + "="*80)
        print(" " * 30 + "📊 性能监控面板")
        print("="*80 + "\n")
        
        # 汇总数据
        summary = data['summary']
        print(f"💰 权益状况:")
        print(f"   当前权益: ${summary['current_equity']:,.2f}")
        print(f"   总盈亏: ${summary['total_pnl']:,.2f}")
        print(f"   当前回撤: {summary['current_drawdown']:.2f}%")
        print(f"   最大回撤: {summary['max_drawdown']:.2f}%\n")
        
        print(f"📈 交易统计:")
        print(f"   总交易: {summary['total_trades']}")
        print(f"   胜率: {summary['win_rate']:.2f}%")
        print(f"   盈亏比: {summary['profit_factor']:.2f}")
        print(f"   当前策略: {summary['active_strategy'] or 'N/A'}\n")
        
        # 持仓信息
        position = data['position']
        if position:
            print(f"📍 当前持仓:")
            print(f"   方向: {position['side'].upper()}")
            print(f"   入场价: ${position['entry_price']:.2f}")
            print(f"   数量: {position['size']:.4f}")
            print(f"   止损: ${position.get('stop_loss', 'N/A')}")
            print(f"   止盈: ${position.get('take_profit', 'N/A')}\n")
        else:
            print(f"📍 当前持仓: 无\n")
        
        # 风险指标
        risk = data['risk']
        print(f"⚠️ 风险指标:")
        print(f"   连续亏损: {risk['consecutive_losses']}")
        print(f"   最大连续亏损: {risk['max_consecutive_losses']}")
        print(f"   仓位占比: {risk['position_size_pct']:.2f}%\n")
        
        # 今日交易
        today = data['today']
        print(f"📅 今日交易:")
        print(f"   总交易: {today['total']}")
        print(f"   盈利: {today['wins']} | 亏损: {today['losses']}")
        print(f"   盈亏: ${today['pnl']:,.2f}")
        print(f"   胜率: {today['win_rate']:.2f}%\n")
        
        # 策略表现
        if data['strategy_performance']:
            print(f"🎯 策略表现:")
            for rank, perf in enumerate(data['strategy_performance'][:5], 1):
                print(f"   {rank}. {perf['strategy']}: "
                      f"{perf['trades']}笔 | "
                      f"胜率{perf['win_rate']:.1f}% | "
                      f"盈亏${perf['total_pnl']:,.2f}")
            print()
        
        # 最近警告
        if data['alerts']:
            print(f"🚨 最近警告:")
            for alert in data['alerts'][-5:]:
                level_emoji = {
                    'info': 'ℹ️',
                    'warning': '⚠️',
                    'error': '🚫'
                }.get(alert['level'], '•')
                
                timestamp = alert['timestamp'].strftime("%H:%M:%S")
                print(f"   {level_emoji} [{timestamp}] {alert['message']}")
            print()
        
        print("="*80)
        print(f"最后更新: {summary['last_update'].strftime('%Y-%m-%d %H:%M:%S') if summary['last_update'] else 'N/A'}")
        print("="*80 + "\n")
    
    def export_report(self, filename: str = None):
        """导出性能报告"""
        if filename is None:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = self.get_dashboard_data()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"性能报告已导出: {filename}")
        return filename
    
    def check_risk_limits(self) -> Dict:
        """检查风险限制"""
        violations = []
        
        # 1. 最大回撤
        if self.stats['current_drawdown'] > 0.2:  # 20%
            violations.append({
                'type': 'max_drawdown',
                'severity': 'critical',
                'message': f'回撤超过20%: {self.stats["current_drawdown"]*100:.2f}%'
            })
        
        # 2. 连续亏损
        if self.risk_metrics['consecutive_losses'] >= 5:
            violations.append({
                'type': 'consecutive_losses',
                'severity': 'high',
                'message': f'连续亏损{self.risk_metrics["consecutive_losses"]}次'
            })
        
        # 3. 仓位过大
        if self.risk_metrics['position_size_pct'] > 0.6:  # 60%
            violations.append({
                'type': 'position_size',
                'severity': 'medium',
                'message': f'仓位占比{self.risk_metrics["position_size_pct"]*100:.1f}%'
            })
        
        # 4. 日内亏损过大
        today_pnl = self._get_today_trades()['pnl']
        if self.stats['current_equity'] > 0:
            daily_loss_pct = today_pnl / self.stats['current_equity']
            if daily_loss_pct < -self.risk_metrics['daily_loss_limit']:
                violations.append({
                    'type': 'daily_loss',
                    'severity': 'high',
                    'message': f'日内亏损{abs(daily_loss_pct)*100:.2f}%，超过限制'
                })
        
        return {
            'has_violations': len(violations) > 0,
            'violations': violations
        }
    
    def get_performance_summary(self) -> str:
        """获取性能摘要（适合通知）"""
        data = self.get_dashboard_data()
        summary = data['summary']
        
        text = f"""
📊 性能摘要

💰 权益: ${summary['current_equity']:,.2f} (总盈亏: ${summary['total_pnl']:,.2f})
📈 胜率: {summary['win_rate']:.2f}% ({summary['total_trades']}笔交易)
⚠️ 回撤: {summary['current_drawdown']:.2f}% (最大: {summary['max_drawdown']:.2f}%)
🎯 当前策略: {summary['active_strategy'] or 'N/A'}
"""
        
        # 添加持仓信息
        if data['position']:
            pos = data['position']
            text += f"\n📍 持仓: {pos['side'].upper()} @ ${pos['entry_price']:.2f}"
        
        # 添加风险警告
        risk_check = self.check_risk_limits()
        if risk_check['has_violations']:
            text += f"\n\n🚨 风险警告:"
            for v in risk_check['violations']:
                text += f"\n   • {v['message']}"
        
        return text.strip()
