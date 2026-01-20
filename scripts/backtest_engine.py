"""
回测引擎 - 模拟交易策略执行
支持完整的交易逻辑模拟，包括开仓、平仓、止盈、止损、手续费计算等
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Callable
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Position:
    """持仓类"""
    def __init__(self, side: str, entry_price: float, size: float, entry_time: datetime, 
                 stop_loss: float = None, take_profit: float = None, leverage: int = 1):
        self.side = side  # 'long' 或 'short'
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.leverage = leverage
        self.highest_price = entry_price  # 用于追踪最高价（做多）
        self.lowest_price = entry_price   # 用于追踪最低价（做空）
        self.trailing_stop_price = None
        self.trailing_activated = False
        
    def update_extreme_prices(self, high: float, low: float):
        """更新极值价格"""
        if self.side == 'long':
            self.highest_price = max(self.highest_price, high)
        else:
            self.lowest_price = min(self.lowest_price, low)

    def update_trailing_stop(self, trailing_window: float = 0.005):
        """根据极值价格更新移动止损，trailing_window以小数表示（0.005=0.5%）。"""

        if self.side == 'long':
            if self.highest_price <= 0:
                return
            candidate = self.highest_price * (1 - trailing_window)
            if candidate <= self.entry_price:
                return
            self.trailing_stop_price = candidate
        else:
            if self.lowest_price <= 0:
                return
            candidate = self.lowest_price * (1 + trailing_window)
            if candidate >= self.entry_price:
                return
            self.trailing_stop_price = candidate

        self.trailing_activated = True
    
    def get_unrealized_pnl_pct(self, current_price: float) -> float:
        """计算未实现盈亏百分比"""
        if self.side == 'long':
            return ((current_price - self.entry_price) / self.entry_price) * self.leverage
        else:
            return ((self.entry_price - current_price) / self.entry_price) * self.leverage
    
    def check_stop_loss(self, current_price: float) -> bool:
        """检查是否触发止损"""
        if self.stop_loss is None:
            return False
        if self.side == 'long':
            return current_price <= self.stop_loss
        else:
            return current_price >= self.stop_loss
    
    def check_take_profit(self, current_price: float) -> bool:
        """检查是否触发止盈"""
        if self.take_profit is None:
            return False
        if self.side == 'long':
            return current_price >= self.take_profit
        else:
            return current_price <= self.take_profit


class Trade:
    """交易记录类"""
    def __init__(self, side: str, entry_price: float, entry_time: datetime, 
                 size: float, leverage: int):
        self.side = side
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.exit_price = None
        self.exit_time = None
        self.size = size
        self.leverage = leverage
        self.pnl_pct = None
        self.pnl_usdt = None
        self.exit_reason = None
        self.entry_fee = None
        self.exit_fee = None
        self.funding_fee = None  # 资金费率成本
        self.holding_time = None
        
    def close(self, exit_price: float, exit_time: datetime, reason: str, 
              entry_fee: float, exit_fee: float, funding_fee: float = 0):
        """平仓"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.entry_fee = entry_fee
        self.exit_fee = exit_fee
        self.funding_fee = funding_fee
        self.holding_time = (exit_time - self.entry_time).total_seconds() / 60  # 分钟
        
        # 计算盈亏
        if self.side == 'long':
            self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * self.leverage
        else:
            self.pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * self.leverage
        
        # 扣除手续费和资金费率
        total_fee_pct = entry_fee + exit_fee + funding_fee
        self.pnl_pct -= total_fee_pct
        
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': self.exit_time.strftime('%Y-%m-%d %H:%M:%S') if self.exit_time else None,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'leverage': self.leverage,
            'pnl_pct': round(self.pnl_pct * 100, 2) if self.pnl_pct else None,
            'pnl_usdt': round(self.pnl_usdt, 4) if self.pnl_usdt else None,
            'exit_reason': self.exit_reason,
            'holding_time_min': round(self.holding_time, 1) if self.holding_time else None,
            'funding_fee_pct': round(self.funding_fee * 100, 4) if self.funding_fee else 0
        }


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_balance: float = 100, leverage: int = 6, 
                 fee_rate: float = 0.001, slippage: float = 0.0001,
                 dynamic_leverage: bool = True, funding_rate: float = 0.0001):
        """
        初始化回测引擎
        
        Args:
            initial_balance: 初始资金（USDT）
            leverage: 默认杠杆倍数
            fee_rate: 手续费率（开仓+平仓总计）
            slippage: 滑点
            dynamic_leverage: 是否启用动态杠杆
            funding_rate: 资金费率（每8小时，默认0.01%）
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.default_leverage = leverage
        self.leverage = leverage  # 保持兼容性
        self.current_leverage = leverage  # 当前使用的杠杆
        self.dynamic_leverage_enabled = dynamic_leverage
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.funding_rate = funding_rate  # 资金费率（每8小时）
        self.funding_interval = 8 * 60  # 8小时，单位分钟
        
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        
        self.current_trade: Optional[Trade] = None
        
        # 统计信息
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
    def reset(self):
        """重置回测引擎"""
        self.balance = self.initial_balance
        self.position = None
        self.trades = []
        self.equity_curve = []
        self.current_trade = None
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
    
    def run(self, df: pd.DataFrame, strategy_func: Callable, verbose: bool = True) -> Dict:
        """
        运行回测
        
        Args:
            df: 历史K线数据，包含 timestamp, open, high, low, close, volume
            strategy_func: 策略函数，输入(当前索引, df, 当前持仓)，输出交易信号字典
            verbose: 是否打印详细日志
            
        Returns:
            回测结果字典
        """
        self.reset()
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"🚀 回测开始")
            print(f"{'='*60}")
            print(f"📊 数据范围: {df['timestamp'].iloc[0]} 至 {df['timestamp'].iloc[-1]}")
            print(f"📈 K线数量: {len(df)} 根")
            print(f"💰 初始资金: {self.initial_balance} USDT")
            print(f"⚡ 杠杆倍数: {self.leverage}x")
            print(f"{'='*60}\n")
        
        # 遍历每根K线
        for i in range(len(df)):
            current_bar = df.iloc[i]
            timestamp = current_bar['timestamp']
            open_price = current_bar['open']
            high_price = current_bar['high']
            low_price = current_bar['low']
            close_price = current_bar['close']
            
            # 更新持仓的极值价格
            if self.position:
                self.position.update_extreme_prices(high_price, low_price)
                self.position.update_trailing_stop(trailing_window=0.005)
                # 若移动止损生成，收紧stop_loss以锁定利润
                if self.position.trailing_stop_price:
                    if self.position.side == 'long':
                        self.position.stop_loss = max(
                            self.position.stop_loss or 0,
                            self.position.trailing_stop_price
                        )
                    else:
                        # 对于空头，止损价需向下移动，取较小值
                        self.position.stop_loss = min(
                            self.position.stop_loss or float('inf'),
                            self.position.trailing_stop_price
                        )
                
                # 检查止损和止盈（在K线的高低价范围内检查）
                if self.position.check_stop_loss(low_price if self.position.side == 'long' else high_price):
                    # 触发止损
                    exit_price = self.position.stop_loss
                    self.close_position(exit_price, timestamp, '止损')
                    if verbose and self.total_trades <= 10:
                        print(f"🛑 止损平仓 | 价格: {exit_price:.2f} | 盈亏: {self.trades[-1].pnl_pct*100:.2f}%")
                
                elif self.position.check_take_profit(high_price if self.position.side == 'long' else low_price):
                    # 触发止盈
                    exit_price = self.position.take_profit
                    self.close_position(exit_price, timestamp, '止盈')
                    if verbose and self.total_trades <= 10:
                        print(f"🎯 止盈平仓 | 价格: {exit_price:.2f} | 盈亏: {self.trades[-1].pnl_pct*100:.2f}%")
            
            # 调用策略函数获取信号（无论是否有持仓）
            signal = strategy_func(i, df, self.position, self.balance, self.get_performance_stats())
            
            # 处理CLOSE信号（平仓）
            if signal and signal.get('action') == 'CLOSE':
                if self.position is not None:
                    close_size = signal.get('size', self.position.size)
                    # 确保不超过持仓
                    close_size = min(close_size, self.position.size)
                    if close_size > 0:
                        # 部分平仓或全部平仓
                        if close_size >= self.position.size:
                            # 全部平仓
                            self.close_position(close_price, timestamp, signal.get('reason', '策略平仓'))
                            if verbose and self.total_trades <= 10:
                                print(f"🔄 策略平仓 | 价格: {close_price:.2f} | 原因: {signal.get('reason', 'N/A')}")
                        else:
                            # 部分平仓（简化处理：全部平仓）
                            self.close_position(close_price, timestamp, signal.get('reason', '策略部分平仓'))
                            if verbose and self.total_trades <= 10:
                                print(f"🔄 策略部分平仓 | 价格: {close_price:.2f} | 数量: {close_size}张")
            
            # 如果没有持仓，处理开仓信号
            elif self.position is None:
                if signal and signal.get('action') in ['BUY', 'SELL']:
                    # 执行开仓
                    action = signal['action']
                    size = signal.get('size', 0.06)  # 默认0.06张
                    stop_loss = signal.get('stop_loss')
                    take_profit = signal.get('take_profit')
                    leverage = signal.get('leverage')  # 获取动态杠杆
                    
                    # 使用收盘价作为入场价（考虑滑点）
                    entry_price = close_price * (1 + self.slippage if action == 'BUY' else 1 - self.slippage)
                    
                    self.open_position(
                        side='long' if action == 'BUY' else 'short',
                        price=entry_price,
                        size=size,
                        timestamp=timestamp,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        leverage=leverage
                    )
                    
                    if verbose and self.total_trades <= 10:
                        side_emoji = '📈' if action == 'BUY' else '📉'
                        sl_str = f"{stop_loss:.2f}" if stop_loss else "N/A"
                        tp_str = f"{take_profit:.2f}" if take_profit else "N/A"
                        print(f"{side_emoji} 开{'多' if action == 'BUY' else '空'}仓 | 价格: {entry_price:.2f} | 仓位: {size}张 | SL: {sl_str} | TP: {tp_str}")
            
            # 记录权益曲线
            equity = self.calculate_equity(close_price)
            self.equity_curve.append({
                'timestamp': timestamp,
                'balance': self.balance,
                'equity': equity,
                'position': self.position.side if self.position else None
            })
        
        # 回测结束，如果还有持仓，强制平仓
        if self.position:
            last_bar = df.iloc[-1]
            self.close_position(last_bar['close'], last_bar['timestamp'], '回测结束')
            if verbose:
                print(f"⚠️ 回测结束强制平仓 | 价格: {last_bar['close']:.2f}")
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"✅ 回测完成")
            print(f"{'='*60}\n")
        
        return self.get_results()
    
    def open_position(self, side: str, price: float, size: float, timestamp: datetime,
                     stop_loss: float = None, take_profit: float = None, leverage: int = None):
        """开仓"""
        # 使用动态杠杆（如果提供）或默认杠杆
        use_leverage = leverage if leverage is not None else self.default_leverage
        if self.dynamic_leverage_enabled:
            self.current_leverage = use_leverage
        else:
            self.current_leverage = self.default_leverage
        
        self.position = Position(
            side=side,
            entry_price=price,
            size=size,
            entry_time=timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=self.current_leverage
        )
        
        self.current_trade = Trade(
            side=side,
            entry_price=price,
            entry_time=timestamp,
            size=size,
            leverage=self.current_leverage
        )
        
        self.total_trades += 1
    
    def close_position(self, price: float, timestamp: datetime, reason: str):
        """平仓"""
        if not self.position or not self.current_trade:
            return
        
        # 计算盈亏
        position_value = self.position.size * price * 0.01  # 1张 = 0.01 BTC
        entry_value = self.position.size * self.position.entry_price * 0.01
        
        if self.position.side == 'long':
            pnl_pct = ((price - self.position.entry_price) / self.position.entry_price) * self.position.leverage
        else:
            pnl_pct = ((self.position.entry_price - price) / self.position.entry_price) * self.position.leverage
        
        # 计算手续费
        entry_fee_pct = self.fee_rate / 2  # 开仓手续费
        exit_fee_pct = self.fee_rate / 2   # 平仓手续费
        
        # 计算资金费率
        holding_time_minutes = (timestamp - self.position.entry_time).total_seconds() / 60
        funding_periods = holding_time_minutes / self.funding_interval  # 持仓跨越的资金费率周期数
        funding_fee_pct = self.funding_rate * funding_periods  # 总资金费率
        
        # 计算实际盈亏（USDT）
        pnl_usdt = self.balance * pnl_pct
        entry_fee_usdt = entry_value * entry_fee_pct / 100
        exit_fee_usdt = position_value * exit_fee_pct / 100
        funding_fee_usdt = position_value * funding_fee_pct / 100  # 资金费率成本
        total_fee_usdt = entry_fee_usdt + exit_fee_usdt + funding_fee_usdt
        
        net_pnl_usdt = pnl_usdt - total_fee_usdt
        
        # 更新余额
        self.balance += net_pnl_usdt
        
        # 记录交易
        self.current_trade.close(price, timestamp, reason, entry_fee_pct, exit_fee_pct, funding_fee_pct)
        self.current_trade.pnl_usdt = net_pnl_usdt
        self.trades.append(self.current_trade)
        
        # 更新统计
        if self.current_trade.pnl_pct > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # 清空持仓
        self.position = None
        self.current_trade = None
    
    def calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        if not self.position:
            return self.balance
        
        unrealized_pnl_pct = self.position.get_unrealized_pnl_pct(current_price)
        unrealized_pnl_usdt = self.balance * unrealized_pnl_pct
        
        return self.balance + unrealized_pnl_usdt
    
    def get_performance_stats(self) -> Dict:
        """
        获取实时性能统计（用于动态调整）
        
        Returns:
            dict: 包含胜率、交易次数等统计信息
        """
        if self.total_trades == 0:
            return {
                'win_rate': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0
            }
        
        return {
            'win_rate': self.winning_trades / self.total_trades,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades
        }
    
    def get_results(self) -> Dict:
        """获取回测结果"""
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_return_pct': ((self.balance - self.initial_balance) / self.initial_balance) * 100,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'trades': [trade.to_dict() for trade in self.trades],
            'equity_curve': self.equity_curve
        }


if __name__ == '__main__':
    print("回测引擎模块")
    print("请使用 backtest_runner.py 运行回测")
