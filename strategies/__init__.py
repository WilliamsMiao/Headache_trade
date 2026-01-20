"""
策略包初始化
导出所有策略类和工具
"""

from .base_strategy import BaseStrategy
from .strategy_registry import StrategyRegistry
from .strategy_adapter import (
    create_backtest_strategy,
    create_backtest_strategy_from_class,
    create_backtest_strategy_from_name
)
from .market_analyzer import MarketAnalyzer
from .adaptive_optimizer import AdaptiveOptimizer

__all__ = [
    'BaseStrategy',
    'StrategyRegistry',
    'create_backtest_strategy',
    'create_backtest_strategy_from_class',
    'create_backtest_strategy_from_name',
    'MarketAnalyzer',
    'AdaptiveOptimizer'
]

# 延迟导入策略类和优化器，避免循环依赖
def get_all_strategies():
    """获取所有策略类"""
    return StrategyRegistry.STRATEGIES

def get_optimizer(ai_client=None):
    """获取策略优化器"""
    from .optimizer import StrategyOptimizer
    return StrategyOptimizer(ai_client=ai_client)
