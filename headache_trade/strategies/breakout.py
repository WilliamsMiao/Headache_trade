"""
突破策略
适用于盘整后的突破行情
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict

from .base import BaseStrategy, TradingSignal, SignalType


class BreakoutStrategy(BaseStrategy):
    """突破策略 - 捕捉盘整突破的大行情"""
    
    def __init__(self,
                 consolidation_period: int = 10,
                 bb_squeeze_threshold: float = 0.25,  # 放宽至0.25
                 volume_surge_multiplier: float = 1.5,  # 降低至1.5倍
                 pullback_tolerance: float = 0.02,  # 放宽至2%
                 max_hold_hours: int = 24):
        
        super().__init__(
            name="BreakoutStrategy",
            description="突破策略 - 盘整突破 + 成交量确认"
        )
        
        # 参数
        self.consolidation_period = consolidation_period
        self.bb_squeeze_threshold = bb_squeeze_threshold
        self.volume_surge_multiplier = volume_surge_multiplier
        self.pullback_tolerance = pullback_tolerance
        self.max_hold_hours = max_hold_hours
        
        # 状态
        self.consolidation_range = None
        self.entry_time = None
    
    def generate_signal(self,
                       price_data: pd.DataFrame,
                       current_position: Optional[Dict] = None) -> Optional[TradingSignal]:
        """
        生成突破信号
        
        策略逻辑：
        1. 识别盘整区间（窄幅震荡）
        2. 布林带收窄确认
        3. 价格突破区间
        4. 成交量爆发确认
        5. 可选：回踩确认
        """
        
        if len(price_data) < 50:
            return None
        
        # 计算指标
        indicators = self._calculate_indicators(price_data)
        
        current_price = price_data['close'].iloc[-1]
        
        # 检查是否应该退出现有持仓
        if current_position:
            return None  # 突破策略只关注入场
        
        # 识别盘整区间
        if not self._is_consolidating(price_data, indicators):
            return None
        
        # 检查向上突破
        long_signal = self._check_long_breakout(current_price, price_data, indicators)
        if long_signal:
            return self._create_long_signal(current_price, price_data, indicators)
        
        # 检查向下突破
        short_signal = self._check_short_breakout(current_price, price_data, indicators)
        if short_signal:
            return self._create_short_signal(current_price, price_data, indicators)
        
        return None
    
    def _calculate_indicators(self, price_data: pd.DataFrame) -> Dict:
        """计算所有需要的指标"""
        close = price_data['close']
        high = price_data['high']
        low = price_data['low']
        volume = price_data['volume']
        
        # 布林带
        bb_middle = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        bb_upper = bb_middle + (bb_std * 2)
        bb_lower = bb_middle - (bb_std * 2)
        bb_width = (bb_upper - bb_lower) / bb_middle
        
        # 历史布林带宽度百分位
        bb_width_percentile = bb_width.rank(pct=True).iloc[-1] * 100
        
        # ATR
        atr = self._calculate_atr(high, low, close, 14)
        
        # 成交量
        volume_ma = volume.rolling(window=20).mean()
        volume_ratio = volume.iloc[-1] / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1.0
        
        # 近期高低点
        lookback = self.consolidation_period
        recent_high = high.iloc[-lookback:].max()
        recent_low = low.iloc[-lookback:].min()
        consolidation_range = (recent_high - recent_low) / recent_low
        
        # ADX
        adx = self._calculate_adx(high, low, close, 14)
        
        return {
            'bb_upper': bb_upper.iloc[-1],
            'bb_middle': bb_middle.iloc[-1],
            'bb_lower': bb_lower.iloc[-1],
            'bb_width': bb_width.iloc[-1],
            'bb_width_percentile': bb_width_percentile,
            'atr': atr.iloc[-1],
            'volume_ratio': volume_ratio,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'consolidation_range': consolidation_range,
            'adx': adx.iloc[-1]
        }
    
    def _is_consolidating(self, price_data: pd.DataFrame, indicators: Dict) -> bool:
        """判断是否处于盘整状态"""
        
        # 1. 布林带宽度在历史低位（收窄）
        if indicators['bb_width_percentile'] > 20:
            return False
        
        # 2. 盘整区间足够窄（相对范围 < 5%）
        if indicators['consolidation_range'] > 0.05:
            return False
        
        # 3. ADX较低（无明显趋势）或开始上升
        # 允许ADX < 25 或 ADX开始上升（突破前夜）
        if indicators['adx'] > 30:
            return False
        
        # 4. 至少经历了最小盘整期
        close = price_data['close'].iloc[-self.consolidation_period:]
        if len(close) < self.consolidation_period:
            return False
        
        print(f"   [BACKUP] 识别到盘整: 区间{indicators['consolidation_range']*100:.2f}%, BB宽度百分位{indicators['bb_width_percentile']:.1f}%")
        
        # 记录盘整区间
        self.consolidation_range = {
            'high': indicators['recent_high'],
            'low': indicators['recent_low'],
            'range': indicators['consolidation_range']
        }
        
        return True
    
    def _check_long_breakout(self, current_price: float, 
                            price_data: pd.DataFrame, 
                            indicators: Dict) -> bool:
        """检查向上突破条件"""
        
        if not self.consolidation_range:
            return False
        
        # 1. 价格突破盘整区间上限
        breakout_price = self.consolidation_range['high']
        if current_price <= breakout_price:
            return False
        
        # 2. 成交量爆发
        if indicators['volume_ratio'] < self.volume_surge_multiplier:
            return False
        
        # 3. 突破幅度足够（避免假突破）
        breakout_strength = (current_price - breakout_price) / breakout_price
        if breakout_strength < 0.005:  # 至少0.5%
            return False
        
        # 4. 价格在布林带上轨附近或突破
        if current_price < indicators['bb_upper'] * 0.98:
            return False
        
        print(f"   [START] 向上突破: {breakout_price:.2f} → {current_price:.2f} (+{breakout_strength*100:.2f}%)")
        print(f"   📊 成交量: {indicators['volume_ratio']:.2f}x")
        
        return True
    
    def _check_short_breakout(self, current_price: float,
                             price_data: pd.DataFrame,
                             indicators: Dict) -> bool:
        """检查向下突破条件"""
        
        if not self.consolidation_range:
            return False
        
        # 1. 价格突破盘整区间下限
        breakout_price = self.consolidation_range['low']
        if current_price >= breakout_price:
            return False
        
        # 2. 成交量爆发
        if indicators['volume_ratio'] < self.volume_surge_multiplier:
            return False
        
        # 3. 突破幅度足够
        breakout_strength = (breakout_price - current_price) / breakout_price
        if breakout_strength < 0.005:
            return False
        
        # 4. 价格在布林带下轨附近或突破
        if current_price > indicators['bb_lower'] * 1.02:
            return False
        
        print(f"   📉 向下突破: {breakout_price:.2f} → {current_price:.2f} (-{breakout_strength*100:.2f}%)")
        print(f"   📊 成交量: {indicators['volume_ratio']:.2f}x")
        
        return True
    
    def _create_long_signal(self, current_price: float,
                           price_data: pd.DataFrame,
                           indicators: Dict) -> TradingSignal:
        """创建做多信号"""
        
        # 止损：盘整区间下限 - 1 ATR
        stop_loss = self.consolidation_range['low'] - indicators['atr']
        
        # 止盈：盘整区间高度的2倍（经典突破目标）
        range_height = self.consolidation_range['high'] - self.consolidation_range['low']
        take_profit = current_price + (range_height * 2)
        
        # 置信度
        confidence = self._calculate_confidence(indicators, 'long')
        
        self.entry_time = pd.Timestamp.now()
        
        return TradingSignal(
            signal_type=SignalType.LONG,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'strategy': self.name,
                'breakout_level': self.consolidation_range['high'],
                'consolidation_range': self.consolidation_range['range'],
                'volume_ratio': indicators['volume_ratio'],
                'reason': '盘整后向上突破 + 成交量爆发'
            }
        )
    
    def _create_short_signal(self, current_price: float,
                            price_data: pd.DataFrame,
                            indicators: Dict) -> TradingSignal:
        """创建做空信号"""
        
        # 止损：盘整区间上限 + 1 ATR
        stop_loss = self.consolidation_range['high'] + indicators['atr']
        
        # 止盈：盘整区间高度的2倍
        range_height = self.consolidation_range['high'] - self.consolidation_range['low']
        take_profit = current_price - (range_height * 2)
        
        # 置信度
        confidence = self._calculate_confidence(indicators, 'short')
        
        self.entry_time = pd.Timestamp.now()
        
        return TradingSignal(
            signal_type=SignalType.SHORT,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'strategy': self.name,
                'breakout_level': self.consolidation_range['low'],
                'consolidation_range': self.consolidation_range['range'],
                'volume_ratio': indicators['volume_ratio'],
                'reason': '盘整后向下突破 + 成交量爆发'
            }
        )
    
    def _calculate_confidence(self, indicators: Dict, direction: str) -> float:
        """计算信号置信度"""
        
        confidence = 60.0
        
        # 盘整时间越长，置信度越高
        if self.consolidation_range:
            consolidation_tightness = 1 - (self.consolidation_range['range'] / 0.05)
            confidence += consolidation_tightness * 10
        
        # 布林带越窄，置信度越高
        if indicators['bb_width_percentile'] < 10:
            confidence += 15
        elif indicators['bb_width_percentile'] < 20:
            confidence += 10
        
        # 成交量爆发越强，置信度越高
        if indicators['volume_ratio'] > 3:
            confidence += 15
        elif indicators['volume_ratio'] > 2:
            confidence += 10
        elif indicators['volume_ratio'] > self.volume_surge_multiplier:
            confidence += 5
        
        return min(95.0, confidence)
    
    def should_exit(self,
                   price_data: pd.DataFrame,
                   entry_price: float,
                   position_side: str) -> bool:
        """
        判断是否应该退出持仓
        
        退出条件：
        1. 假突破（回落到盘整区间内）
        2. 达到目标盈利
        3. 时间止损
        4. 止损触发
        """
        
        if len(price_data) < 20:
            return False
        
        current_price = price_data['close'].iloc[-1]
        
        # 1. 假突破检测
        if self.consolidation_range:
            if position_side == 'long':
                # 回落到盘整区间内
                if current_price < self.consolidation_range['high'] * (1 - self.pullback_tolerance):
                    print(f"   [WARN] 假突破，回落到区间内")
                    return True
            else:
                # 反弹到盘整区间内
                if current_price > self.consolidation_range['low'] * (1 + self.pullback_tolerance):
                    print(f"   [WARN] 假突破，反弹到区间内")
                    return True
        
        # 2. 时间止损
        if self.entry_time:
            hold_hours = (pd.Timestamp.now() - self.entry_time).total_seconds() / 3600
            if hold_hours > self.max_hold_hours:
                print(f"   ⏰ 超过最大持仓时间")
                return True
        
        return False
    
    def calculate_position_size(self,
                               account_balance: float,
                               signal: TradingSignal) -> float:
        """计算仓位大小 - 突破策略采用中等仓位"""
        
        if not signal.stop_loss:
            return 0.0
        
        # 每次交易风险1.5%
        risk_per_trade = 0.015
        risk_amount = account_balance * risk_per_trade
        
        # 计算止损距离
        if signal.signal_type == SignalType.LONG:
            stop_distance = signal.entry_price - signal.stop_loss
        else:
            stop_distance = signal.stop_loss - signal.entry_price
        
        if stop_distance <= 0:
            return 0.0
        
        # 计算仓位
        position_size = risk_amount / stop_distance
        
        # 根据置信度调整
        confidence_factor = signal.confidence / 100.0
        position_size *= confidence_factor
        
        # 限制最大仓位（40%）
        max_position = account_balance * 0.4 / signal.entry_price
        position_size = min(position_size, max_position)
        
        return position_size
    
    # 注意：_calculate_atr, _calculate_adx 方法已从 BaseStrategy 继承
