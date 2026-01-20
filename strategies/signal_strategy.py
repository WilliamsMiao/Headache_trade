"""
信号策略
基于技术指标组合产生交易信号，参数化的趋势策略
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from .base_strategy import BaseStrategy


class SignalStrategy(BaseStrategy):
    """信号策略 - 基于技术指标组合"""
    
    PARAMETERS = {
        'rsi_long_min': {
            'type': float,
            'default': 45.0,
            'min': 0.0,
            'max': 100.0,
            'description': '做多信号的RSI下限',
            'optimizable': True
        },
        'rsi_long_max': {
            'type': float,
            'default': 75.0,
            'min': 0.0,
            'max': 100.0,
            'description': '做多信号的RSI上限',
            'optimizable': True
        },
        'rsi_short_min': {
            'type': float,
            'default': 25.0,
            'min': 0.0,
            'max': 100.0,
            'description': '做空信号的RSI下限',
            'optimizable': True
        },
        'rsi_short_max': {
            'type': float,
            'default': 55.0,
            'min': 0.0,
            'max': 100.0,
            'description': '做空信号的RSI上限',
            'optimizable': True
        },
        'macd_signal_threshold': {
            'type': float,
            'default': 0.0,
            'min': -1.0,
            'max': 1.0,
            'description': 'MACD信号阈值',
            'optimizable': True
        },
        'bb_position_min': {
            'type': float,
            'default': 0.3,
            'min': 0.0,
            'max': 1.0,
            'description': '布林带位置下限',
            'optimizable': True
        },
        'bb_position_max': {
            'type': float,
            'default': 0.7,
            'min': 0.0,
            'max': 1.0,
            'description': '布林带位置上限',
            'optimizable': True
        },
        'volume_ratio_min': {
            'type': float,
            'default': 1.2,
            'min': 0.5,
            'max': 5.0,
            'description': '成交量比率下限',
            'optimizable': True
        },
        'atr_pct_min': {
            'type': float,
            'default': 0.005,
            'min': 0.0,
            'max': 0.1,
            'description': 'ATR百分比下限（避免极低波动）',
            'optimizable': True
        },
        'atr_pct_max': {
            'type': float,
            'default': 0.030,
            'min': 0.0,
            'max': 0.1,
            'description': 'ATR百分比上限（避免剧烈波动）',
            'optimizable': True
        },
        'stop_loss_atr_multiplier': {
            'type': float,
            'default': 1.8,
            'min': 0.5,
            'max': 5.0,
            'description': '止损ATR倍数',
            'optimizable': True
        },
        'take_profit_atr_multiplier': {
            'type': float,
            'default': 2.2,
            'min': 0.5,
            'max': 10.0,
            'description': '止盈ATR倍数',
            'optimizable': True
        },
        'require_trend_alignment': {
            'type': bool,
            'default': True,
            'description': '是否需要多周期趋势对齐',
            'optimizable': False
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
        self._indicator_cache = {}  # 缓存指标计算结果
    
    def _calculate_indicators(self, df: pd.DataFrame, index: int) -> Optional[Dict]:
        """计算技术指标"""
        # 确保有足够的数据
        if index < 200:
            return None
        
        # 检查缓存
        cache_key = index
        if cache_key in self._indicator_cache:
            return self._indicator_cache[cache_key]
        
        # 获取当前数据窗口
        window_df = df.iloc[max(0, index-200):index+1].copy()
        
        # 移动平均线
        window_df['sma_20'] = window_df['close'].rolling(20).mean()
        window_df['sma_50'] = window_df['close'].rolling(50).mean()
        window_df['ema_9'] = window_df['close'].ewm(span=9).mean()
        window_df['ema_21'] = window_df['close'].ewm(span=21).mean()
        window_df['ema_50'] = window_df['close'].ewm(span=50).mean()
        
        # ATR
        window_df['tr'] = window_df[['high', 'low', 'close']].apply(
            lambda x: max(x['high'] - x['low'],
                         abs(x['high'] - x['close']),
                         abs(x['low'] - x['close'])),
            axis=1
        )
        window_df['atr'] = window_df['tr'].rolling(14).mean()
        
        # RSI
        delta = window_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        window_df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = window_df['close'].ewm(span=12).mean()
        ema26 = window_df['close'].ewm(span=26).mean()
        window_df['macd'] = ema12 - ema26
        window_df['macd_signal'] = window_df['macd'].ewm(span=9).mean()
        window_df['macd_hist'] = window_df['macd'] - window_df['macd_signal']
        
        # 布林带
        window_df['bb_middle'] = window_df['close'].rolling(20).mean()
        bb_std = window_df['close'].rolling(20).std()
        window_df['bb_upper'] = window_df['bb_middle'] + (bb_std * 2)
        window_df['bb_lower'] = window_df['bb_middle'] - (bb_std * 2)
        window_df['bb_position'] = (window_df['close'] - window_df['bb_lower']) / (
            window_df['bb_upper'] - window_df['bb_lower']
        )
        
        # 成交量均线
        window_df['volume_sma'] = window_df['volume'].rolling(20).mean()
        
        # 获取最新值
        current = window_df.iloc[-1]
        prev = window_df.iloc[-2] if len(window_df) > 1 else current
        
        indicators = {
            'close': current['close'],
            'atr': current['atr'],
            'rsi': current['rsi'],
            'macd': current['macd'],
            'macd_signal': current['macd_signal'],
            'macd_hist': current['macd_hist'],
            'bb_position': current['bb_position'],
            'volume': current['volume'],
            'volume_sma': current.get('volume_sma', current['volume']),
            'sma_20': current['sma_20'],
            'sma_50': current['sma_50'],
            'ema_9': current['ema_9'],
            'ema_21': current['ema_21'],
            'ema_50': current['ema_50'],
            'current': current,
            'prev': prev
        }
        
        # 缓存结果
        self._indicator_cache[cache_key] = indicators
        return indicators
    
    def _check_trend_alignment(self, indicators: Dict) -> tuple:
        """
        检查多周期趋势对齐
        
        Returns:
            (is_aligned, direction) - 是否对齐，方向('up'/'down'/'neutral')
        """
        if not self.get_parameter('require_trend_alignment'):
            return True, 'neutral'
        
        ema_9 = indicators['ema_9']
        ema_21 = indicators['ema_21']
        ema_50 = indicators['ema_50']
        close = indicators['close']
        
        # 检查短期趋势
        short_up = close > ema_9 and ema_9 > ema_21
        short_down = close < ema_9 and ema_9 < ema_21
        
        # 检查中期趋势
        medium_up = close > ema_50
        medium_down = close < ema_50
        
        if short_up and medium_up:
            return True, 'up'
        elif short_down and medium_down:
            return True, 'down'
        else:
            return False, 'neutral'
    
    def generate_signal(
        self,
        index: int,
        df: pd.DataFrame,
        position: Optional[Any],
        current_balance: float,
        performance_stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """生成交易信号"""
        # 如果已有持仓，不产生新信号
        if position is not None:
            return None
        
        # 计算指标
        indicators = self._calculate_indicators(df, index)
        if indicators is None:
            return None
        
        current_price = indicators['close']
        atr = indicators['atr']
        rsi = indicators['rsi']
        macd_hist = indicators['macd_hist']
        bb_position = indicators['bb_position']
        volume = indicators['volume']
        volume_sma = indicators['volume_sma']
        
        # 计算ATR百分比
        atr_pct = atr / current_price if current_price > 0 else 0
        
        # 极端波动过滤
        if atr_pct < self.get_parameter('atr_pct_min') or atr_pct > self.get_parameter('atr_pct_max'):
            return None
        
        # 成交量过滤
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1.0
        if volume_ratio < self.get_parameter('volume_ratio_min'):
            return None
        
        # 布林带位置过滤
        if bb_position < self.get_parameter('bb_position_min') or bb_position > self.get_parameter('bb_position_max'):
            return None
        
        # 检查趋势对齐
        trend_aligned, trend_direction = self._check_trend_alignment(indicators)
        if not trend_aligned:
            return None
        
        # 做多信号检查
        if (trend_direction == 'up' and
            self.get_parameter('rsi_long_min') <= rsi <= self.get_parameter('rsi_long_max') and
            macd_hist > self.get_parameter('macd_signal_threshold')):
            
            stop_loss = current_price - (atr * self.get_parameter('stop_loss_atr_multiplier'))
            take_profit = current_price + (atr * self.get_parameter('take_profit_atr_multiplier'))
            
            return {
                'action': 'BUY',
                'size': self.get_parameter('default_size'),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': self.get_parameter('default_leverage'),
                'reason': f'信号策略做多: RSI={rsi:.1f}, MACD={macd_hist:.4f}, BB={bb_position:.2f}',
                'metadata': {
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'bb_position': bb_position,
                    'atr_pct': atr_pct
                }
            }
        
        # 做空信号检查
        if (trend_direction == 'down' and
            self.get_parameter('rsi_short_min') <= rsi <= self.get_parameter('rsi_short_max') and
            macd_hist < -self.get_parameter('macd_signal_threshold')):
            
            stop_loss = current_price + (atr * self.get_parameter('stop_loss_atr_multiplier'))
            take_profit = current_price - (atr * self.get_parameter('take_profit_atr_multiplier'))
            
            return {
                'action': 'SELL',
                'size': self.get_parameter('default_size'),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': self.get_parameter('default_leverage'),
                'reason': f'信号策略做空: RSI={rsi:.1f}, MACD={macd_hist:.4f}, BB={bb_position:.2f}',
                'metadata': {
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'bb_position': bb_position,
                    'atr_pct': atr_pct
                }
            }
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        return "信号策略 - 基于RSI、MACD、布林带等技术指标组合产生交易信号"
