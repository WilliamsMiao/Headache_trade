"""
交易策略基类
定义统一的策略接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

# 导入核心指标计算函数
from ..core.indicators import (
    calculate_rsi,
    calculate_atr,
    calculate_adx,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_sma,
    calculate_volume_ratio
)


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"
    LONG = "long"   # 做多信号
    SHORT = "short"  # 做空信号


@dataclass
class TradingSignal:
    """交易信号"""
    signal_type: SignalType
    confidence: float  # 0-100
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: float = 0.0
    metadata: Dict = None  # 额外信息
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.is_active = False
        self.performance = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
        }
    
    @abstractmethod
    def generate_signal(self, price_data: pd.DataFrame, 
                       current_position: Optional[Dict] = None) -> TradingSignal:
        """
        生成交易信号
        
        Args:
            price_data: OHLCV数据
            current_position: 当前持仓信息
        
        Returns:
            TradingSignal: 交易信号
        """
        pass
    
    @abstractmethod
    def should_exit(self, price_data: pd.DataFrame, 
                   entry_price: float, position_side: str) -> bool:
        """
        判断是否应该退出
        
        Args:
            price_data: OHLCV数据
            entry_price: 入场价格
            position_side: 'long' or 'short'
        
        Returns:
            bool: 是否退出
        """
        pass
    
    @abstractmethod
    def calculate_position_size(self, account_balance: float, 
                               signal: TradingSignal) -> float:
        """
        计算仓位大小
        
        Args:
            account_balance: 账户余额
            signal: 交易信号
        
        Returns:
            float: 仓位大小
        """
        pass
    
    def activate(self):
        """激活策略"""
        self.is_active = True
        print(f"✅ 策略已激活: {self.name}")
    
    def deactivate(self):
        """停用策略"""
        self.is_active = False
        print(f"⏸️ 策略已停用: {self.name}")
    
    def update_performance(self, trade_result: Dict):
        """
        更新策略表现
        
        Args:
            trade_result: 交易结果 {'pnl': float, 'is_win': bool}
        """
        self.performance['total_trades'] += 1
        if trade_result['is_win']:
            self.performance['winning_trades'] += 1
        self.performance['total_pnl'] += trade_result['pnl']
    
    def get_win_rate(self) -> float:
        """获取胜率"""
        if self.performance['total_trades'] == 0:
            return 0.0
        return (self.performance['winning_trades'] / 
                self.performance['total_trades']) * 100
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        return {
            'name': self.name,
            'total_trades': self.performance['total_trades'],
            'win_rate': self.get_win_rate(),
            'total_pnl': self.performance['total_pnl'],
            'max_drawdown': self.performance['max_drawdown'],
            'is_active': self.is_active
        }
    
    # ============================================================================
    # 公共指标计算方法
    # ============================================================================
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI相对强弱指标"""
        return calculate_rsi(close, period)
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, 
                      close: pd.Series, period: int = 14) -> pd.Series:
        """计算ATR平均真实波动范围"""
        return calculate_atr(high, low, close, period)
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, 
                      close: pd.Series, period: int = 14) -> pd.Series:
        """计算ADX平均趋向指数"""
        return calculate_adx(high, low, close, period)
    
    def _calculate_macd(self, close: pd.Series, fast: int = 12, 
                       slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算MACD指标，返回(MACD线, 信号线, 柱状图)"""
        return calculate_macd(close, fast, slow, signal)
    
    def _calculate_bollinger_bands(self, close: pd.Series, period: int = 20, 
                                   std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算布林带，返回(上轨, 中轨, 下轨)"""
        return calculate_bollinger_bands(close, period, std_dev)
    
    def _calculate_ema(self, close: pd.Series, period: int) -> pd.Series:
        """计算EMA指数移动平均"""
        return calculate_ema(close, period)
    
    def _calculate_sma(self, close: pd.Series, period: int) -> pd.Series:
        """计算SMA简单移动平均"""
        return calculate_sma(close, period)
    
    def _calculate_volume_ratio(self, volume: pd.Series, period: int = 20) -> pd.Series:
        """计算成交量比率"""
        return calculate_volume_ratio(volume, period)
    
    def _get_last_n_closes(self, price_data: pd.DataFrame, n: int) -> pd.Series:
        """获取最近N根K线的收盘价"""
        return price_data['close'].tail(n)
    
    def _is_bullish_candle(self, row: pd.Series) -> bool:
        """判断是否为阳线"""
        return row['close'] > row['open']
    
    def _is_bearish_candle(self, row: pd.Series) -> bool:
        """判断是否为阴线"""
        return row['close'] < row['open']
    
    def _get_candle_body_size(self, row: pd.Series) -> float:
        """获取K线实体大小"""
        return abs(row['close'] - row['open'])
    
    def _get_upper_shadow(self, row: pd.Series) -> float:
        """获取上影线长度"""
        return row['high'] - max(row['open'], row['close'])
    
    def _get_lower_shadow(self, row: pd.Series) -> float:
        """获取下影线长度"""
        return min(row['open'], row['close']) - row['low']
    
    def __str__(self) -> str:
        return f"{self.name} - {self.description}"
