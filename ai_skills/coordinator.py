"""
Skill Coordinator - 技能协调层
负责技能调度、结果聚合、异常熔断
"""

import sys
import os
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.base_skill import BaseSkill, SkillResult, SkillStatus
from ai_skills.context_manager import ContextManager
from ai_skills.messaging import MessageBus, MessageType
from ai_skills.config import AISkillsConfig
from ai_skills.market_analyst import MarketAnalystSkill
from ai_skills.quant_strategist import QuantStrategistSkill
from ai_skills.risk_manager import RiskManagerSkill
from ai_skills.trade_executor import TradeExecutorSkill


class TriggerType(Enum):
    """触发类型"""
    TIME = "time"  # 时间触发
    EVENT = "event"  # 事件触发
    MANUAL = "manual"  # 手动触发


class Trigger:
    """触发条件"""
    
    def __init__(self, trigger_type: TriggerType, condition: Optional[Callable] = None):
        self.trigger_type = trigger_type
        self.condition = condition  # 可选的触发条件函数
        self.last_triggered = None


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: int = 300
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = {}
        self.last_failure_time = {}
        self.state = {}  # 'closed', 'open', 'half_open'
    
    def check(self, skill_name: str) -> bool:
        """检查是否允许执行"""
        if skill_name not in self.state:
            self.state[skill_name] = 'closed'
            self.failure_count[skill_name] = 0
            self.last_failure_time[skill_name] = None
        
        state = self.state[skill_name]
        
        if state == 'open':
            # 检查是否可以重置
            if self.last_failure_time[skill_name]:
                elapsed = time.time() - self.last_failure_time[skill_name]
                if elapsed >= self.reset_timeout:
                    self.state[skill_name] = 'half_open'
                    return True
            return False
        
        return True
    
    def record_success(self, skill_name: str):
        """记录成功"""
        if skill_name in self.state:
            if self.state[skill_name] == 'half_open':
                self.state[skill_name] = 'closed'
            self.failure_count[skill_name] = 0
    
    def record_failure(self, skill_name: str):
        """记录失败"""
        if skill_name not in self.state:
            self.state[skill_name] = 'closed'
            self.failure_count[skill_name] = 0
        
        self.failure_count[skill_name] += 1
        self.last_failure_time[skill_name] = time.time()
        
        if self.failure_count[skill_name] >= self.failure_threshold:
            self.state[skill_name] = 'open'
            print(f"⚠️ 熔断器触发: {skill_name} 失败次数达到阈值")
    
    def get_state(self, skill_name: str) -> str:
        """获取熔断器状态"""
        return self.state.get(skill_name, 'closed')


class SkillCoordinator:
    """技能协调器 - 单例模式"""
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            import threading
            cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self.context_manager = ContextManager()
        self.message_bus = MessageBus()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=AISkillsConfig.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=AISkillsConfig.CIRCUIT_BREAKER_RESET_TIMEOUT
        ) if AISkillsConfig.CIRCUIT_BREAKER_ENABLED else None
        
        # 初始化技能
        self.skills: Dict[str, BaseSkill] = {}
        self._initialize_skills()
        
        # 调度器状态
        self.last_execution_time = None
        self.execution_count = 0
        
        self._initialized = True
    
    def _initialize_skills(self):
        """初始化所有技能"""
        try:
            if AISkillsConfig.MARKET_ANALYST_ENABLED:
                self.skills['market_analyst'] = MarketAnalystSkill()
            
            if AISkillsConfig.QUANT_STRATEGIST_ENABLED:
                self.skills['quant_strategist'] = QuantStrategistSkill()
            
            if AISkillsConfig.RISK_MANAGER_ENABLED:
                self.skills['risk_manager'] = RiskManagerSkill()
            
            if AISkillsConfig.TRADE_EXECUTOR_ENABLED:
                self.skills['trade_executor'] = TradeExecutorSkill()
            
            print(f"✅ 已初始化 {len(self.skills)} 个AI技能")
        except Exception as e:
            print(f"⚠️ 技能初始化失败: {e}")
    
    def execute_trading_cycle(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        执行完整的交易周期
        
        Args:
            market_data: 市场数据
            
        Returns:
            最终交易决策或None
        """
        try:
            start_time = time.time()
            self.execution_count += 1
            self.last_execution_time = datetime.now()
            
            print(f"\n{'='*60}")
            print(f"🚀 AI交易团队执行周期 #{self.execution_count}")
            print(f"{'='*60}")
            
            # 1. Market Analyst Skill
            market_analysis_result = self._execute_skill(
                'market_analyst',
                {'market_data': market_data}
            )
            
            if not market_analysis_result or not market_analysis_result.is_success():
                print("⚠️ 市场分析失败，使用备用策略")
                if AISkillsConfig.FALLBACK_TO_LEGACY:
                    return self._fallback_to_legacy(market_data)
                return None
            
            market_analysis = market_analysis_result.output
            
            # 更新上下文
            self.context_manager.update_market_state(market_analysis)
            
            # 2. Quant Strategist Skill
            strategy_result = self._execute_skill(
                'quant_strategist',
                {'market_analysis': market_analysis}
            )
            
            if not strategy_result or not strategy_result.is_success():
                print("⚠️ 策略生成失败，保持HOLD")
                return {
                    'action': 'HOLD',
                    'reason': '策略生成失败'
                }
            
            strategy_signal = strategy_result.output
            
            # 更新上下文
            self.context_manager.add_strategy_signal(strategy_signal)
            
            # 3. Risk Manager Skill
            risk_result = self._execute_skill(
                'risk_manager',
                {
                    'strategy_signal': strategy_signal,
                    'market_analysis': market_analysis
                }
            )
            
            if not risk_result or not risk_result.is_success():
                print("⚠️ 风险管理失败，拒绝交易")
                return {
                    'action': 'HOLD',
                    'reason': '风险管理失败'
                }
            
            risk_adjusted_signal = risk_result.output
            
            # 更新上下文
            self.context_manager.update_risk_parameters({
                'risk_score': risk_adjusted_signal.get('risk_score', 0),
                'position_size': risk_adjusted_signal.get('size', 0)
            })
            
            # 4. Trade Executor Skill（如果需要执行）
            if risk_adjusted_signal.get('action') in ['BUY', 'SELL', 'CLOSE']:
                execution_result = self._execute_skill(
                    'trade_executor',
                    {'risk_adjusted_signal': risk_adjusted_signal}
                )
                
                if execution_result and execution_result.is_success():
                    # 更新上下文
                    self.context_manager.update_performance_metrics({
                        'last_execution': execution_result.output,
                        'execution_time': time.time() - start_time
                    })
                    
                    # 发布执行结果消息
                    self.message_bus.publish_simple(
                        MessageType.EXECUTION_RESULT,
                        'coordinator',
                        execution_result.output
                    )
            
            execution_time = time.time() - start_time
            print(f"✅ 交易周期完成，耗时 {execution_time:.2f}秒")
            
            return risk_adjusted_signal
            
        except Exception as e:
            print(f"❌ 交易周期执行失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _execute_skill(
        self,
        skill_name: str,
        input_data: Dict[str, Any]
    ) -> Optional[SkillResult]:
        """执行技能"""
        if skill_name not in self.skills:
            print(f"⚠️ 技能 {skill_name} 不存在")
            return None
        
        skill = self.skills[skill_name]
        
        # 检查熔断器
        if self.circuit_breaker and not self.circuit_breaker.check(skill_name):
            print(f"⚠️ 技能 {skill_name} 已熔断，跳过执行")
            return None
        
        # 获取上下文
        context = self.context_manager.get_context()
        
        # 执行技能
        try:
            result = skill.run_with_timeout(context, input_data)
            
            # 更新熔断器状态
            if self.circuit_breaker:
                if result.is_success():
                    self.circuit_breaker.record_success(skill_name)
                else:
                    self.circuit_breaker.record_failure(skill_name)
            
            # 发布消息
            if result.is_success():
                self.message_bus.publish_simple(
                    MessageType.MARKET_ANALYSIS if skill_name == 'market_analyst' else
                    MessageType.STRATEGY_SIGNAL if skill_name == 'quant_strategist' else
                    MessageType.RISK_ASSESSMENT if skill_name == 'risk_manager' else
                    MessageType.TRADE_EXECUTION,
                    skill_name,
                    result.output
                )
            else:
                self.message_bus.publish_simple(
                    MessageType.ERROR,
                    skill_name,
                    {'error': result.error}
                )
            
            return result
            
        except Exception as e:
            print(f"⚠️ 技能 {skill_name} 执行异常: {e}")
            if self.circuit_breaker:
                self.circuit_breaker.record_failure(skill_name)
            return None
    
    def _fallback_to_legacy(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """回退到传统策略"""
        print("🔄 回退到传统策略系统")
        # 这里可以调用原有的信号生成逻辑
        # 简化处理，返回HOLD
        return {
            'action': 'HOLD',
            'reason': 'AI技能失败，回退到传统策略'
        }
    
    def get_skill_statistics(self) -> Dict[str, Any]:
        """获取所有技能的统计信息"""
        stats = {}
        for name, skill in self.skills.items():
            stats[name] = skill.get_statistics()
        return stats
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        return {
            'enabled': AISkillsConfig.COORDINATOR_ENABLED,
            'skills_count': len(self.skills),
            'execution_count': self.execution_count,
            'last_execution_time': self.last_execution_time.isoformat() if self.last_execution_time else None,
            'circuit_breaker_enabled': AISkillsConfig.CIRCUIT_BREAKER_ENABLED,
            'skills': list(self.skills.keys())
        }
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        return cls()
