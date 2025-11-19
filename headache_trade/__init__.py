"""
Headache Trade - 加密货币自动交易系统

多策略AI驱动的加密货币交易系统，支持回测和实盘交易。
"""

__version__ = "2.0.0"
__author__ = "Headache Trade Team"

# 导出核心组件
from headache_trade.core.data_manager import DataManager
from headache_trade.backtest.system import BacktestSystem

__all__ = [
    "DataManager",
    "BacktestSystem",
]
