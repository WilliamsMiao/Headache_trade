"""
市场状态识别器 - Market Regime Detector
识别市场处于趋势市还是震荡市，为策略选择提供依据

Author: AI Assistant
Date: 2025-11-18
"""

import pandas as pd
import numpy as np
from typing import Dict, Literal, Tuple
from dataclasses import dataclass


@dataclass
class MarketRegime:
    """市场状态数据类"""
    regime: Literal['trending', 'ranging', 'volatile', 'neutral']  # 市场状态
    trend_direction: Literal['up', 'down', 'sideways']  # 趋势方向
    confidence: float  # 置信度 (0-1)
    adx_value: float  # ADX指标值
    volatility: float  # 波动率
    trend_strength: float  # 趋势强度
    range_strength: float  # 震荡强度
    recommended_strategies: list  # 推荐策略


class MarketRegimeDetector:
    """
    市场状态识别器
    
    识别逻辑：
    1. 使用ADX判断趋势强度
    2. 使用ATR判断波动率
    3. 使用价格区间判断震荡特征
    4. 综合评分决定市场状态
    """
    
    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        volatility_period: int = 20,
        adx_trending_threshold: float = 25.0,  # ADX > 25 为趋势市
        adx_strong_threshold: float = 40.0,    # ADX > 40 为强趋势
        volatility_threshold: float = 0.02     # 波动率阈值 2%
    ):
        """
        初始化市场状态识别器
        
        Args:
            adx_period: ADX周期
            atr_period: ATR周期
            volatility_period: 波动率计算周期
            adx_trending_threshold: 趋势市ADX阈值
            adx_strong_threshold: 强趋势ADX阈值
            volatility_threshold: 高波动率阈值
        """
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.volatility_period = volatility_period
        self.adx_trending_threshold = adx_trending_threshold
        self.adx_strong_threshold = adx_strong_threshold
        self.volatility_threshold = volatility_threshold
    
    def calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算ADX（Average Directional Index）指标
        
        ADX用于衡量趋势强度：
        - ADX < 20: 无趋势或弱趋势
        - 20 <= ADX < 25: 趋势开始形成
        - 25 <= ADX < 40: 明显趋势
        - ADX >= 40: 强趋势
        
        Args:
            df: OHLCV数据
            
        Returns:
            包含ADX, +DI, -DI的DataFrame
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # 计算+DM和-DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # 计算True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算平滑的+DM, -DM和TR
        atr = tr.rolling(window=self.adx_period).mean()
        plus_di = 100 * (plus_dm.rolling(window=self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=self.adx_period).mean() / atr)
        
        # 计算DX和ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.adx_period).mean()
        
        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        return df
    
    def calculate_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算价格波动率
        
        使用对数收益率的标准差衡量波动率
        
        Args:
            df: OHLCV数据
            
        Returns:
            包含波动率的DataFrame
        """
        log_returns = np.log(df['close'] / df['close'].shift(1))
        volatility = log_returns.rolling(window=self.volatility_period).std()
        df['volatility'] = volatility
        
        return df
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算ATR（Average True Range）
        
        Args:
            df: OHLCV数据
            
        Returns:
            包含ATR的DataFrame
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=self.atr_period).mean()
        df['atr'] = atr
        df['atr_percent'] = (atr / close) * 100  # ATR占价格的百分比
        
        return df
    
    def detect_ranging_market(self, df: pd.DataFrame, lookback: int = 50) -> float:
        """
        检测震荡市特征
        
        震荡市特征：
        1. 价格在一定区间内波动
        2. 高点和低点比较稳定
        3. 没有明显的趋势方向
        
        Args:
            df: OHLCV数据
            lookback: 回看周期
            
        Returns:
            震荡强度 (0-1)
        """
        if len(df) < lookback:
            return 0.0
        
        recent_data = df.tail(lookback)
        
        # 计算价格在区间内的百分比
        price_high = recent_data['high'].max()
        price_low = recent_data['low'].min()
        price_range = price_high - price_low
        
        if price_range == 0:
            return 0.0
        
        # 计算价格触及上下轨的次数
        upper_touches = (recent_data['high'] >= price_high * 0.98).sum()
        lower_touches = (recent_data['low'] <= price_low * 1.02).sum()
        
        # 震荡特征：频繁触及上下轨
        touch_ratio = (upper_touches + lower_touches) / lookback
        
        # 计算价格在区间中部停留的时间
        mid_price = (price_high + price_low) / 2
        mid_range = price_range * 0.3
        in_middle = ((recent_data['close'] >= mid_price - mid_range) & 
                     (recent_data['close'] <= mid_price + mid_range)).sum()
        middle_ratio = in_middle / lookback
        
        # 综合评分
        range_score = (touch_ratio * 0.6 + middle_ratio * 0.4)
        
        return min(range_score, 1.0)
    
    def detect_trend_direction(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[str, float]:
        """
        检测趋势方向
        
        Args:
            df: OHLCV数据（必须包含plus_di和minus_di）
            lookback: 回看周期
            
        Returns:
            (趋势方向, 趋势强度)
        """
        if len(df) < lookback:
            return 'sideways', 0.0
        
        recent_data = df.tail(lookback)
        
        # 使用DI指标判断方向
        avg_plus_di = recent_data['plus_di'].mean()
        avg_minus_di = recent_data['minus_di'].mean()
        
        # 价格变化
        price_change = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
        
        # 综合判断
        if avg_plus_di > avg_minus_di and price_change > 0.01:
            direction = 'up'
            strength = min((avg_plus_di - avg_minus_di) / 50, 1.0)
        elif avg_minus_di > avg_plus_di and price_change < -0.01:
            direction = 'down'
            strength = min((avg_minus_di - avg_plus_di) / 50, 1.0)
        else:
            direction = 'sideways'
            strength = 0.0
        
        return direction, strength
    
    def detect_regime(self, df: pd.DataFrame) -> MarketRegime:
        """
        综合检测市场状态
        
        Args:
            df: OHLCV数据
            
        Returns:
            MarketRegime对象
        """
        # 计算所有指标
        df = self.calculate_adx(df)
        df = self.calculate_volatility(df)
        df = self.calculate_atr(df)
        
        # 获取最新值
        current_adx = df['adx'].iloc[-1]
        current_volatility = df['volatility'].iloc[-1]
        current_atr_percent = df['atr_percent'].iloc[-1]
        
        # 检测震荡市特征
        range_strength = self.detect_ranging_market(df)
        
        # 检测趋势方向
        trend_direction, trend_strength = self.detect_trend_direction(df)
        
        # 判断市场状态
        regime, confidence = self._classify_regime(
            current_adx,
            current_volatility,
            current_atr_percent,
            range_strength,
            trend_strength
        )
        
        # 推荐策略
        recommended_strategies = self._recommend_strategies(regime, trend_direction)
        
        return MarketRegime(
            regime=regime,
            trend_direction=trend_direction,
            confidence=confidence,
            adx_value=current_adx,
            volatility=current_volatility,
            trend_strength=trend_strength,
            range_strength=range_strength,
            recommended_strategies=recommended_strategies
        )
    
    def _classify_regime(
        self,
        adx: float,
        volatility: float,
        atr_percent: float,
        range_strength: float,
        trend_strength: float
    ) -> Tuple[str, float]:
        """
        分类市场状态
        
        分类逻辑：
        1. 超高ADX（>50）= 强趋势（忽略range_strength，优先级最高）
        2. 高波动 + 任何ADX = volatile（高波动市）
        3. 高ADX + 低震荡强度 = trending（趋势市）
        4. 低ADX + 高震荡强度 = ranging（震荡市）
        5. 其他 = neutral（中性市）
        
        Returns:
            (市场状态, 置信度)
        """
        # 超强趋势（ADX>50，优先级最高）
        if adx >= 50:
            confidence = min(adx / 70, 1.0)
            return 'trending', confidence
        
        # 高波动市
        if volatility > self.volatility_threshold or atr_percent > 3.0:
            confidence = min(volatility / self.volatility_threshold, 1.0)
            return 'volatile', confidence
        
        # 强趋势市
        if adx >= self.adx_strong_threshold and range_strength < 0.5:
            confidence = min(adx / 50, 1.0) * 0.9
            return 'trending', confidence
        
        # 明显趋势市
        if adx >= self.adx_trending_threshold and range_strength < 0.6:
            confidence = min(adx / 40, 1.0) * 0.8
            return 'trending', confidence
        
        # 震荡市
        if adx < self.adx_trending_threshold and range_strength > 0.6:
            confidence = range_strength
            return 'ranging', confidence
        
        # 中性市（不明确）
        confidence = 0.5
        return 'neutral', confidence
    
    def _recommend_strategies(self, regime: str, trend_direction: str) -> list:
        """
        根据市场状态推荐策略
        
        推荐逻辑：
        - trending + up: Trend Following (LONG), Breakout (LONG), Momentum (LONG)
        - trending + down: Trend Following (SHORT), Momentum (SHORT)
        - ranging: Grid Trading, Mean Reversion
        - volatile: 谨慎交易或使用保守策略
        - neutral: 根据次要信号选择
        """
        if regime == 'trending':
            if trend_direction == 'up':
                return ['trend_following', 'breakout', 'momentum']
            elif trend_direction == 'down':
                return ['trend_following', 'momentum']
            else:
                return ['trend_following']
        
        elif regime == 'ranging':
            return ['grid', 'mean_reversion']
        
        elif regime == 'volatile':
            return ['trend_following']  # 高波动时只用趋势跟随，减少震荡
        
        else:  # neutral
            return ['trend_following', 'grid']  # 保守选择
    
    def print_regime_report(self, regime: MarketRegime):
        """
        打印市场状态报告
        
        Args:
            regime: MarketRegime对象
        """
        print("\n" + "="*70)
        print("MARKET REGIME ANALYSIS")
        print("="*70)
        
        print(f"\n[Market State]")
        print(f"   Regime: {regime.regime.upper()}")
        print(f"   Trend Direction: {regime.trend_direction.upper()}")
        print(f"   Confidence: {regime.confidence:.2%}")
        
        print(f"\n[Technical Indicators]")
        print(f"   ADX: {regime.adx_value:.2f}")
        print(f"   Volatility: {regime.volatility:.4f}")
        print(f"   Trend Strength: {regime.trend_strength:.2f}")
        print(f"   Range Strength: {regime.range_strength:.2f}")
        
        print(f"\n[Strategy Recommendations]")
        for i, strategy in enumerate(regime.recommended_strategies, 1):
            print(f"   {i}. {strategy}")
        
        print("\n" + "="*70)


def test_detector():
    """测试市场状态识别器"""
    import sys
    sys.path.append('c:/Users/cair1/Desktop/HT/Headache_trade')
    from trading_bots.data_manager import DataManager
    
    # 获取数据
    data_mgr = DataManager()
    df = data_mgr.fetch_data('binance', 'BTC/USDT', '1h', days=30)
    
    # 创建检测器
    detector = MarketRegimeDetector()
    
    # 检测市场状态
    regime = detector.detect_regime(df)
    
    # 打印报告
    detector.print_regime_report(regime)
    
    return regime


if __name__ == '__main__':
    regime = test_detector()
