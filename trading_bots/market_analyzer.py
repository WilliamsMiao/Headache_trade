"""
市场环境分析器
识别当前市场状态：趋势/震荡/突破等
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from enum import Enum
from dataclasses import dataclass


class MarketRegime(Enum):
    """市场状态枚举"""
    STRONG_TREND = "strong_trend"          # 强趋势
    WEAK_TREND = "weak_trend"              # 弱趋势
    RANGE_BOUND = "range_bound"            # 震荡区间
    HIGH_VOLATILITY = "high_volatility"    # 高波动
    BREAKOUT_PENDING = "breakout_pending"  # 突破前夜
    UNKNOWN = "unknown"                     # 未知


@dataclass
class MarketState:
    """市场状态数据类"""
    regime: MarketRegime
    trend_strength: float  # 0-100
    volatility: float      # 波动率百分比
    confidence: float      # 识别置信度 0-100
    adx: float
    atr_pct: float
    bb_width: float
    volume_ratio: float
    recommendation: str    # 推荐策略


class MarketAnalyzer:
    """市场环境分析器"""
    
    def __init__(self):
        self.history = []  # 历史状态
        
    def analyze(self, price_data: pd.DataFrame) -> MarketState:
        """
        分析市场环境
        
        Args:
            price_data: OHLCV数据
        
        Returns:
            MarketState: 市场状态
        """
        # 计算各项指标
        trend_strength = self._calculate_trend_strength(price_data)
        volatility = self._calculate_volatility(price_data)
        adx = self._calculate_adx(price_data)
        atr_pct = self._calculate_atr_percentage(price_data)
        bb_width = self._calculate_bb_width(price_data)
        volume_ratio = self._calculate_volume_ratio(price_data)
        
        # 识别市场状态
        regime, confidence = self._classify_regime(
            adx, atr_pct, bb_width, volume_ratio, price_data
        )
        
        # 生成推荐
        recommendation = self._generate_recommendation(regime)
        
        state = MarketState(
            regime=regime,
            trend_strength=trend_strength,
            volatility=volatility,
            confidence=confidence,
            adx=adx,
            atr_pct=atr_pct,
            bb_width=bb_width,
            volume_ratio=volume_ratio,
            recommendation=recommendation
        )
        
        self.history.append(state)
        return state
    
    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """计算趋势强度 0-100"""
        close = df['close']
        
        # 多周期均线排列
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        
        current_price = close.iloc[-1]
        
        strength = 0
        
        # 均线多头排列
        if ma5 > ma10 > ma20 > ma50:
            strength += 40
        elif ma5 < ma10 < ma20 < ma50:
            strength += 40
        
        # 价格与均线关系
        if current_price > ma20:
            strength += 20
        elif current_price < ma20:
            strength += 20
        
        # 均线斜率
        ma20_slope = (close.rolling(20).mean().iloc[-1] - 
                     close.rolling(20).mean().iloc[-5]) / 5
        if abs(ma20_slope) > 0:
            strength += min(40, abs(ma20_slope) * 1000)
        
        return min(100, strength)
    
    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """计算波动率百分比"""
        returns = df['close'].pct_change()
        volatility = returns.rolling(20).std().iloc[-1] * np.sqrt(365) * 100
        return volatility if not np.isnan(volatility) else 0
    
    def _calculate_adx(self, df: pd.DataFrame) -> float:
        """计算ADX"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        # +DM and -DM
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)
        
        plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
        minus_dm[(down_move > up_move) & (down_move > 0)] = down_move
        
        # +DI and -DI
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean().iloc[-1]
        
        return adx if not np.isnan(adx) else 0
    
    def _calculate_atr_percentage(self, df: pd.DataFrame) -> float:
        """计算ATR占价格的百分比"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        current_price = close.iloc[-1]
        atr_pct = (atr / current_price) * 100
        
        return atr_pct if not np.isnan(atr_pct) else 0
    
    def _calculate_bb_width(self, df: pd.DataFrame) -> float:
        """计算布林带宽度（标准化）"""
        close = df['close']
        ma = close.rolling(20).mean()
        std = close.rolling(20).std()
        
        upper = ma + (2 * std)
        lower = ma - (2 * std)
        
        bb_width = ((upper - lower) / ma).iloc[-1] * 100
        
        return bb_width if not np.isnan(bb_width) else 0
    
    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float:
        """计算成交量比率"""
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        
        ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        return ratio if not np.isnan(ratio) else 1.0
    
    def _classify_regime(self, adx: float, atr_pct: float, bb_width: float,
                         volume_ratio: float, df: pd.DataFrame) -> Tuple[MarketRegime, float]:
        """
        分类市场状态
        
        Returns:
            (MarketRegime, confidence)
        """
        confidence = 0
        
        # 1. 强趋势市场
        if adx > 30:
            confidence = min(100, (adx - 30) * 2 + 70)
            return MarketRegime.STRONG_TREND, confidence
        
        # 2. 弱趋势市场
        if 20 < adx <= 30:
            confidence = 60 + (adx - 20)
            return MarketRegime.WEAK_TREND, confidence
        
        # 3. 突破前夜（BB收窄 + 成交量萎缩）
        if bb_width < 3.0 and volume_ratio < 0.8:
            # 检查是否有长时间整理
            close = df['close']
            price_range = (close.iloc[-20:].max() - close.iloc[-20:].min()) / close.iloc[-1]
            
            if price_range < 0.05:  # 价格区间小于5%
                confidence = 70
                return MarketRegime.BREAKOUT_PENDING, confidence
        
        # 4. 高波动震荡
        if adx < 20 and atr_pct > 3.0:
            confidence = 65
            return MarketRegime.HIGH_VOLATILITY, confidence
        
        # 5. 震荡区间
        if adx < 20:
            confidence = 70 - adx  # ADX越低，震荡越明显
            return MarketRegime.RANGE_BOUND, confidence
        
        # 未知状态
        return MarketRegime.UNKNOWN, 30
    
    def _generate_recommendation(self, regime: MarketRegime) -> str:
        """生成策略推荐"""
        recommendations = {
            MarketRegime.STRONG_TREND: "趋势跟随策略(70%) + 动量策略(30%)",
            MarketRegime.WEAK_TREND: "趋势跟随策略(50%) + 突破策略(50%)",
            MarketRegime.RANGE_BOUND: "网格交易策略(80%) + 均值回归策略(20%)",
            MarketRegime.HIGH_VOLATILITY: "均值回归策略(60%) + 观望(40%)",
            MarketRegime.BREAKOUT_PENDING: "突破策略(70%) + 观望(30%)",
            MarketRegime.UNKNOWN: "观望，等待明确信号"
        }
        
        return recommendations.get(regime, "观望")
    
    def get_regime_history(self, periods: int = 24) -> pd.DataFrame:
        """
        获取历史市场状态
        
        Args:
            periods: 回看周期数
        
        Returns:
            DataFrame: 历史状态数据
        """
        if not self.history:
            return pd.DataFrame()
        
        recent = self.history[-periods:]
        
        data = {
            'regime': [s.regime.value for s in recent],
            'trend_strength': [s.trend_strength for s in recent],
            'volatility': [s.volatility for s in recent],
            'confidence': [s.confidence for s in recent],
            'adx': [s.adx for s in recent],
            'atr_pct': [s.atr_pct for s in recent],
            'bb_width': [s.bb_width for s in recent],
        }
        
        return pd.DataFrame(data)
    
    def detect_regime_change(self) -> bool:
        """检测市场状态是否发生变化"""
        if len(self.history) < 2:
            return False
        
        current = self.history[-1]
        previous = self.history[-2]
        
        # 状态切换
        if current.regime != previous.regime:
            return True
        
        # ADX显著变化
        if abs(current.adx - previous.adx) > 10:
            return True
        
        # 波动率显著变化
        if abs(current.volatility - previous.volatility) > current.volatility * 0.3:
            return True
        
        return False


# 便捷函数
def analyze_market(price_data: pd.DataFrame) -> MarketState:
    """快速市场分析"""
    analyzer = MarketAnalyzer()
    return analyzer.analyze(price_data)


def get_market_regime_name(regime: MarketRegime) -> str:
    """获取市场状态中文名称"""
    names = {
        MarketRegime.STRONG_TREND: "强趋势",
        MarketRegime.WEAK_TREND: "弱趋势",
        MarketRegime.RANGE_BOUND: "震荡区间",
        MarketRegime.HIGH_VOLATILITY: "高波动",
        MarketRegime.BREAKOUT_PENDING: "突破前夜",
        MarketRegime.UNKNOWN: "未知"
    }
    return names.get(regime, "未知")
