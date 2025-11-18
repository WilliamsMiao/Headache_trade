"""
均值回归策略
适用于超买超卖的震荡市场
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict

from strategies.base_strategy import BaseStrategy, TradingSignal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """均值回归策略 - 捕捉价格回归均值的机会"""
    
    def __init__(self, 
                 rsi_period: int = 14,
                 rsi_oversold: float = 35,  # 放宽至35
                 rsi_overbought: float = 65,  # 放宽至65
                 bb_period: int = 20,
                 bb_std: float = 2.0,
                 volume_threshold: float = 1.5,  # 放宽至1.5
                 max_hold_hours: int = 48):
        
        super().__init__(
            name="MeanReversionStrategy",
            description="均值回归策略 - RSI超买超卖 + 布林带偏离"
        )
        
        # RSI参数
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        
        # 布林带参数
        self.bb_period = bb_period
        self.bb_std = bb_std
        
        # 其他参数
        self.volume_threshold = volume_threshold
        self.max_hold_hours = max_hold_hours
        
        # 持仓信息
        self.entry_time = None
    
    def generate_signal(self, 
                       price_data: pd.DataFrame,
                       current_position: Optional[Dict] = None) -> Optional[TradingSignal]:
        """
        生成均值回归信号
        
        策略逻辑：
        1. RSI识别超买超卖
        2. 布林带确认偏离
        3. 成交量萎缩确认
        4. 非强趋势市场（ADX < 25）
        """
        
        if len(price_data) < max(self.rsi_period, self.bb_period) + 10:
            return None
        
        # 计算指标
        indicators = self._calculate_indicators(price_data)
        
        current_price = price_data['close'].iloc[-1]
        
        # 检查是否应该退出现有持仓
        if current_position:
            return None  # 均值回归策略只关注入场，退出由should_exit处理
        
        # 检查做多机会（超卖反弹）
        long_signal = self._check_long_entry(current_price, indicators)
        if long_signal:
            return self._create_long_signal(current_price, indicators)
        
        # 检查做空机会（超买回落）
        short_signal = self._check_short_entry(current_price, indicators)
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
        rsi = self._calculate_rsi(close, self.rsi_period)
        
        # 布林带
        bb_middle = close.rolling(window=self.bb_period).mean()
        bb_std_val = close.rolling(window=self.bb_period).std()
        bb_upper = bb_middle + (bb_std_val * self.bb_std)
        bb_lower = bb_middle - (bb_std_val * self.bb_std)
        
        # 布林带位置（0-1，0=下轨，1=上轨）
        bb_position = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
        
        # ATR
        atr = self._calculate_atr(high, low, close, 14)
        
        # ADX（趋势强度）
        adx = self._calculate_adx(high, low, close, 14)
        
        # 成交量比率
        volume_ma = volume.rolling(window=20).mean()
        volume_ratio = volume.iloc[-1] / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1.0
        
        # 价格距离均值的百分比
        distance_from_mean = abs(close.iloc[-1] - bb_middle.iloc[-1]) / bb_middle.iloc[-1] * 100
        
        return {
            'rsi': rsi.iloc[-1],
            'bb_upper': bb_upper.iloc[-1],
            'bb_middle': bb_middle.iloc[-1],
            'bb_lower': bb_lower.iloc[-1],
            'bb_position': bb_position,
            'atr': atr.iloc[-1],
            'adx': adx.iloc[-1],
            'volume_ratio': volume_ratio,
            'distance_from_mean': distance_from_mean
        }
    
    def _check_long_entry(self, current_price: float, indicators: Dict) -> bool:
        """检查做多条件（超卖反弹）"""
        
        # 1. RSI超卖
        if indicators['rsi'] > self.rsi_oversold:
            return False
        
        # 2. 价格触及或突破布林带下轨
        if current_price > indicators['bb_lower'] * 1.01:  # 放宽至1%偏差
            return False
        
        # 3. 非强趋势市场（放宽）
        if indicators['adx'] > 35:  # 从25放宽到35
            return False
        
        # 4. 价格显著偏离均值（放宽）
        if indicators['distance_from_mean'] < 1.0:  # 从1.5%放宽到1.0%
            return False
        
        return True
    
    def _check_short_entry(self, current_price: float, indicators: Dict) -> bool:
        """检查做空条件（超买回落）"""
        
        # 1. RSI超买
        if indicators['rsi'] < self.rsi_overbought:
            return False
        
        # 2. 价格触及或突破布林带上轨
        if current_price < indicators['bb_upper'] * 0.99:  # 放宽至1%偏差
            return False
        
        # 3. 非强趋势市场（放宽）
        if indicators['adx'] > 35:  # 从25放宽到35
            return False
        
        # 4. 价格显著偏离均值（放宽）
        if indicators['distance_from_mean'] < 1.0:  # 从1.5%放宽到1.0%
            return False
        
        return True
        
        # 5. 价格显著偏离均值
        if indicators['distance_from_mean'] < 1.5:
            return False
        
        return True
    
    def _create_long_signal(self, current_price: float, indicators: Dict) -> TradingSignal:
        """创建做多信号"""
        
        # 止损：布林带下轨下方1 ATR
        stop_loss = indicators['bb_lower'] - indicators['atr']
        
        # 止盈：布林带中轨（均值回归目标）
        take_profit = indicators['bb_middle']
        
        # 置信度计算
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
                'rsi': indicators['rsi'],
                'bb_position': indicators['bb_position'],
                'distance_from_mean': indicators['distance_from_mean'],
                'reason': 'RSI超卖 + 布林带下轨 + 成交量萎缩'
            }
        )
    
    def _create_short_signal(self, current_price: float, indicators: Dict) -> TradingSignal:
        """创建做空信号"""
        
        # 止损：布林带上轨上方1 ATR
        stop_loss = indicators['bb_upper'] + indicators['atr']
        
        # 止盈：布林带中轨（均值回归目标）
        take_profit = indicators['bb_middle']
        
        # 置信度计算
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
                'rsi': indicators['rsi'],
                'bb_position': indicators['bb_position'],
                'distance_from_mean': indicators['distance_from_mean'],
                'reason': 'RSI超买 + 布林带上轨 + 成交量萎缩'
            }
        )
    
    def _calculate_confidence(self, indicators: Dict, direction: str) -> float:
        """计算信号置信度"""
        
        confidence = 50.0
        
        if direction == 'long':
            # RSI越低，置信度越高
            if indicators['rsi'] < 25:
                confidence += 20
            elif indicators['rsi'] < 30:
                confidence += 10
            
            # 价格越接近下轨，置信度越高
            if indicators['bb_position'] < 0.1:
                confidence += 15
            elif indicators['bb_position'] < 0.2:
                confidence += 10
            
        else:  # short
            # RSI越高，置信度越高
            if indicators['rsi'] > 75:
                confidence += 20
            elif indicators['rsi'] > 70:
                confidence += 10
            
            # 价格越接近上轨，置信度越高
            if indicators['bb_position'] > 0.9:
                confidence += 15
            elif indicators['bb_position'] > 0.8:
                confidence += 10
        
        # 成交量萎缩程度
        if indicators['volume_ratio'] < 0.6:
            confidence += 10
        elif indicators['volume_ratio'] < 0.8:
            confidence += 5
        
        # 偏离均值程度
        if indicators['distance_from_mean'] > 3:
            confidence += 10
        elif indicators['distance_from_mean'] > 2:
            confidence += 5
        
        # ADX越低（非趋势），置信度越高
        if indicators['adx'] < 15:
            confidence += 5
        
        return min(95.0, confidence)
    
    def should_exit(self, 
                   price_data: pd.DataFrame,
                   entry_price: float,
                   position_side: str) -> bool:
        """
        判断是否应该退出持仓
        
        退出条件：
        1. 价格回归布林带中轨（目标达成）
        2. RSI回归中性区域（50附近）
        3. 时间止损（超过最大持仓时间）
        4. 止损触发
        """
        
        if len(price_data) < self.bb_period:
            return False
        
        current_price = price_data['close'].iloc[-1]
        
        # 计算指标
        indicators = self._calculate_indicators(price_data)
        
        # 1. 价格回归中轨（成功）
        if position_side == 'long':
            if current_price >= indicators['bb_middle']:
                print(f"   ✅ 均值回归成功，价格回到中轨")
                return True
            
            # RSI回归中性
            if indicators['rsi'] > 45:
                print(f"   ✅ RSI回归中性区域")
                return True
        
        else:  # short
            if current_price <= indicators['bb_middle']:
                print(f"   ✅ 均值回归成功，价格回到中轨")
                return True
            
            # RSI回归中性
            if indicators['rsi'] < 55:
                print(f"   ✅ RSI回归中性区域")
                return True
        
        # 2. 时间止损
        if self.entry_time:
            hold_hours = (pd.Timestamp.now() - self.entry_time).total_seconds() / 3600
            if hold_hours > self.max_hold_hours:
                print(f"   ⏰ 超过最大持仓时间 {self.max_hold_hours}小时")
                return True
        
        # 3. 止损检查（由风险管理模块处理，这里做额外检查）
        if position_side == 'long':
            if current_price < indicators['bb_lower'] - indicators['atr']:
                print(f"   🛑 触发止损")
                return True
        else:
            if current_price > indicators['bb_upper'] + indicators['atr']:
                print(f"   🛑 触发止损")
                return True
        
        return False
    
    def calculate_position_size(self, 
                               account_balance: float,
                               signal: TradingSignal) -> float:
        """
        计算仓位大小
        
        均值回归策略：较保守的仓位
        """
        
        if not signal.stop_loss:
            return 0.0
        
        # 每次交易风险0.8%（比趋势策略更保守）
        risk_per_trade = 0.008
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
        
        # 限制最大仓位（单次最多30%资金）
        max_position = account_balance * 0.3 / signal.entry_price
        position_size = min(position_size, max_position)
        
        return position_size
    
    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """计算RSI"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, 
                      close: pd.Series, period: int) -> pd.Series:
        """计算ATR"""
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, 
                      close: pd.Series, period: int) -> pd.Series:
        """计算ADX"""
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        atr = self._calculate_atr(high, low, close, period)
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
