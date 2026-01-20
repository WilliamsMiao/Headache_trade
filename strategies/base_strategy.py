"""
基础策略抽象类
定义所有策略的统一接口和参数管理
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import pandas as pd
from datetime import datetime


class BaseStrategy(ABC):
    """策略基类，所有策略必须继承此类"""
    
    # 子类需要定义 PARAMETERS 字典
    PARAMETERS: Dict[str, Dict[str, Any]] = {}
    
    def __init__(self, **kwargs):
        """
        初始化策略
        
        Args:
            **kwargs: 策略参数，会覆盖默认值
        """
        self.params = {}
        self.state = {}  # 策略状态（用于网格、马丁格尔等需要状态的策略）
        
        # 加载默认参数
        self._load_default_parameters()
        
        # 应用传入的参数
        if kwargs:
            self.set_parameters(kwargs)
        
        # 验证参数
        self.validate_parameters()
    
    def _load_default_parameters(self):
        """加载默认参数"""
        for param_name, param_def in self.PARAMETERS.items():
            self.params[param_name] = param_def.get('default')
    
    def validate_parameters(self):
        """验证参数的有效性"""
        for param_name, param_value in self.params.items():
            if param_name not in self.PARAMETERS:
                raise ValueError(f"未知参数: {param_name}")
            
            param_def = self.PARAMETERS[param_name]
            
            # 类型检查
            expected_type = param_def.get('type')
            if expected_type and not isinstance(param_value, expected_type):
                try:
                    # 尝试类型转换
                    self.params[param_name] = expected_type(param_value)
                except (ValueError, TypeError):
                    raise TypeError(
                        f"参数 {param_name} 类型错误: 期望 {expected_type.__name__}, "
                        f"得到 {type(param_value).__name__}"
                    )
            
            # 范围检查
            if 'min' in param_def:
                if param_value < param_def['min']:
                    raise ValueError(
                        f"参数 {param_name} 值 {param_value} 小于最小值 {param_def['min']}"
                    )
            
            if 'max' in param_def:
                if param_value > param_def['max']:
                    raise ValueError(
                        f"参数 {param_name} 值 {param_value} 大于最大值 {param_def['max']}"
                    )
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数字典"""
        return self.params.copy()
    
    def set_parameters(self, params: Dict[str, Any]):
        """批量设置参数"""
        for param_name, param_value in params.items():
            if param_name in self.PARAMETERS:
                self.params[param_name] = param_value
            else:
                raise ValueError(f"未知参数: {param_name}")
        self.validate_parameters()
    
    def get_parameter(self, name: str, default: Any = None) -> Any:
        """获取单个参数值"""
        return self.params.get(name, default)
    
    def set_parameter(self, name: str, value: Any):
        """设置单个参数值"""
        if name not in self.PARAMETERS:
            raise ValueError(f"未知参数: {name}")
        self.params[name] = value
        self.validate_parameters()
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有参数的详细信息（用于UI显示）"""
        info = {}
        for param_name, param_def in self.PARAMETERS.items():
            info[param_name] = {
                'value': self.params[param_name],
                'type': param_def.get('type').__name__ if param_def.get('type') else 'any',
                'default': param_def.get('default'),
                'min': param_def.get('min'),
                'max': param_def.get('max'),
                'description': param_def.get('description', ''),
                'optimizable': param_def.get('optimizable', False)
            }
        return info
    
    def reset_state(self):
        """重置策略状态（用于回测重置）"""
        self.state = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于保存配置）"""
        return {
            'strategy_name': self.__class__.__name__,
            'parameters': self.params.copy(),
            'state': self.state.copy() if hasattr(self, 'state') else {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """从字典反序列化（用于加载配置）"""
        instance = cls(**data.get('parameters', {}))
        if 'state' in data:
            instance.state = data['state']
        return instance
    
    @abstractmethod
    def generate_signal(
        self,
        index: int,
        df: pd.DataFrame,
        position: Optional[Any],  # Position 对象或 None
        current_balance: float,
        performance_stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        生成交易信号
        
        Args:
            index: 当前K线索引
            df: 完整的历史K线数据（DataFrame，包含 timestamp, open, high, low, close, volume）
            position: 当前持仓（Position对象或None）
            current_balance: 当前账户余额
            performance_stats: 性能统计字典，包含 win_rate, total_trades 等
            
        Returns:
            交易信号字典或None：
            {
                'action': 'BUY' | 'SELL' | 'CLOSE' | None,
                'size': float,              # 仓位大小（合约张数）
                'stop_loss': float,         # 止损价格
                'take_profit': float,       # 止盈价格
                'leverage': int,            # 杠杆倍数
                'reason': str,              # 信号原因（用于日志）
                'metadata': Dict            # 策略特定元数据
            }
            如果返回None，表示不产生信号
        """
        pass
    
    def get_name(self) -> str:
        """获取策略名称"""
        return self.__class__.__name__
    
    def get_description(self) -> str:
        """获取策略描述（子类可重写）"""
        return f"{self.get_name()} 策略"
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"{self.get_name()}({self.params})"
