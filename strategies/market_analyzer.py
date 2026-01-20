"""
市场分析器
分析市场状态，包括波动率、震荡强度、趋势强度等指标
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List


class MarketAnalyzer:
    """市场分析器 - 分析市场状态和特征"""
    
    def __init__(self, atr_period: int = 14, lookback_period: int = 50):
        """
        初始化市场分析器
        
        Args:
            atr_period: ATR计算周期
            lookback_period: 回看周期（用于计算震荡强度等）
        """
        self.atr_period = atr_period
        self.lookback_period = lookback_period
    
    def analyze_market(self, df: pd.DataFrame, index: int) -> Dict:
        """
        分析当前市场状态
        
        Args:
            df: 历史K线数据
            index: 当前K线索引
            
        Returns:
            市场分析结果字典
        """
        if index < max(self.atr_period, self.lookback_period):
            # 数据不足，返回默认值
            return self._get_default_analysis()
        
        # 计算ATR和波动率
        atr_pct = self._calculate_atr_percentage(df, index)
        volatility_level = self._classify_volatility(atr_pct)
        
        # 计算震荡强度
        oscillation_strength = self._calculate_oscillation_strength(df, index)
        
        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(df, index)
        
        # 分析成交量
        volume_profile = self._analyze_volume(df, index)
        
        # 综合判断市场状态
        market_regime = self._classify_regime(
            volatility_level, oscillation_strength, trend_strength
        )
        
        return {
            'volatility_level': volatility_level,
            'atr_pct': atr_pct,
            'oscillation_strength': oscillation_strength,
            'trend_strength': trend_strength,
            'volume_profile': volume_profile,
            'market_regime': market_regime,
            'timestamp': df['timestamp'].iloc[index] if 'timestamp' in df.columns else None
        }
    
    def _calculate_atr_percentage(self, df: pd.DataFrame, index: int) -> float:
        """计算ATR百分比"""
        if index < self.atr_period:
            return 0.0
        
        window_df = df.iloc[max(0, index - self.atr_period * 2):index + 1].copy()
        
        # 计算True Range
        high_low = window_df['high'] - window_df['low']
        high_close = abs(window_df['high'] - window_df['close'].shift(1))
        low_close = abs(window_df['low'] - window_df['close'].shift(1))
        
        window_df['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # 计算ATR
        atr = window_df['tr'].rolling(self.atr_period).mean().iloc[-1]
        current_price = window_df['close'].iloc[-1]
        
        if current_price > 0:
            return atr / current_price
        return 0.0
    
    def _classify_volatility(self, atr_pct: float) -> str:
        """
        分类波动率水平
        
        Args:
            atr_pct: ATR百分比
            
        Returns:
            'low', 'medium', 'high'
        """
        if atr_pct < 0.005:  # < 0.5%
            return 'low'
        elif atr_pct < 0.02:  # 0.5% - 2%
            return 'medium'
        else:  # > 2%
            return 'high'
    
    def _calculate_oscillation_strength(self, df: pd.DataFrame, index: int) -> float:
        """
        计算震荡强度（0-1）
        
        基于价格在区间内的来回波动频率
        """
        if index < self.lookback_period:
            return 0.5  # 默认中等震荡
        
        window_df = df.iloc[max(0, index - self.lookback_period):index + 1].copy()
        
        # 计算布林带
        window_df['bb_middle'] = window_df['close'].rolling(20).mean()
        bb_std = window_df['close'].rolling(20).std()
        window_df['bb_upper'] = window_df['bb_middle'] + (bb_std * 2)
        window_df['bb_lower'] = window_df['bb_middle'] - (bb_std * 2)
        
        # 计算价格在布林带内的位置
        window_df['bb_position'] = (window_df['close'] - window_df['bb_lower']) / (
            window_df['bb_upper'] - window_df['bb_lower']
        )
        
        # 计算价格穿越中线的次数（震荡指标）
        crosses = 0
        prev_position = None
        for pos in window_df['bb_position'].dropna():
            if prev_position is not None:
                # 价格从上方穿越中线到下方，或从下方穿越到上方
                if (prev_position > 0.5 and pos <= 0.5) or (prev_position < 0.5 and pos >= 0.5):
                    crosses += 1
            prev_position = pos
        
        # 归一化到0-1（基于回看周期）
        oscillation_strength = min(crosses / (self.lookback_period / 10), 1.0)
        
        # 计算价格区间宽度（窄区间 = 强震荡）
        price_range = (window_df['high'].max() - window_df['low'].min()) / window_df['close'].mean()
        range_factor = min(price_range / 0.05, 1.0)  # 5%作为参考
        
        # 综合震荡强度（穿越次数 + 区间宽度）
        final_strength = (oscillation_strength * 0.6 + (1 - range_factor) * 0.4)
        
        return max(0.0, min(1.0, final_strength))
    
    def _calculate_trend_strength(self, df: pd.DataFrame, index: int) -> float:
        """
        计算趋势强度（0-1）
        
        基于ADX指标和均线排列
        """
        if index < max(self.lookback_period, 50):
            return 0.5  # 默认中等趋势
        
        window_df = df.iloc[max(0, index - self.lookback_period):index + 1].copy()
        
        # 计算ADX
        high = window_df['high']
        low = window_df['low']
        close = window_df['close']
        
        # +DM 和 -DM
        up_move = high.diff()
        down_move = -low.diff()
        
        plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
        minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
        
        # True Range
        high_low = high - low
        high_close = abs(high - close.shift(1))
        low_close = abs(low - close.shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # 平滑TR
        atr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()
        
        # +DI 和 -DI
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth.replace(0, np.nan))
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth.replace(0, np.nan))
        
        # DX
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        
        # ADX
        adx = dx.ewm(alpha=1/14, adjust=False).mean().iloc[-1]
        
        # 计算均线排列
        window_df['sma_20'] = window_df['close'].rolling(20).mean()
        window_df['sma_50'] = window_df['close'].rolling(50).mean()
        
        current_price = window_df['close'].iloc[-1]
        sma_20 = window_df['sma_20'].iloc[-1]
        sma_50 = window_df['sma_50'].iloc[-1]
        
        # 检查多头排列或空头排列
        bullish_alignment = current_price > sma_20 > sma_50
        bearish_alignment = current_price < sma_20 < sma_50
        
        alignment_strength = 1.0 if (bullish_alignment or bearish_alignment) else 0.5
        
        # 综合趋势强度：ADX（0-100）归一化 + 均线排列
        adx_strength = min(adx / 50.0, 1.0) if not pd.isna(adx) else 0.5
        trend_strength = (adx_strength * 0.7 + alignment_strength * 0.3)
        
        return max(0.0, min(1.0, trend_strength))
    
    def _analyze_volume(self, df: pd.DataFrame, index: int) -> str:
        """
        分析成交量特征
        
        Returns:
            'low', 'normal', 'high'
        """
        if index < 20:
            return 'normal'
        
        window_df = df.iloc[max(0, index - 20):index + 1]
        current_volume = window_df['volume'].iloc[-1]
        volume_ma = window_df['volume'].rolling(20).mean().iloc[-1]
        
        if volume_ma == 0:
            return 'normal'
        
        volume_ratio = current_volume / volume_ma
        
        if volume_ratio < 0.8:
            return 'low'
        elif volume_ratio > 1.5:
            return 'high'
        else:
            return 'normal'
    
    def _classify_regime(
        self,
        volatility_level: str,
        oscillation_strength: float,
        trend_strength: float
    ) -> str:
        """
        分类市场状态
        
        Returns:
            'ranging', 'trending', 'volatile'
        """
        # 震荡市场：震荡强度高，趋势强度低
        if oscillation_strength > 0.6 and trend_strength < 0.4:
            return 'ranging'
        
        # 趋势市场：趋势强度高，震荡强度低
        if trend_strength > 0.6 and oscillation_strength < 0.4:
            return 'trending'
        
        # 高波动市场：波动率高，但无明显趋势或震荡
        if volatility_level == 'high':
            return 'volatile'
        
        # 默认：根据趋势强度判断
        if trend_strength > 0.5:
            return 'trending'
        else:
            return 'ranging'
    
    def _get_default_analysis(self) -> Dict:
        """返回默认市场分析结果"""
        return {
            'volatility_level': 'medium',
            'atr_pct': 0.01,
            'oscillation_strength': 0.5,
            'trend_strength': 0.5,
            'volume_profile': 'normal',
            'market_regime': 'ranging',
            'timestamp': None
        }
    
    def analyze_market_states(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """
        分析整个历史数据的市场状态分布
        
        Args:
            df: 完整的历史数据
            
        Returns:
            字典，键为市场状态，值为该状态下的K线索引列表
        """
        market_states = {
            'ranging': [],
            'trending': [],
            'volatile': []
        }
        
        start_index = max(self.atr_period, self.lookback_period)
        
        for i in range(start_index, len(df)):
            analysis = self.analyze_market(df, i)
            regime = analysis['market_regime']
            if regime in market_states:
                market_states[regime].append(i)
        
        return market_states
