"""
策略适配器
将策略实例转换为回测引擎需要的函数
"""

from typing import Callable, Optional, Any
import pandas as pd
from .base_strategy import BaseStrategy


def create_backtest_strategy(strategy_instance: BaseStrategy) -> Callable:
    """
    将策略实例转换为回测函数
    
    Args:
        strategy_instance: 策略实例
        
    Returns:
        回测函数，符合 BacktestEngine.run() 的接口要求
    """
    # 重置策略状态
    strategy_instance.reset_state()
    
    def strategy_func(index: int, df: pd.DataFrame, position: Optional[Any],
                     current_balance: float, performance_stats: dict) -> Optional[dict]:
        """
        回测策略函数
        
        Args:
            index: 当前K线索引
            df: 完整的历史数据
            position: 当前持仓（Position对象或None）
            current_balance: 当前账户余额
            performance_stats: 性能统计字典
            
        Returns:
            交易信号字典或None
        """
        try:
            signal = strategy_instance.generate_signal(
                index=index,
                df=df,
                position=position,
                current_balance=current_balance,
                performance_stats=performance_stats
            )
            
            # 处理CLOSE信号（回测引擎期望CLOSE作为action）
            if signal and signal.get('action') == 'CLOSE':
                # 如果position存在，使用position.size
                if position is not None:
                    signal['action'] = 'CLOSE'
                    # 确保size不超过持仓
                    if 'size' not in signal or signal['size'] > position.size:
                        signal['size'] = position.size
                else:
                    # 无持仓但收到CLOSE信号，忽略
                    return None
            
            return signal
            
        except Exception as e:
            # 记录错误但不中断回测
            print(f"策略执行错误 (index={index}): {str(e)}")
            return None
    
    # 附加策略信息到函数（用于日志等）
    strategy_func.strategy_name = strategy_instance.get_name()
    strategy_func.strategy_instance = strategy_instance
    
    return strategy_func


def create_backtest_strategy_from_class(
    strategy_class: type,
    strategy_params: dict = None
) -> Callable:
    """
    从策略类创建回测函数
    
    Args:
        strategy_class: 策略类
        strategy_params: 策略参数字典
        
    Returns:
        回测函数
    """
    if strategy_params is None:
        strategy_params = {}
    
    strategy_instance = strategy_class(**strategy_params)
    return create_backtest_strategy(strategy_instance)


def create_backtest_strategy_from_name(
    strategy_name: str,
    strategy_params: dict = None
) -> Callable:
    """
    从策略名称创建回测函数
    
    Args:
        strategy_name: 策略名称（如 'grid', 'martingale'）
        strategy_params: 策略参数字典
        
    Returns:
        回测函数
    """
    from .strategy_registry import StrategyRegistry
    
    strategy_class = StrategyRegistry.get_strategy_class(strategy_name)
    return create_backtest_strategy_from_class(strategy_class, strategy_params)
