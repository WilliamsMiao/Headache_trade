"""
配置管理模块
支持配置热更新、缓存管理等性能优化
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from functools import lru_cache
import threading


class ConfigManager:
    """配置管理器（支持热更新）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.config_file = Path("config/trading_config.json")
            self.config = {}
            self.last_modified = None
            self.check_interval = 5  # 检查间隔（秒）
            self.last_check = datetime.now()
            self._load_config()
            self._initialized = True
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.last_modified = self.config_file.stat().st_mtime
                print(f"[OK] 配置已加载: {self.config_file}")
            else:
                # 创建默认配置
                self._create_default_config()
        except Exception as e:
            print(f"[FAIL] 加载配置失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        default_config = {
            "trading": {
                "symbol": "BTC/USDT:USDT",
                "max_position_pct": 0.8,
                "min_position_pct": 0.1,
                "default_leverage": 2,
                "min_confidence": 60,
            },
            "risk_management": {
                "base_risk_pct": 0.01,
                "max_risk_pct": 0.02,
                "min_risk_reward_ratio": 1.5,
                "trailing_stop_activation": 0.5,
                "trailing_stop_distance": 0.3,
            },
            "indicators": {
                "atr_period": 14,
                "rsi_period": 14,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "bb_period": 20,
                "bb_std": 2,
            },
            "api": {
                "deepseek_timeout": 30,
                "exchange_timeout": 10,
                "sentiment_api_timeout": 10,
                "max_retries": 3,
            },
            "performance": {
                "enable_cache": True,
                "cache_ttl": 60,
                "use_async_api": False,
                "dashboard_update_interval": 5,
            },
            "logging": {
                "level": "INFO",
                "console_level": "INFO",
                "file_level": "DEBUG",
                "rotation": "00:00",
                "retention": "30 days",
            }
        }
        
        self.config = default_config
        self._save_config()
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print(f"[OK] 配置已保存: {self.config_file}")
        except Exception as e:
            print(f"[FAIL] 保存配置失败: {e}")
    
    def reload_if_changed(self):
        """检查并重新加载配置（如果文件已修改）"""
        now = datetime.now()
        
        # 控制检查频率
        if (now - self.last_check).total_seconds() < self.check_interval:
            return False
        
        self.last_check = now
        
        try:
            if self.config_file.exists():
                current_mtime = self.config_file.stat().st_mtime
                
                if self.last_modified is None or current_mtime > self.last_modified:
                    print("🔄 检测到配置文件变化，重新加载...")
                    self._load_config()
                    return True
        
        except Exception as e:
            print(f"[FAIL] 检查配置文件失败: {e}")
        
        return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）
        
        Args:
            key_path: 配置路径，如 "trading.symbol"
            default: 默认值
        
        Returns:
            配置值
        """
        # 检查是否需要重新加载
        self.reload_if_changed()
        
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any, save: bool = True):
        """
        设置配置值
        
        Args:
            key_path: 配置路径
            value: 值
            save: 是否保存到文件
        """
        keys = key_path.split('.')
        config = self.config
        
        # 遍历到倒数第二层
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置值
        config[keys[-1]] = value
        
        if save:
            self._save_config()
    
    def get_all(self) -> Dict:
        """获取所有配置"""
        self.reload_if_changed()
        return self.config.copy()


# 全局配置实例
config_manager = ConfigManager()


# =============================================================================
# 缓存管理
# =============================================================================

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, ttl: int = 60):
        """
        Args:
            ttl: 缓存生存时间（秒）
        """
        self.cache = {}
        self.ttl = ttl
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                
                # 检查是否过期
                if (datetime.now() - timestamp).total_seconds() < self.ttl:
                    return value
                else:
                    # 过期，删除
                    del self.cache[key]
            
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存"""
        with self._lock:
            self.cache[key] = (value, datetime.now())
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self.cache.clear()
    
    def remove(self, key: str):
        """删除指定缓存"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
    
    def cleanup(self):
        """清理过期缓存"""
        with self._lock:
            now = datetime.now()
            expired_keys = []
            
            for key, (value, timestamp) in self.cache.items():
                if (now - timestamp).total_seconds() >= self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                print(f"🧹 已清理 {len(expired_keys)} 个过期缓存")


# 全局缓存实例
cache_manager = CacheManager(ttl=60)


# =============================================================================
# 便捷函数
# =============================================================================

def get_config(key_path: str, default: Any = None) -> Any:
    """获取配置值"""
    return config_manager.get(key_path, default)


def set_config(key_path: str, value: Any, save: bool = True):
    """设置配置值"""
    config_manager.set(key_path, value, save)


def reload_config():
    """重新加载配置"""
    config_manager._load_config()


def get_cache(key: str) -> Optional[Any]:
    """获取缓存"""
    if not get_config('performance.enable_cache', True):
        return None
    return cache_manager.get(key)


def set_cache(key: str, value: Any):
    """设置缓存"""
    if get_config('performance.enable_cache', True):
        ttl = get_config('performance.cache_ttl', 60)
        cache_manager.ttl = ttl
        cache_manager.set(key, value)


def clear_cache():
    """清空缓存"""
    cache_manager.clear()


# 缓存装饰器
def cached(ttl: Optional[int] = None):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存生存时间（秒），None使用默认值
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 检查是否启用缓存
            if not get_config('performance.enable_cache', True):
                return func(*args, **kwargs)
            
            # 生成缓存键
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # 尝试从缓存获取
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 保存到缓存
            if ttl:
                old_ttl = cache_manager.ttl
                cache_manager.ttl = ttl
                cache_manager.set(cache_key, result)
                cache_manager.ttl = old_ttl
            else:
                cache_manager.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator


# 导出
__all__ = [
    'ConfigManager',
    'CacheManager',
    'config_manager',
    'cache_manager',
    'get_config',
    'set_config',
    'reload_config',
    'get_cache',
    'set_cache',
    'clear_cache',
    'cached',
]
