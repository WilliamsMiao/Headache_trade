"""
上下文管理器
维护跨技能共享的上下文数据
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import threading


class ContextManager:
    """上下文管理器 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._context: Dict[str, Any] = {
            'market_state': {},
            'strategy_signals': [],
            'risk_parameters': {},
            'position_info': {},
            'performance_metrics': {},
            'last_update': None,
            'version': 1
        }
        
        self._lock = threading.RLock()
        self._context_file = Path('data/ai_skills_context.json')
        self._context_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载持久化的上下文
        self.load_context()
        self._initialized = True
    
    def get_context(self) -> Dict[str, Any]:
        """获取完整上下文"""
        with self._lock:
            return self._context.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文中的值"""
        with self._lock:
            return self._context.get(key, default)
    
    def update(self, updates: Dict[str, Any]) -> None:
        """更新上下文"""
        with self._lock:
            self._context.update(updates)
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def update_market_state(self, market_state: Dict[str, Any]) -> None:
        """更新市场状态"""
        with self._lock:
            self._context['market_state'] = market_state
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def add_strategy_signal(self, signal: Dict[str, Any]) -> None:
        """添加策略信号"""
        with self._lock:
            if 'strategy_signals' not in self._context:
                self._context['strategy_signals'] = []
            
            # 限制历史信号数量（保留最近100条）
            self._context['strategy_signals'].append(signal)
            if len(self._context['strategy_signals']) > 100:
                self._context['strategy_signals'] = self._context['strategy_signals'][-100:]
            
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def update_risk_parameters(self, risk_params: Dict[str, Any]) -> None:
        """更新风险参数"""
        with self._lock:
            self._context['risk_parameters'].update(risk_params)
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def update_position_info(self, position_info: Dict[str, Any]) -> None:
        """更新持仓信息"""
        with self._lock:
            self._context['position_info'] = position_info
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def update_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """更新性能指标"""
        with self._lock:
            self._context['performance_metrics'].update(metrics)
            self._context['last_update'] = datetime.now().isoformat()
            self._save_context()
    
    def clear_strategy_signals(self) -> None:
        """清空策略信号历史"""
        with self._lock:
            self._context['strategy_signals'] = []
            self._save_context()
    
    def _save_context(self) -> None:
        """保存上下文到文件"""
        try:
            with open(self._context_file, 'w', encoding='utf-8') as f:
                json.dump(self._context, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 保存上下文失败: {e}")
    
    def load_context(self) -> None:
        """从文件加载上下文"""
        try:
            if self._context_file.exists():
                with open(self._context_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并加载的上下文，保留默认值
                    self._context.update(loaded)
                    print(f"✅ 已加载上下文: {self._context_file}")
        except Exception as e:
            print(f"⚠️ 加载上下文失败: {e}")
    
    def reset(self) -> None:
        """重置上下文"""
        with self._lock:
            self._context = {
                'market_state': {},
                'strategy_signals': [],
                'risk_parameters': {},
                'position_info': {},
                'performance_metrics': {},
                'last_update': None,
                'version': 1
            }
            self._save_context()
    
    def get_recent_signals(self, count: int = 10) -> list:
        """获取最近的策略信号"""
        with self._lock:
            signals = self._context.get('strategy_signals', [])
            return signals[-count:] if signals else []
    
    def get_market_state(self) -> Dict[str, Any]:
        """获取市场状态"""
        with self._lock:
            return self._context.get('market_state', {}).copy()
    
    def get_risk_parameters(self) -> Dict[str, Any]:
        """获取风险参数"""
        with self._lock:
            return self._context.get('risk_parameters', {}).copy()
    
    def get_position_info(self) -> Dict[str, Any]:
        """获取持仓信息"""
        with self._lock:
            return self._context.get('position_info', {}).copy()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        with self._lock:
            return self._context.get('performance_metrics', {}).copy()
