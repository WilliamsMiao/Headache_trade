"""
增强趋势跟随策略
基于唐奇安通道 + 布林带突破 + ATR动态止损
适用于明确趋势市场
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from .base import BaseStrategy, TradingSignal, SignalType


class TrendFollowingStrategy(BaseStrategy):
    """趋势跟随策略"""
    
    def __init__(self, channel_period: int = 20, max_pyramid: int = 3):
        """
        Args:
            channel_period: 唐奇安通道周期
            max_pyramid: 最大加仓次数
        """
        super().__init__(
            name="Trend Following",
            description="增强趋势跟随策略（海龟交易法则）"
        )
        
        self.channel_period = channel_period
        self.max_pyramid = max_pyramid
        self.pyramid_count = 0
        self.last_pyramid_price = None
    
    def generate_signal(self, price_data: pd.DataFrame,
                       current_position: Optional[Dict] = None) -> TradingSignal:
        """生成交易信号"""
        
        current_price = price_data['close'].iloc[-1]
        
        # 计算指标
        indicators = self._calculate_indicators(price_data)
        
        # 检查入场条件
        signal_type = self._check_entry_conditions(price_data, indicators, current_position)
        
        if signal_type == SignalType.HOLD:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                confidence=0,
                entry_price=current_price
            )
        
        # 计算止损止盈
        atr = indicators['atr']
        stop_loss, take_profit = self._calculate_tp_sl(
            current_price, signal_type, atr
        )
        
        # 计算置信度
        confidence = self._calculate_confidence(indicators)
        
        return TradingSignal(
            signal_type=signal_type,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                'atr': atr,
                'adx': indicators['adx'],
                'macd_signal': 'bullish' if indicators['macd'] > indicators['macd_signal'] else 'bearish',
                'strategy': self.name
            }
        )
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # 唐奇安通道
        donchian_high = high.rolling(self.channel_period).max().iloc[-1]
        donchian_low = low.rolling(self.channel_period).min().iloc[-1]
        
        # 布林带
        bb_middle = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = (bb_middle + 2 * bb_std).iloc[-1]
        bb_lower = (bb_middle - 2 * bb_std).iloc[-1]
        
        # ATR
        atr = self._calculate_atr(df)
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = (ema12 - ema26).iloc[-1]
        macd_signal = (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1]
        
        # ADX
        adx = self._calculate_adx(df)
        
        # 成交量
        avg_volume = volume.rolling(20).mean().iloc[-1]
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0
        
        return {
            'donchian_high': donchian_high,
            'donchian_low': donchian_low,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'atr': atr,
            'macd': macd,
            'macd_signal': macd_signal,
            'adx': adx,
            'volume_ratio': volume_ratio
        }
    
    def _check_entry_conditions(self, df: pd.DataFrame, indicators: Dict,
                                current_position: Optional[Dict]) -> SignalType:
        """检查入场条件"""
        current_price = df['close'].iloc[-1]
        
        # 已有持仓，检查是否加仓
        if current_position:
            return self._check_pyramid_conditions(current_price, current_position, indicators)
        
        # 多头入场条件
        if self._check_long_entry(current_price, indicators):
            return SignalType.BUY
        
        # 空头入场条件
        if self._check_short_entry(current_price, indicators):
            return SignalType.SELL
        
        return SignalType.HOLD
    
    def _check_long_entry(self, current_price: float, indicators: Dict) -> bool:
        """检查做多条件"""
        # 1. 突破唐奇安通道上轨
        if current_price < indicators['donchian_high']:
            return False
        
        # 2. ADX确认趋势强度
        if indicators['adx'] < 25:
            return False
        
        # 3. MACD金叉
        if indicators['macd'] <= indicators['macd_signal']:
            return False
        
        # 4. 成交量放大
        if indicators['volume_ratio'] < 1.2:
            return False
        
        return True
    
    def _check_short_entry(self, current_price: float, indicators: Dict) -> bool:
        """检查做空条件"""
        # 1. 突破唐奇安通道下轨
        if current_price > indicators['donchian_low']:
            return False
        
        # 2. ADX确认趋势强度
        if indicators['adx'] < 25:
            return False
        
        # 3. MACD死叉
        if indicators['macd'] >= indicators['macd_signal']:
            return False
        
        # 4. 成交量放大
        if indicators['volume_ratio'] < 1.2:
            return False
        
        return True
    
    def _check_pyramid_conditions(self, current_price: float,
                                  current_position: Dict, indicators: Dict) -> SignalType:
        """检查加仓条件"""
        # 已达到最大加仓次数
        if self.pyramid_count >= self.max_pyramid:
            return SignalType.HOLD
        
        entry_price = current_position.get('entry_price', 0)
        position_side = current_position.get('side', '')
        atr = indicators['atr']
        
        # 多头加仓
        if position_side == 'long':
            # 价格上涨0.5 ATR
            if self.last_pyramid_price is None:
                pyramid_threshold = entry_price + (0.5 * atr)
            else:
                pyramid_threshold = self.last_pyramid_price + (0.5 * atr)
            
            if current_price > pyramid_threshold:
                self.pyramid_count += 1
                self.last_pyramid_price = current_price
                return SignalType.BUY
        
        # 空头加仓
        elif position_side == 'short':
            # 价格下跌0.5 ATR
            if self.last_pyramid_price is None:
                pyramid_threshold = entry_price - (0.5 * atr)
            else:
                pyramid_threshold = self.last_pyramid_price - (0.5 * atr)
            
            if current_price < pyramid_threshold:
                self.pyramid_count += 1
                self.last_pyramid_price = current_price
                return SignalType.SELL
        
        return SignalType.HOLD
    
    def _calculate_tp_sl(self, current_price: float, signal_type: SignalType,
                        atr: float) -> tuple:
        """计算止盈止损"""
        if signal_type == SignalType.BUY:
            stop_loss = current_price - (2 * atr)  # 2 ATR止损
            take_profit = None  # 使用跟踪止损，不设固定止盈
        
        elif signal_type == SignalType.SELL:
            stop_loss = current_price + (2 * atr)
            take_profit = None
        
        else:
            return None, None
        
        return stop_loss, take_profit
    
    def _calculate_confidence(self, indicators: Dict) -> float:
        """计算信号置信度"""
        confidence = 50.0
        
        # ADX强度加分
        if indicators['adx'] > 30:
            confidence += 20
        elif indicators['adx'] > 25:
            confidence += 10
        
        # MACD背离度加分
        macd_divergence = abs(indicators['macd'] - indicators['macd_signal'])
        if macd_divergence > 0.001:
            confidence += 10
        
        # 成交量加分
        if indicators['volume_ratio'] > 1.5:
            confidence += 15
        elif indicators['volume_ratio'] > 1.2:
            confidence += 10
        
        return min(95.0, confidence)
    
    def should_exit(self, price_data: pd.DataFrame,
                   entry_price: float, position_side: str) -> bool:
        """判断是否退出"""
        close = price_data['close']
        high = price_data['high']
        low = price_data['low']
        
        # 计算10日唐奇安通道（退出通道）
        exit_period = 10
        
        if position_side == 'long':
            # 跌破10日低点退出
            exit_channel = low.rolling(exit_period).min().iloc[-1]
            if close.iloc[-1] < exit_channel:
                self._reset_pyramid()
                return True
        
        elif position_side == 'short':
            # 突破10日高点退出
            exit_channel = high.rolling(exit_period).max().iloc[-1]
            if close.iloc[-1] > exit_channel:
                self._reset_pyramid()
                return True
        
        return False
    
    def calculate_position_size(self, account_balance: float,
                               signal: TradingSignal) -> float:
        """计算仓位大小"""
        # 基础仓位：账户的1%风险
        risk_per_trade = account_balance * 0.01
        
        # 根据止损计算仓位
        if signal.stop_loss:
            price_risk = abs(signal.entry_price - signal.stop_loss)
            position_size = risk_per_trade / price_risk
        else:
            # 默认仓位
            position_size = account_balance * 0.3 / signal.entry_price
        
        # 加仓时减半
        if self.pyramid_count > 0:
            position_size *= 0.5
        
        return round(position_size, 3)
    
    def _reset_pyramid(self):
        """重置加仓计数"""
        self.pyramid_count = 0
        self.last_pyramid_price = None
    
    # 注意：_calculate_atr, _calculate_adx 方法已从 BaseStrategy 继承
    # 但 trend_following 策略中需要返回单个值而不是Series，所以包装一下
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ATR（返回单个值）"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        atr_series = super()._calculate_atr(high, low, close, period)
        return atr_series.iloc[-1] if not np.isnan(atr_series.iloc[-1]) else (high.iloc[-1] - low.iloc[-1])
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """计算ADX（返回单个值）"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        adx_series = super()._calculate_adx(high, low, close, period)
        return adx_series.iloc[-1] if not np.isnan(adx_series.iloc[-1]) else 0
