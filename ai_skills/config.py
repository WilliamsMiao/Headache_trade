"""
AI技能配置
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class AISkillsConfig:
    """AI技能系统配置"""
    
    # 技能协调层配置
    COORDINATOR_ENABLED = os.getenv("AI_SKILLS_ENABLED", "true").lower() == "true"
    COORDINATOR_INTERVAL = int(os.getenv("AI_SKILLS_INTERVAL", "300"))  # 5分钟
    
    # 技能执行配置
    SKILL_TIMEOUT = float(os.getenv("AI_SKILL_TIMEOUT", "5.0"))  # 默认5秒超时
    SKILL_MAX_RETRIES = int(os.getenv("AI_SKILL_MAX_RETRIES", "2"))
    
    # 技能开关
    MARKET_ANALYST_ENABLED = os.getenv("AI_MARKET_ANALYST_ENABLED", "true").lower() == "true"
    QUANT_STRATEGIST_ENABLED = os.getenv("AI_QUANT_STRATEGIST_ENABLED", "true").lower() == "true"
    RISK_MANAGER_ENABLED = os.getenv("AI_RISK_MANAGER_ENABLED", "true").lower() == "true"
    TRADE_EXECUTOR_ENABLED = os.getenv("AI_TRADE_EXECUTOR_ENABLED", "true").lower() == "true"
    
    # 技能优先级（1-10，数字越大优先级越高）
    MARKET_ANALYST_PRIORITY = int(os.getenv("AI_MARKET_ANALYST_PRIORITY", "5"))
    QUANT_STRATEGIST_PRIORITY = int(os.getenv("AI_QUANT_STRATEGIST_PRIORITY", "7"))
    RISK_MANAGER_PRIORITY = int(os.getenv("AI_RISK_MANAGER_PRIORITY", "9"))  # 最高优先级
    TRADE_EXECUTOR_PRIORITY = int(os.getenv("AI_TRADE_EXECUTOR_PRIORITY", "8"))
    
    # 熔断器配置
    CIRCUIT_BREAKER_ENABLED = os.getenv("AI_CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("AI_CIRCUIT_BREAKER_THRESHOLD", "5"))
    CIRCUIT_BREAKER_RESET_TIMEOUT = int(os.getenv("AI_CIRCUIT_BREAKER_RESET", "300"))  # 5分钟
    
    # 性能监控配置
    PERFORMANCE_MONITORING_ENABLED = os.getenv("AI_PERF_MONITORING_ENABLED", "true").lower() == "true"
    PERFORMANCE_LOG_INTERVAL = int(os.getenv("AI_PERF_LOG_INTERVAL", "3600"))  # 1小时
    
    # 回退机制配置
    FALLBACK_TO_LEGACY = os.getenv("AI_FALLBACK_LEGACY", "true").lower() == "true"
    
    # 多时间框架配置
    MULTI_TIMEFRAME_ENABLED = os.getenv("AI_MULTI_TIMEFRAME_ENABLED", "true").lower() == "true"
    TIMEFRAMES = os.getenv("AI_TIMEFRAMES", "1m,5m,15m,1h,4h,1d").split(",")
    
    # 链上数据配置（未来扩展）
    ONCHAIN_DATA_ENABLED = os.getenv("AI_ONCHAIN_ENABLED", "false").lower() == "true"
    
    # 市场情绪配置
    SENTIMENT_ANALYSIS_ENABLED = os.getenv("AI_SENTIMENT_ENABLED", "true").lower() == "true"
    
    @classmethod
    def get_skill_config(cls, skill_name: str) -> Dict[str, Any]:
        """获取特定技能的配置"""
        config_map = {
            'market_analyst': {
                'enabled': cls.MARKET_ANALYST_ENABLED,
                'priority': cls.MARKET_ANALYST_PRIORITY,
                'timeout': cls.SKILL_TIMEOUT
            },
            'quant_strategist': {
                'enabled': cls.QUANT_STRATEGIST_ENABLED,
                'priority': cls.QUANT_STRATEGIST_PRIORITY,
                'timeout': cls.SKILL_TIMEOUT
            },
            'risk_manager': {
                'enabled': cls.RISK_MANAGER_ENABLED,
                'priority': cls.RISK_MANAGER_PRIORITY,
                'timeout': cls.SKILL_TIMEOUT
            },
            'trade_executor': {
                'enabled': cls.TRADE_EXECUTOR_ENABLED,
                'priority': cls.TRADE_EXECUTOR_PRIORITY,
                'timeout': cls.SKILL_TIMEOUT
            }
        }
        
        return config_map.get(skill_name, {
            'enabled': True,
            'priority': 5,
            'timeout': cls.SKILL_TIMEOUT
        })
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """转换为字典（用于日志/监控）"""
        return {
            'coordinator_enabled': cls.COORDINATOR_ENABLED,
            'coordinator_interval': cls.COORDINATOR_INTERVAL,
            'skill_timeout': cls.SKILL_TIMEOUT,
            'market_analyst': cls.get_skill_config('market_analyst'),
            'quant_strategist': cls.get_skill_config('quant_strategist'),
            'risk_manager': cls.get_skill_config('risk_manager'),
            'trade_executor': cls.get_skill_config('trade_executor'),
            'circuit_breaker_enabled': cls.CIRCUIT_BREAKER_ENABLED,
            'fallback_to_legacy': cls.FALLBACK_TO_LEGACY
        }
