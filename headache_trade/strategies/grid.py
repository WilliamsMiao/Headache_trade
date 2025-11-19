"""
网格交易策略
适用于震荡市场，在价格区间内低买高卖
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from .base import BaseStrategy, TradingSignal, SignalType


class GridTradingStrategy(BaseStrategy):
    """网格交易策略"""
    
    def __init__(self, grid_count: int = 7, grid_spacing_atr: float = 0.5):
        """
        Args:
            grid_count: 网格数量
            grid_spacing_atr: 网格间距（ATR倍数）
        """
        super().__init__(
            name="Grid Trading",
            description="震荡市场网格交易策略"
        )
        
        self.grid_count = grid_count
        self.grid_spacing_atr = grid_spacing_atr
        self.grid_levels = []
        self.grid_positions = {}  # 记录各网格持仓
        self.range_upper = None
        self.range_lower = None
    
    def generate_signal(self, price_data: pd.DataFrame,
                       current_position: Optional[Dict] = None) -> TradingSignal:
        """生成交易信号"""
        
        current_price = price_data['close'].iloc[-1]
        
        # 首次运行或网格失效，重新初始化网格
        if not self.grid_levels or not self._is_grid_valid(current_price):
            self._initialize_grid(price_data)
        
        # 检查是否触发买入/卖出网格
        signal_type, grid_level = self._check_grid_trigger(current_price)
        
        if signal_type == SignalType.HOLD:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                confidence=0,
                entry_price=current_price
            )
        
        # 计算止损止盈
        stop_loss, take_profit = self._calculate_tp_sl(current_price, signal_type)
        
        # 置信度基于网格位置
        confidence = self._calculate_confidence(current_price, grid_level)
        
        return TradingSignal(
            signal_type=signal_type,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'grid_level': grid_level,
                'grid_count': self.grid_count,
                'strategy': self.name
            }
        )
    
    def _initialize_grid(self, price_data: pd.DataFrame):
        """初始化网格"""
        close = price_data['close']
        high = price_data['high']
        low = price_data['low']
        
        # 计算区间上下限（近20日高低点 ± 3%）
        lookback = min(20, len(price_data))
        self.range_upper = high.iloc[-lookback:].max() * 1.03
        self.range_lower = low.iloc[-lookback:].min() * 0.97
        
        # 计算ATR
        atr = self._calculate_atr(price_data)
        
        # 网格间距
        grid_spacing = atr * self.grid_spacing_atr
        
        # 生成网格价格
        current_price = close.iloc[-1]
        self.grid_levels = []
        
        # 向上生成网格
        level = current_price
        for i in range(self.grid_count // 2 + 1):
            if level <= self.range_upper:
                self.grid_levels.append(round(level, 2))
            level += grid_spacing
        
        # 向下生成网格
        level = current_price - grid_spacing
        for i in range(self.grid_count // 2):
            if level >= self.range_lower:
                self.grid_levels.insert(0, round(level, 2))
            level -= grid_spacing
        
        self.grid_levels = sorted(set(self.grid_levels))
        
        print(f"[Grid] Initialized: {len(self.grid_levels)} grids")
        print(f"   Range: [{self.range_lower:.2f}, {self.range_upper:.2f}]")
        print(f"   Levels: {self.grid_levels}")
    
    def _is_grid_valid(self, current_price: float) -> bool:
        """检查网格是否有效"""
        if not self.grid_levels:
            return False
        
        # 价格突破区间
        if current_price > self.range_upper * 1.05 or current_price < self.range_lower * 0.95:
            print("[Grid] Price broke out of grid range, reinitializing...")
            return False
        
        return True
    
    def _check_grid_trigger(self, current_price: float) -> tuple:
        """检查是否触发网格交易"""
        if not self.grid_levels:
            return SignalType.HOLD, None
        
        # 找到最接近的网格
        closest_grid = min(self.grid_levels, key=lambda x: abs(x - current_price))
        price_diff = abs(current_price - closest_grid)
        
        # 触发阈值（距离网格0.1%内）
        trigger_threshold = closest_grid * 0.001
        
        if price_diff > trigger_threshold:
            return SignalType.HOLD, None
        
        # 触发买入网格（价格在网格下方）
        if current_price < closest_grid * 0.999:
            # 检查该网格是否已有持仓
            if closest_grid not in self.grid_positions:
                return SignalType.BUY, closest_grid
        
        # 触发卖出网格（价格在网格上方）
        elif current_price > closest_grid * 1.001:
            # 检查该网格是否有持仓可平
            if closest_grid in self.grid_positions:
                return SignalType.SELL, closest_grid
        
        return SignalType.HOLD, None
    
    def _calculate_tp_sl(self, current_price: float, 
                        signal_type: SignalType) -> tuple:
        """计算止盈止损"""
        if not self.grid_levels:
            return None, None
        
        # 找到当前网格位置
        current_grid_idx = min(range(len(self.grid_levels)),
                              key=lambda i: abs(self.grid_levels[i] - current_price))
        
        if signal_type == SignalType.BUY:
            # 止盈：上一个网格
            if current_grid_idx < len(self.grid_levels) - 1:
                take_profit = self.grid_levels[current_grid_idx + 1]
            else:
                take_profit = current_price * 1.02
            
            # 止损：下一个网格或区间下限
            if current_grid_idx > 0:
                stop_loss = self.grid_levels[current_grid_idx - 1]
            else:
                stop_loss = self.range_lower
        
        elif signal_type == SignalType.SELL:
            # 卖出信号的止盈止损相反
            if current_grid_idx > 0:
                take_profit = self.grid_levels[current_grid_idx - 1]
            else:
                take_profit = current_price * 0.98
            
            if current_grid_idx < len(self.grid_levels) - 1:
                stop_loss = self.grid_levels[current_grid_idx + 1]
            else:
                stop_loss = self.range_upper
        
        else:
            return None, None
        
        return stop_loss, take_profit
    
    def _calculate_confidence(self, current_price: float, grid_level: Optional[float]) -> float:
        """计算信号置信度"""
        if grid_level is None:
            return 0.0
        
        if not self.grid_levels:
            return 50.0
        
        # 基础置信度
        base_confidence = 70.0
        
        # 根据网格位置调整（越靠近区间边缘，置信度越高）
        grid_position = (current_price - self.range_lower) / (self.range_upper - self.range_lower)
        
        # 买入时靠近下限置信度高，卖出时靠近上限置信度高
        if current_price < grid_level:  # 买入
            confidence = base_confidence + (1 - grid_position) * 20
        else:  # 卖出
            confidence = base_confidence + grid_position * 20
        
        return min(95.0, confidence)
    
    def should_exit(self, price_data: pd.DataFrame,
                   entry_price: float, position_side: str) -> bool:
        """判断是否退出"""
        current_price = price_data['close'].iloc[-1]
        
        # 价格突破区间，退出所有持仓
        if current_price > self.range_upper or current_price < self.range_lower:
            print(f"[Grid] Price broke range, exiting grid trading...")
            return True
        
        # 检查是否达到网格止盈
        if position_side == 'long':
            # 找到上一个网格
            next_grid = min([g for g in self.grid_levels if g > entry_price], 
                           default=entry_price * 1.02)
            if current_price >= next_grid:
                return True
        
        elif position_side == 'short':
            # 找到下一个网格
            next_grid = max([g for g in self.grid_levels if g < entry_price],
                           default=entry_price * 0.98)
            if current_price <= next_grid:
                return True
        
        return False
    
    def calculate_position_size(self, account_balance: float,
                               signal: TradingSignal) -> float:
        """计算仓位大小"""
        # 单网格仓位 = 总仓位 / 网格数量
        single_grid_allocation = 0.3 / self.grid_count  # 总仓位30%
        
        position_value = account_balance * single_grid_allocation
        position_size = position_value / signal.entry_price
        
        return round(position_size, 3)
    
    # 注意：_calculate_atr 方法已从 BaseStrategy 继承
    # 但 grid 策略中需要返回单个值而不是Series，所以重写一下
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR（返回单个值）"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        atr_series = super()._calculate_atr(high, low, close, period)
        return atr_series.iloc[-1] if not np.isnan(atr_series.iloc[-1]) else (high.iloc[-1] - low.iloc[-1])
    
    def update_grid_position(self, grid_level: float, action: str):
        """更新网格持仓记录"""
        if action == 'open':
            self.grid_positions[grid_level] = True
        elif action == 'close':
            if grid_level in self.grid_positions:
                del self.grid_positions[grid_level]
    
    def get_grid_status(self) -> Dict:
        """获取网格状态"""
        return {
            'grid_count': len(self.grid_levels),
            'active_positions': len(self.grid_positions),
            'range': [self.range_lower, self.range_upper],
            'grid_levels': self.grid_levels,
            'filled_grids': list(self.grid_positions.keys())
        }
