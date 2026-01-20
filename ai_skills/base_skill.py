"""
基础技能抽象类
定义所有AI技能的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import time


class SkillStatus(Enum):
    """技能状态"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


class SkillResult:
    """技能执行结果"""
    
    def __init__(
        self,
        skill_name: str,
        status: SkillStatus,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.skill_name = skill_name
        self.status = status
        self.output = output or {}
        self.error = error
        self.execution_time = execution_time
        self.confidence = confidence
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == SkillStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'skill_name': self.skill_name,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'execution_time': self.execution_time,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class BaseSkill(ABC):
    """AI技能基类，所有技能必须继承此类"""
    
    def __init__(
        self,
        name: str,
        timeout: float = 5.0,
        enabled: bool = True,
        priority: int = 5
    ):
        """
        初始化技能
        
        Args:
            name: 技能名称
            timeout: 执行超时时间（秒）
            enabled: 是否启用
            priority: 优先级（1-10，数字越大优先级越高）
        """
        self.name = name
        self.timeout = timeout
        self.enabled = enabled
        self.priority = priority
        self.status = SkillStatus.IDLE
        self.last_result: Optional[SkillResult] = None
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
    
    @abstractmethod
    def execute(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """
        执行技能
        
        Args:
            context: 共享上下文
            input_data: 输入数据
            
        Returns:
            SkillResult: 执行结果
        """
        pass
    
    @abstractmethod
    def get_required_inputs(self) -> List[str]:
        """
        获取所需的输入字段列表
        
        Returns:
            List[str]: 输入字段名称列表
        """
        pass
    
    @abstractmethod
    def get_output_schema(self) -> Dict[str, Any]:
        """
        获取输出数据格式定义
        
        Returns:
            Dict: 输出格式定义
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        required = self.get_required_inputs()
        for field in required:
            if field not in input_data:
                return False
        return True
    
    def run_with_timeout(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """
        带超时控制的执行方法
        
        Args:
            context: 共享上下文
            input_data: 输入数据
            
        Returns:
            SkillResult: 执行结果
        """
        if not self.enabled:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.DISABLED,
                error="技能已禁用"
            )
        
        if not self.validate_input(input_data):
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"输入数据验证失败，缺少必需字段: {self.get_required_inputs()}"
            )
        
        self.status = SkillStatus.RUNNING
        self.execution_count += 1
        start_time = time.time()
        
        try:
            # 使用超时机制执行
            result = self.execute(context, input_data)
            execution_time = time.time() - start_time
            
            if execution_time > self.timeout:
                result = SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.TIMEOUT,
                    error=f"执行超时（{execution_time:.2f}s > {self.timeout}s）"
                )
            
            result.execution_time = execution_time
            
            if result.is_success():
                self.success_count += 1
            else:
                self.failure_count += 1
            
            self.last_result = result
            self.status = result.status
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.failure_count += 1
            result = SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=str(e),
                execution_time=execution_time
            )
            self.last_result = result
            self.status = SkillStatus.FAILED
            return result
        finally:
            if self.status == SkillStatus.RUNNING:
                self.status = SkillStatus.IDLE
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取技能统计信息"""
        total = self.execution_count
        success_rate = (self.success_count / total * 100) if total > 0 else 0.0
        
        return {
            'name': self.name,
            'enabled': self.enabled,
            'status': self.status.value,
            'execution_count': total,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'last_execution_time': self.last_result.execution_time if self.last_result else 0.0
        }
    
    def enable(self):
        """启用技能"""
        self.enabled = True
    
    def disable(self):
        """禁用技能"""
        self.enabled = False
        self.status = SkillStatus.DISABLED
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, enabled={self.enabled}, status={self.status.value})"
