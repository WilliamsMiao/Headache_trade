"""
技术指标计算模块
包含所有技术指标的计算逻辑
"""

import pandas as pd
import numpy as np
from functools import lru_cache
from typing import Dict, Tuple


def calculate_atr(df, period=14):
    """计算平均真实波动范围(ATR)"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    atr = true_range.rolling(period).mean()
    return atr.iloc[-1]


def calculate_volatility(df, period=20):
    """计算价格波动率"""
    returns = df['close'].pct_change()
    volatility = returns.rolling(window=period).std() * np.sqrt(365)
    return volatility.iloc[-1]


@lru_cache(maxsize=32)
def calculate_technical_indicators_cached(symbol: str, timestamp: int, period: int = 20):
    """
    缓存版技术指标计算（用于减少重复计算）
    
    Args:
        symbol: 交易对符号
        timestamp: 时间戳（用于缓存失效）
        period: 计算周期
    
    注意：此函数需要配合外部数据获取使用
    """
    # 此函数由外部调用时传入数据帧
    pass


def calculate_technical_indicators(df):
    """
    计算完整的技术指标套件
    
    Args:
        df: OHLCV数据帧
    
    Returns:
        dict: 包含所有技术指标的字典
    """
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # 移动平均线
    ma5 = close.rolling(window=5).mean()
    ma10 = close.rolling(window=10).mean()
    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()
    ma100 = close.rolling(window=100).mean()
    ma200 = close.rolling(window=200).mean()
    
    # EMA指数移动平均
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    
    # MACD
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_histogram = macd_line - signal_line
    
    # RSI相对强弱指标
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 布林带
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)
    bb_width = (bb_upper - bb_lower) / bb_middle
    
    # ATR平均真实波动范围
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(14).mean()
    
    # 成交量指标
    volume_ma = volume.rolling(window=20).mean()
    volume_ratio = volume / volume_ma
    
    # ADX平均趋向指数
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr = true_range
    atr_14 = tr.rolling(14).mean()
    
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
    
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()
    
    # 动量指标
    momentum = close - close.shift(10)
    
    # 返回最新值
    indicators = {
        'ma5': ma5.iloc[-1],
        'ma10': ma10.iloc[-1],
        'ma20': ma20.iloc[-1],
        'ma50': ma50.iloc[-1],
        'ma100': ma100.iloc[-1],
        'ma200': ma200.iloc[-1],
        'ema12': ema12.iloc[-1],
        'ema26': ema26.iloc[-1],
        'macd': macd_line.iloc[-1],
        'macd_signal': signal_line.iloc[-1],
        'macd_histogram': macd_histogram.iloc[-1],
        'rsi': rsi.iloc[-1],
        'bb_upper': bb_upper.iloc[-1],
        'bb_middle': bb_middle.iloc[-1],
        'bb_lower': bb_lower.iloc[-1],
        'bb_width': bb_width.iloc[-1],
        'atr': atr.iloc[-1],
        'volume_ratio': volume_ratio.iloc[-1],
        'adx': adx.iloc[-1],
        'plus_di': plus_di.iloc[-1],
        'minus_di': minus_di.iloc[-1],
        'momentum': momentum.iloc[-1],
    }
    
    return indicators


def get_market_trend(df) -> Dict[str, any]:
    """
    判断市场趋势
    
    Returns:
        dict: 包含趋势方向、强度等信息
    """
    close = df['close']
    
    # 计算多个时间周期的MA
    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()
    ma100 = close.rolling(window=100).mean()
    ma200 = close.rolling(window=200).mean()
    
    current_price = close.iloc[-1]
    
    # 趋势判断
    if current_price > ma20.iloc[-1] > ma50.iloc[-1] > ma100.iloc[-1]:
        trend = "strong_uptrend"
        strength = 1.0
    elif current_price > ma20.iloc[-1] > ma50.iloc[-1]:
        trend = "uptrend"
        strength = 0.7
    elif current_price < ma20.iloc[-1] < ma50.iloc[-1] < ma100.iloc[-1]:
        trend = "strong_downtrend"
        strength = 1.0
    elif current_price < ma20.iloc[-1] < ma50.iloc[-1]:
        trend = "downtrend"
        strength = 0.7
    else:
        trend = "sideways"
        strength = 0.3
    
    return {
        'trend': trend,
        'strength': strength,
        'ma20': ma20.iloc[-1],
        'ma50': ma50.iloc[-1],
        'ma100': ma100.iloc[-1],
        'ma200': ma200.iloc[-1],
    }


def get_support_resistance_levels(df, lookback=20) -> Dict[str, float]:
    """
    识别支撑位和阻力位
    
    Args:
        df: OHLCV数据帧
        lookback: 回看周期
    
    Returns:
        dict: 支撑位和阻力位信息
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 最近N根K线的高低点
    recent_high = high.tail(lookback).max()
    recent_low = low.tail(lookback).min()
    
    # 布林带作为支撑阻力
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)
    
    return {
        'resistance_1': recent_high,
        'resistance_2': bb_upper.iloc[-1],
        'support_1': recent_low,
        'support_2': bb_lower.iloc[-1],
        'pivot': bb_middle.iloc[-1],
    }


def enhanced_trend_analysis(df) -> Dict[str, any]:
    """
    增强趋势分析
    
    Returns:
        dict: 详细的趋势分析结果
    """
    indicators = calculate_technical_indicators(df)
    trend_info = get_market_trend(df)
    sr_levels = get_support_resistance_levels(df)
    
    close = df['close'].iloc[-1]
    
    # 趋势强度评分
    trend_score = 0
    
    # MA排列
    if indicators['ma5'] > indicators['ma10'] > indicators['ma20']:
        trend_score += 2
    elif indicators['ma5'] < indicators['ma10'] < indicators['ma20']:
        trend_score -= 2
    
    # MACD
    if indicators['macd'] > indicators['macd_signal'] and indicators['macd'] > 0:
        trend_score += 1
    elif indicators['macd'] < indicators['macd_signal'] and indicators['macd'] < 0:
        trend_score -= 1
    
    # RSI
    if indicators['rsi'] > 70:
        trend_score -= 1  # 超买
    elif indicators['rsi'] < 30:
        trend_score += 1  # 超卖
    
    # ADX趋势强度
    if indicators['adx'] > 25:
        if indicators['plus_di'] > indicators['minus_di']:
            trend_score += 1
        else:
            trend_score -= 1
    
    # 综合判断
    if trend_score >= 3:
        primary_trend = "strong_bullish"
    elif trend_score >= 1:
        primary_trend = "bullish"
    elif trend_score <= -3:
        primary_trend = "strong_bearish"
    elif trend_score <= -1:
        primary_trend = "bearish"
    else:
        primary_trend = "neutral"
    
    return {
        'primary_trend': primary_trend,
        'trend_score': trend_score,
        'indicators': indicators,
        'support_resistance': sr_levels,
        'market_trend': trend_info,
    }


def structure_timing_signals(df, primary_trend: str) -> Dict[str, any]:
    """
    结构化时机信号
    
    Args:
        df: OHLCV数据帧
        primary_trend: 主要趋势
    
    Returns:
        dict: 入场时机信号
    """
    indicators = calculate_technical_indicators(df)
    
    # 入场信号强度
    entry_signal = 0
    
    # MACD金叉/死叉
    macd_cross = "none"
    if indicators['macd'] > indicators['macd_signal']:
        if indicators['macd_histogram'] > 0:
            macd_cross = "golden_cross"
            entry_signal += 2
    elif indicators['macd'] < indicators['macd_signal']:
        if indicators['macd_histogram'] < 0:
            macd_cross = "death_cross"
            entry_signal -= 2
    
    # RSI信号
    rsi_signal = "neutral"
    if indicators['rsi'] < 30:
        rsi_signal = "oversold"
        entry_signal += 1
    elif indicators['rsi'] > 70:
        rsi_signal = "overbought"
        entry_signal -= 1
    
    # 布林带突破
    close = df['close'].iloc[-1]
    bb_signal = "neutral"
    if close < indicators['bb_lower']:
        bb_signal = "lower_breakout"
        entry_signal += 1
    elif close > indicators['bb_upper']:
        bb_signal = "upper_breakout"
        entry_signal -= 1
    
    # 成交量确认
    volume_signal = "normal"
    if indicators['volume_ratio'] > 1.5:
        volume_signal = "high"
        entry_signal += 1
    elif indicators['volume_ratio'] < 0.5:
        volume_signal = "low"
        entry_signal -= 1
    
    return {
        'entry_signal': entry_signal,
        'macd_cross': macd_cross,
        'rsi_signal': rsi_signal,
        'bb_signal': bb_signal,
        'volume_signal': volume_signal,
    }


def generate_trend_king_signal(price_data) -> Dict[str, any]:
    """
    生成趋势之王信号（整合版）
    
    Args:
        price_data: 价格数据帧
    
    Returns:
        dict: 完整的交易信号
    """
    df = price_data
    
    # 增强趋势分析
    trend_analysis = enhanced_trend_analysis(df)
    primary_trend = trend_analysis['primary_trend']
    
    # 时机信号
    timing_signals = structure_timing_signals(df, primary_trend)
    
    # 综合信号
    signal = "hold"
    confidence = 50
    
    if primary_trend in ["strong_bullish", "bullish"] and timing_signals['entry_signal'] > 0:
        signal = "buy"
        confidence = min(95, 50 + abs(trend_analysis['trend_score']) * 5 + timing_signals['entry_signal'] * 5)
    elif primary_trend in ["strong_bearish", "bearish"] and timing_signals['entry_signal'] < 0:
        signal = "sell"
        confidence = min(95, 50 + abs(trend_analysis['trend_score']) * 5 + abs(timing_signals['entry_signal']) * 5)
    
    return {
        'signal': signal,
        'confidence': confidence,
        'trend': primary_trend,
        'trend_score': trend_analysis['trend_score'],
        'timing': timing_signals,
        'indicators': trend_analysis['indicators'],
        'support_resistance': trend_analysis['support_resistance'],
    }
