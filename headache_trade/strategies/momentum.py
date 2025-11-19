"""
动量策略
适用于强势单边行情
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from datetime import datetime, timedelta

from .base import BaseStrategy, TradingSignal, SignalType


class MomentumStrategy(BaseStrategy):
    """动量策略 - 捕捉强势趋势中的动量行情"""
    
    def __init__(self,
                 consecutive_candles: int = 2,  # 降低至2根
                 volume_surge_multiplier: float = 1.2,  # 降低至1.2倍
                 rsi_min: float = 55,  # 降低至55
                 rsi_max: float = 85,  # 提高至85
                 adx_threshold: float = 25,  # 降低至25
                 trailing_atr_multiplier: float = 1.5,
                 max_hold_hours: int = 6):
        
        super().__init__(
            name="MomentumStrategy",
            description="动量策略 - 强势趋势 + 连续K线 + 成交量爆发"
        )
        
        # 参数
        self.consecutive_candles = consecutive_candles
        self.volume_surge_multiplier = volume_surge_multiplier
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.adx_threshold = adx_threshold
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.max_hold_hours = max_hold_hours
        
        # 状态
        self.entry_time = None
        self.highest_price = None
        self.lowest_price = None
    
    def generate_signal(self,
                       price_data: pd.DataFrame,
                       current_position: Optional[Dict] = None) -> Optional[TradingSignal]:
        """
        生成动量信号
        
        策略逻辑：
        1. 检测连续同向K线（3根以上）
        2. 成交量持续放大
        3. RSI在强势区间但未超买（60-80）
        4. ADX > 30（超强趋势）
        5. 顺势入场，追踪止损
        """
        
        if len(price_data) < 50:
            return None
        
        # 计算指标
        indicators = self._calculate_indicators(price_data)
        
        current_price = price_data['close'].iloc[-1]
        
        # 如果有持仓，检查是否应该退出
        if current_position:
            return None  # 动量策略只关注入场信号
        
        # 检查做多动量
        long_signal = self._check_long_momentum(price_data, indicators)
        if long_signal:
            return self._create_long_signal(current_price, indicators)
        
        # 检查做空动量
        short_signal = self._check_short_momentum(price_data, indicators)
        if short_signal:
            return self._create_short_signal(current_price, indicators)
        
        return None
    
    def _calculate_indicators(self, price_data: pd.DataFrame) -> Dict:
        """计算所有需要的指标"""
        close = price_data['close']
        high = price_data['high']
        low = price_data['low']
        volume = price_data['volume']
        
        # RSI
        rsi = self._calculate_rsi(close, 14)
        
        # ADX
        adx = self._calculate_adx(high, low, close, 14)
        
        # ATR
        atr = self._calculate_atr(high, low, close, 14)
        
        # 成交量
        volume_ma = volume.rolling(window=20).mean()
        volume_ratio = volume.iloc[-1] / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1.0
        
        # 平均成交量放大
        recent_volume_ma = volume.iloc[-5:].mean()
        avg_volume_ratio = recent_volume_ma / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1.0
        
        # K线连续性
        consecutive_up = self._count_consecutive_candles(price_data, 'up')
        consecutive_down = self._count_consecutive_candles(price_data, 'down')
        
        # 动量强度（最近5根K线的平均涨跌幅）
        momentum_strength = close.pct_change().iloc[-5:].mean()
        
        return {
            'rsi': rsi.iloc[-1],
            'adx': adx.iloc[-1],
            'atr': atr.iloc[-1],
            'volume_ratio': volume_ratio,
            'avg_volume_ratio': avg_volume_ratio,
            'consecutive_up': consecutive_up,
            'consecutive_down': consecutive_down,
            'momentum_strength': momentum_strength
        }
    
    def _count_consecutive_candles(self, price_data: pd.DataFrame, direction: str) -> int:
        """计算连续同向K线数量"""
        count = 0
        
        for i in range(len(price_data) - 1, 0, -1):
            current = price_data.iloc[i]
            
            if direction == 'up':
                if current['close'] > current['open']:
                    count += 1
                else:
                    break
            else:  # down
                if current['close'] < current['open']:
                    count += 1
                else:
                    break
        
        return count
    
    def _check_long_momentum(self, price_data: pd.DataFrame, indicators: Dict) -> bool:
        """检查做多动量条件"""
        
        # 1. 连续阳线
        if indicators['consecutive_up'] < self.consecutive_candles:
            return False
        
        # 2. 成交量持续放大
        if indicators['avg_volume_ratio'] < self.volume_surge_multiplier:
            return False
        
        # 3. RSI在强势区间但未超买
        if not (self.rsi_min <= indicators['rsi'] <= self.rsi_max):
            return False
        
        # 4. 超强趋势
        if indicators['adx'] < self.adx_threshold:
            return False
        
        # 5. 正向动量足够强
        if indicators['momentum_strength'] < 0.005:  # 平均涨幅 > 0.5%
            return False
        
        print(f"   🔥 做多动量: {indicators['consecutive_up']}连阳, RSI={indicators['rsi']:.1f}, ADX={indicators['adx']:.1f}")
        print(f"   📊 成交量: {indicators['avg_volume_ratio']:.2f}x, 动量强度={indicators['momentum_strength']*100:.2f}%")
        
        return True
    
    def _check_short_momentum(self, price_data: pd.DataFrame, indicators: Dict) -> bool:
        """检查做空动量条件"""
        
        # 1. 连续阴线
        if indicators['consecutive_down'] < self.consecutive_candles:
            return False
        
        # 2. 成交量持续放大
        if indicators['avg_volume_ratio'] < self.volume_surge_multiplier:
            return False
        
        # 3. RSI在弱势区间但未超卖
        # 反向：20-40区间
        if not (20 <= indicators['rsi'] <= 40):
            return False
        
        # 4. 超强趋势
        if indicators['adx'] < self.adx_threshold:
            return False
        
        # 5. 负向动量足够强
        if indicators['momentum_strength'] > -0.005:  # 平均跌幅 > 0.5%
            return False
        
        print(f"   🔥 做空动量: {indicators['consecutive_down']}连阴, RSI={indicators['rsi']:.1f}, ADX={indicators['adx']:.1f}")
        print(f"   📊 成交量: {indicators['avg_volume_ratio']:.2f}x, 动量强度={indicators['momentum_strength']*100:.2f}%")
        
        return True
    
    def _create_long_signal(self, current_price: float, indicators: Dict) -> TradingSignal:
        """创建做多信号"""
        
        # 追踪止损（1.5 ATR）
        stop_loss = current_price - (indicators['atr'] * self.trailing_atr_multiplier)
        
        # 止盈：基于动量强度预测
        expected_move = indicators['momentum_strength'] * 3  # 预期继续这个势头3倍
        take_profit = current_price * (1 + expected_move)
        
        # 置信度
        confidence = self._calculate_confidence(indicators, 'long')
        
        self.entry_time = datetime.now()
        self.highest_price = current_price
        
        return TradingSignal(
            signal_type=SignalType.LONG,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'strategy': self.name,
                'consecutive_candles': indicators['consecutive_up'],
                'rsi': indicators['rsi'],
                'adx': indicators['adx'],
                'volume_ratio': indicators['avg_volume_ratio'],
                'momentum_strength': indicators['momentum_strength'],
                'reason': f'{indicators["consecutive_up"]}连阳 + 超强趋势 + 成交量爆发'
            }
        )
    
    def _create_short_signal(self, current_price: float, indicators: Dict) -> TradingSignal:
        """创建做空信号"""
        
        # 追踪止损（1.5 ATR）
        stop_loss = current_price + (indicators['atr'] * self.trailing_atr_multiplier)
        
        # 止盈
        expected_move = abs(indicators['momentum_strength']) * 3
        take_profit = current_price * (1 - expected_move)
        
        # 置信度
        confidence = self._calculate_confidence(indicators, 'short')
        
        self.entry_time = datetime.now()
        self.lowest_price = current_price
        
        return TradingSignal(
            signal_type=SignalType.SHORT,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'strategy': self.name,
                'consecutive_candles': indicators['consecutive_down'],
                'rsi': indicators['rsi'],
                'adx': indicators['adx'],
                'volume_ratio': indicators['avg_volume_ratio'],
                'momentum_strength': indicators['momentum_strength'],
                'reason': f'{indicators["consecutive_down"]}连阴 + 超强趋势 + 成交量爆发'
            }
        )
    
    def _calculate_confidence(self, indicators: Dict, direction: str) -> float:
        """计算信号置信度"""
        
        confidence = 65.0
        
        # 连续K线越多，置信度越高
        consecutive = indicators['consecutive_up'] if direction == 'long' else indicators['consecutive_down']
        if consecutive >= 5:
            confidence += 15
        elif consecutive >= 4:
            confidence += 10
        elif consecutive >= self.consecutive_candles:
            confidence += 5
        
        # ADX越强，置信度越高
        if indicators['adx'] > 40:
            confidence += 15
        elif indicators['adx'] > 35:
            confidence += 10
        elif indicators['adx'] >= self.adx_threshold:
            confidence += 5
        
        # 成交量放大越多，置信度越高
        if indicators['avg_volume_ratio'] > 2.0:
            confidence += 10
        elif indicators['avg_volume_ratio'] > 1.5:
            confidence += 5
        
        # 动量强度
        momentum_abs = abs(indicators['momentum_strength'])
        if momentum_abs > 0.01:  # 1%
            confidence += 5
        
        return min(95.0, confidence)
    
    def should_exit(self,
                   price_data: pd.DataFrame,
                   entry_price: float,
                   position_side: str) -> bool:
        """
        判断是否应该退出持仓
        
        退出条件：
        1. RSI极端值（>85 或 <15）
        2. 动量衰竭（连续反向K线）
        3. 时间止损
        4. 追踪止损触发
        """
        
        if len(price_data) < 20:
            return False
        
        current_price = price_data['close'].iloc[-1]
        indicators = self._calculate_indicators(price_data)
        
        # 1. RSI极端值退出
        if position_side == 'long' and indicators['rsi'] > 85:
            print(f"   ⚠️ RSI超买退出: {indicators['rsi']:.1f}")
            return True
        if position_side == 'short' and indicators['rsi'] < 15:
            print(f"   ⚠️ RSI超卖退出: {indicators['rsi']:.1f}")
            return True
        
        # 2. 动量衰竭（2根以上反向K线）
        if position_side == 'long':
            if indicators['consecutive_down'] >= 2:
                print(f"   ⚠️ 动量衰竭: {indicators['consecutive_down']}连阴")
                return True
        else:
            if indicators['consecutive_up'] >= 2:
                print(f"   ⚠️ 动量衰竭: {indicators['consecutive_up']}连阳")
                return True
        
        # 3. 时间止损
        if self.entry_time:
            hold_hours = (datetime.now() - self.entry_time).total_seconds() / 3600
            if hold_hours > self.max_hold_hours:
                print(f"   ⏰ 超过最大持仓时间: {hold_hours:.1f}小时")
                return True
        
        # 4. 追踪止损
        if position_side == 'long' and self.highest_price:
            self.highest_price = max(self.highest_price, current_price)
            trailing_stop = self.highest_price - (indicators['atr'] * self.trailing_atr_multiplier)
            if current_price < trailing_stop:
                print(f"   🛑 追踪止损触发: {current_price:.2f} < {trailing_stop:.2f}")
                return True
        
        if position_side == 'short' and self.lowest_price:
            self.lowest_price = min(self.lowest_price, current_price)
            trailing_stop = self.lowest_price + (indicators['atr'] * self.trailing_atr_multiplier)
            if current_price > trailing_stop:
                print(f"   🛑 追踪止损触发: {current_price:.2f} > {trailing_stop:.2f}")
                return True
        
        return False
    
    def calculate_position_size(self,
                               account_balance: float,
                               signal: TradingSignal) -> float:
        """计算仓位大小 - 动量策略采用激进仓位"""
        
        if not signal.stop_loss:
            return 0.0
        
        # 每次交易风险2%（较激进）
        risk_per_trade = 0.02
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
        
        # 限制最大仓位（50%）
        max_position = account_balance * 0.5 / signal.entry_price
        position_size = min(position_size, max_position)
        
        return position_size
    
    # 注意：_calculate_rsi, _calculate_atr, _calculate_adx 方法已从 BaseStrategy 继承
