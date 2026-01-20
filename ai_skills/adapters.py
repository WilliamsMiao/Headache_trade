"""
适配层
负责数据格式转换、结果映射、性能监控
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.config import AISkillsConfig


class DataAdapter:
    """数据适配器 - 转换数据格式"""
    
    @staticmethod
    def convert_market_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将现有系统的市场数据转换为AI技能标准格式
        
        Args:
            raw_data: 原始市场数据（来自get_btc_ohlcv_enhanced）
            
        Returns:
            标准化的市场数据
        """
        return {
            'market_data': raw_data,
            'full_data': raw_data.get('full_data'),
            'kline_data': raw_data.get('kline_data', []),
            'price': raw_data.get('price', 0),
            'timestamp': raw_data.get('timestamp', datetime.now().isoformat())
        }
    
    @staticmethod
    def convert_signal(ai_signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        将AI技能输出转换为现有系统的交易信号格式
        
        Args:
            ai_signal: AI技能输出的信号
            
        Returns:
            现有系统格式的信号
        """
        # 映射字段
        action = ai_signal.get('action', 'HOLD')
        
        # 转换为现有系统的信号格式
        signal_map = {
            'BUY': 'BUY',
            'SELL': 'SELL',
            'HOLD': 'HOLD',
            'CLOSE': 'HOLD'  # CLOSE在现有系统中可能需要特殊处理
        }
        
        signal = signal_map.get(action, 'HOLD')
        
        return {
            'signal': signal,
            'confidence': ai_signal.get('confidence', 0.5),
            'size': ai_signal.get('size', 0),
            'stop_loss': ai_signal.get('stop_loss', 0),
            'take_profit': ai_signal.get('take_profit', 0),
            'leverage': ai_signal.get('leverage', 6),
            'reason': ai_signal.get('reasoning', ai_signal.get('reason', 'AI决策')),
            'trend_score': 0,  # 从market_analysis中获取
            'risk_score': ai_signal.get('risk_score', 0),
            'strategy_name': ai_signal.get('strategy_name', 'ai_team'),
            'ai_decision': True,  # 标记为AI决策
            'risk_adjustments': ai_signal.get('risk_adjustments', {})
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics_file = Path('data/ai_skills_performance.json')
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.metrics: Dict[str, Any] = {
            'skills': {},
            'coordinator': {},
            'last_update': None
        }
        self.load_metrics()
    
    def track_skill_performance(self, skill_name: str, metrics: Dict[str, Any]) -> None:
        """跟踪技能性能"""
        if skill_name not in self.metrics['skills']:
            self.metrics['skills'][skill_name] = {
                'execution_count': 0,
                'success_count': 0,
                'failure_count': 0,
                'total_execution_time': 0,
                'avg_execution_time': 0,
                'last_execution': None
            }
        
        skill_metrics = self.metrics['skills'][skill_name]
        skill_metrics['execution_count'] += 1
        skill_metrics['last_execution'] = datetime.now().isoformat()
        
        if metrics.get('success', False):
            skill_metrics['success_count'] += 1
        else:
            skill_metrics['failure_count'] += 1
        
        execution_time = metrics.get('execution_time', 0)
        if execution_time > 0:
            skill_metrics['total_execution_time'] += execution_time
            skill_metrics['avg_execution_time'] = (
                skill_metrics['total_execution_time'] / skill_metrics['execution_count']
            )
        
        self.metrics['last_update'] = datetime.now().isoformat()
        self.save_metrics()
    
    def track_coordinator_performance(self, metrics: Dict[str, Any]) -> None:
        """跟踪协调器性能"""
        self.metrics['coordinator'].update(metrics)
        self.metrics['last_update'] = datetime.now().isoformat()
        self.save_metrics()
    
    def get_skill_stats(self, skill_name: str) -> Dict[str, Any]:
        """获取技能统计信息"""
        return self.metrics['skills'].get(skill_name, {})
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        return self.metrics.copy()
    
    def save_metrics(self) -> None:
        """保存指标到文件"""
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存性能指标失败: {e}")
    
    def load_metrics(self) -> None:
        """从文件加载指标"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.metrics.update(loaded)
        except Exception as e:
            print(f"⚠️ 加载性能指标失败: {e}")
    
    def reset_metrics(self) -> None:
        """重置指标"""
        self.metrics = {
            'skills': {},
            'coordinator': {},
            'last_update': None
        }
        self.save_metrics()


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()
