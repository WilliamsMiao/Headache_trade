"""
趋势策略
识别趋势方向，跟随趋势交易，适合趋势明显的市场
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from .base_strategy import BaseStrategy


class TrendStrategy(BaseStrategy):
    """趋势策略 - 跟随趋势交易"""
    
    PARAMETERS = {
        'trend_periods': {
            'type': list,
            'default': [20, 50, 200],
            'description': '趋势判断周期列表（SMA周期）',
            'optimizable': False  # 列表类型暂不支持优化
        },
        'trend_strength_threshold': {
            'type': float,
            'default': 60.0,
            'min': 0.0,
            'max': 100.0,
            'description': '趋势强度阈值（0-100）',
            'optimizable': True
        },
        'entry_signal_type': {
            'type': str,
            'default': 'crossover',
            'description': '入场信号类型: crossover/breakout/pullback',
            'optimizable': False
        },
        'rsi_oversold': {
            'type': float,
            'default': 30.0,
            'min': 0.0,
            'max': 50.0,
            'description': 'RSI超卖阈值',
            'optimizable': True
        },
        'rsi_overbought': {
            'type': float,
            'default': 70.0,
            'min': 50.0,
            'max': 100.0,
            'description': 'RSI超买阈值',
            'optimizable': True
        },
        'atr_stop_loss_multiplier': {
            'type': float,
            'default': 2.0,
            'min': 0.5,
            'max': 5.0,
            'description': 'ATR止损倍数',
            'optimizable': True
        },
        'atr_take_profit_multiplier': {
            'type': float,
            'default': 3.0,
            'min': 0.5,
            'max': 10.0,
            'description': 'ATR止盈倍数',
            'optimizable': True
        },
        'min_volume_ratio': {
            'type': float,
            'default': 1.2,
            'min': 0.5,
            'max': 5.0,
            'description': '最小成交量比率',
            'optimizable': True
        },
        'trend_confirmation_bars': {
            'type': int,
            'default': 3,
            'min': 1,
            'max': 10,
            'description': '趋势确认K线数',
            'optimizable': True
        },
        'default_leverage': {
            'type': int,
            'default': 6,
            'min': 1,
            'max': 20,
            'description': '默认杠杆倍数',
            'optimizable': True
        },
        'default_size': {
            'type': float,
            'default': 0.06,
            'min': 0.01,
            'max': 1.0,
            'description': '默认仓位大小（合约张数）',
            'optimizable': True
        }
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._indicator_cache = {}
    
    def _calculate_indicators(self, df: pd.DataFrame, index: int) -> Optional[Dict]:
        """计算技术指标"""
        if index < 200:
            return None
        
        cache_key = index
        if cache_key in self._indicator_cache:
            return self._indicator_cache[cache_key]
        
        window_df = df.iloc[max(0, index-200):index+1].copy()
        current_price = window_df['close'].iloc[-1]
        
        # 计算多周期移动平均线
        trend_periods = self.get_parameter('trend_periods')
        sma_values = {}
        for period in trend_periods:
            sma_values[f'sma_{period}'] = window_df['close'].rolling(period).mean().iloc[-1]
        
        # ATR
        window_df['tr'] = window_df[['high', 'low', 'close']].apply(
            lambda x: max(x['high'] - x['low'],
                         abs(x['high'] - x['close']),
                         abs(x['low'] - x['close'])),
            axis=1
        )
        atr = window_df['tr'].rolling(14).mean().iloc[-1]
        
        # RSI
        delta = window_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        # MACD
        ema12 = window_df['close'].ewm(span=12).mean()
        ema26 = window_df['close'].ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        macd_signal = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
        macd_hist = macd - macd_signal
        
        # 成交量
        volume = window_df['volume'].iloc[-1]
        volume_sma = window_df['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1.0
        
        # 趋势确认：检查最近N根K线的趋势一致性
        confirmation_bars = self.get_parameter('trend_confirmation_bars')
        recent_closes = window_df['close'].tail(confirmation_bars + 1).values
        recent_sma = sma_values[f'sma_{trend_periods[0]}']
        
        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(
            current_price, sma_values, trend_periods, recent_closes
        )
        
        indicators = {
            'close': current_price,
            'atr': atr,
            'rsi': rsi,
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'volume_ratio': volume_ratio,
            'sma_values': sma_values,
            'trend_strength': trend_strength,
            'recent_closes': recent_closes,
            'window_df': window_df
        }
        
        self._indicator_cache[cache_key] = indicators
        return indicators
    
    def _calculate_trend_strength(
        self,
        current_price: float,
        sma_values: Dict[str, float],
        trend_periods: list,
        recent_closes: np.ndarray
    ) -> Dict[str, Any]:
        """计算趋势强度和方向"""
        # 检查价格与各周期均线的关系
        above_sma_count = 0
        below_sma_count = 0
        
        for period in trend_periods:
            sma_key = f'sma_{period}'
            if sma_key in sma_values:
                if current_price > sma_values[sma_key]:
                    above_sma_count += 1
                else:
                    below_sma_count += 1
        
        # 检查均线排列（多头排列：短周期 > 长周期）
        sma_list = [sma_values.get(f'sma_{p}', 0) for p in trend_periods]
        is_bullish_alignment = all(
            sma_list[i] > sma_list[i+1] for i in range(len(sma_list)-1)
        )
        is_bearish_alignment = all(
            sma_list[i] < sma_list[i+1] for i in range(len(sma_list)-1)
        )
        
        # 检查价格趋势（最近N根K线是否一致）
        price_trend_up = len(recent_closes) > 1 and recent_closes[-1] > recent_closes[0]
        price_trend_down = len(recent_closes) > 1 and recent_closes[-1] < recent_closes[0]
        
        # 计算趋势强度分数（0-100）
        strength_score = 0
        if above_sma_count == len(trend_periods) and is_bullish_alignment and price_trend_up:
            strength_score = 80 + (above_sma_count * 5)
            direction = 'up'
        elif below_sma_count == len(trend_periods) and is_bearish_alignment and price_trend_down:
            strength_score = 80 + (below_sma_count * 5)
            direction = 'down'
        elif above_sma_count > below_sma_count:
            strength_score = 50 + (above_sma_count * 10)
            direction = 'up'
        elif below_sma_count > above_sma_count:
            strength_score = 50 + (below_sma_count * 10)
            direction = 'down'
        else:
            strength_score = 30
            direction = 'neutral'
        
        return {
            'score': min(100, strength_score),
            'direction': direction,
            'above_sma_count': above_sma_count,
            'below_sma_count': below_sma_count,
            'is_bullish_alignment': is_bullish_alignment,
            'is_bearish_alignment': is_bearish_alignment
        }
    
    def _check_entry_signal(
        self,
        indicators: Dict,
        entry_type: str
    ) -> tuple:
        """
        检查入场信号
        
        Returns:
            (should_enter, direction, reason)
        """
        trend_strength = indicators['trend_strength']
        rsi = indicators['rsi']
        macd_hist = indicators['macd_hist']
        volume_ratio = indicators['volume_ratio']
        current_price = indicators['close']
        sma_values = indicators['sma_values']
        trend_periods = self.get_parameter('trend_periods')
        
        # 趋势强度过滤
        if trend_strength['score'] < self.get_parameter('trend_strength_threshold'):
            return False, None, '趋势强度不足'
        
        # 成交量过滤
        if volume_ratio < self.get_parameter('min_volume_ratio'):
            return False, None, '成交量不足'
        
        direction = trend_strength['direction']
        
        if entry_type == 'crossover':
            # 均线交叉信号
            if direction == 'up':
                # 做多：价格上穿短期均线，且RSI未超买
                short_sma = sma_values.get(f'sma_{trend_periods[0]}', current_price)
                if current_price > short_sma and rsi < self.get_parameter('rsi_overbought'):
                    if macd_hist > 0:  # MACD确认
                        return True, 'up', '均线交叉做多'
            
            elif direction == 'down':
                # 做空：价格下穿短期均线，且RSI未超卖
                short_sma = sma_values.get(f'sma_{trend_periods[0]}', current_price)
                if current_price < short_sma and rsi > self.get_parameter('rsi_oversold'):
                    if macd_hist < 0:  # MACD确认
                        return True, 'down', '均线交叉做空'
        
        elif entry_type == 'pullback':
            # 回调入场
            if direction == 'up':
                # 做多：上涨趋势中的回调
                if (rsi < self.get_parameter('rsi_overbought') and
                    rsi > self.get_parameter('rsi_oversold')):
                    return True, 'up', '趋势回调做多'
            
            elif direction == 'down':
                # 做空：下跌趋势中的反弹
                if (rsi > self.get_parameter('rsi_oversold') and
                    rsi < self.get_parameter('rsi_overbought')):
                    return True, 'down', '趋势反弹做空'
        
        elif entry_type == 'breakout':
            # 突破入场
            if direction == 'up':
                # 做多：突破阻力位
                long_sma = sma_values.get(f'sma_{trend_periods[-1]}', current_price)
                if current_price > long_sma and macd_hist > 0:
                    return True, 'up', '突破阻力做多'
            
            elif direction == 'down':
                # 做空：跌破支撑位
                long_sma = sma_values.get(f'sma_{trend_periods[-1]}', current_price)
                if current_price < long_sma and macd_hist < 0:
                    return True, 'down', '跌破支撑做空'
        
        return False, None, '无入场信号'
    
    def generate_signal(
        self,
        index: int,
        df: pd.DataFrame,
        position: Optional[Any],
        current_balance: float,
        performance_stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """生成交易信号"""
        if position is not None:
            return None
        
        indicators = self._calculate_indicators(df, index)
        if indicators is None:
            return None
        
        entry_type = self.get_parameter('entry_signal_type')
        should_enter, direction, reason = self._check_entry_signal(indicators, entry_type)
        
        if not should_enter:
            return None
        
        current_price = indicators['close']
        atr = indicators['atr']
        trend_strength = indicators['trend_strength']
        
        if direction == 'up':
            # 做多
            stop_loss = current_price - (atr * self.get_parameter('atr_stop_loss_multiplier'))
            take_profit = current_price + (atr * self.get_parameter('atr_take_profit_multiplier'))
            
            return {
                'action': 'BUY',
                'size': self.get_parameter('default_size'),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': self.get_parameter('default_leverage'),
                'reason': f'趋势策略做多: {reason}, 强度={trend_strength["score"]:.1f}',
                'metadata': {
                    'trend_strength': trend_strength['score'],
                    'trend_direction': direction,
                    'rsi': indicators['rsi'],
                    'macd_hist': indicators['macd_hist']
                }
            }
        
        elif direction == 'down':
            # 做空
            stop_loss = current_price + (atr * self.get_parameter('atr_stop_loss_multiplier'))
            take_profit = current_price - (atr * self.get_parameter('atr_take_profit_multiplier'))
            
            return {
                'action': 'SELL',
                'size': self.get_parameter('default_size'),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': self.get_parameter('default_leverage'),
                'reason': f'趋势策略做空: {reason}, 强度={trend_strength["score"]:.1f}',
                'metadata': {
                    'trend_strength': trend_strength['score'],
                    'trend_direction': direction,
                    'rsi': indicators['rsi'],
                    'macd_hist': indicators['macd_hist']
                }
            }
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        return "趋势策略 - 识别趋势方向，跟随趋势交易"
