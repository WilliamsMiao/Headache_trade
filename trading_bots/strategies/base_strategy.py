"""
交易策略基类
定义统一的策略接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import pandas as pd


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
    
    def __str__(self) -> str:
        return f"{self.name} - {self.description}"
