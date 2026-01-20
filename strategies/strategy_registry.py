"""
策略注册表
管理所有可用策略的注册和加载
"""

from typing import Dict, Type, Optional, List
from .base_strategy import BaseStrategy


class StrategyRegistry:
    """策略注册表"""
    
    # 策略字典，键为策略名称，值为策略类
    STRATEGIES: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]):
        """
        注册策略
        
        Args:
            name: 策略名称（如 'grid', 'martingale'）
            strategy_class: 策略类
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"{strategy_class} 必须继承自 BaseStrategy")
        cls.STRATEGIES[name] = strategy_class
    
    @classmethod
    def get_strategy(cls, name: str, params: Optional[Dict] = None) -> BaseStrategy:
        """
        获取策略实例
        
        Args:
            name: 策略名称
            params: 策略参数字典
            
        Returns:
            策略实例
            
        Raises:
            KeyError: 如果策略不存在
        """
        if name not in cls.STRATEGIES:
            raise KeyError(f"策略 '{name}' 不存在。可用策略: {list(cls.STRATEGIES.keys())}")
        
        strategy_class = cls.STRATEGIES[name]
        if params:
            return strategy_class(**params)
        else:
            return strategy_class()
    
    @classmethod
    def list_strategies(cls) -> List[str]:
        """
        列出所有可用策略名称
        
        Returns:
            策略名称列表
        """
        return list(cls.STRATEGIES.keys())
    
    @classmethod
    def get_strategy_class(cls, name: str) -> Type[BaseStrategy]:
        """
        获取策略类（不实例化）
        
        Args:
            name: 策略名称
            
        Returns:
            策略类
        """
        if name not in cls.STRATEGIES:
            raise KeyError(f"策略 '{name}' 不存在。可用策略: {list(cls.STRATEGIES.keys())}")
        return cls.STRATEGIES[name]
    
    @classmethod
    def get_strategy_info(cls, name: str) -> Dict:
        """
        获取策略信息（包括参数定义）
        
        Args:
            name: 策略名称
            
        Returns:
            策略信息字典
        """
        strategy_class = cls.get_strategy_class(name)
        instance = strategy_class()  # 使用默认参数创建实例
        
        return {
            'name': name,
            'class_name': strategy_class.__name__,
            'description': instance.get_description(),
            'parameters': instance.get_parameter_info()
        }
    
    @classmethod
    def list_all_strategies_info(cls) -> Dict[str, Dict]:
        """
        获取所有策略的详细信息
        
        Returns:
            字典，键为策略名称，值为策略信息
        """
        return {
            name: cls.get_strategy_info(name)
            for name in cls.list_strategies()
        }


# 自动注册策略（延迟导入避免循环依赖）
def _register_all_strategies():
    """注册所有策略"""
    try:
        from .signal_strategy import SignalStrategy
        StrategyRegistry.register('signal', SignalStrategy)
    except ImportError:
        pass
    
    try:
        from .trend_strategy import TrendStrategy
        StrategyRegistry.register('trend', TrendStrategy)
    except ImportError:
        pass
    
    try:
        from .grid_strategy import GridStrategy
        StrategyRegistry.register('grid', GridStrategy)
    except ImportError:
        pass
    
    try:
        from .martingale_strategy import MartingaleStrategy
        StrategyRegistry.register('martingale', MartingaleStrategy)
    except ImportError:
        pass


# 在导入时自动注册
_register_all_strategies()
