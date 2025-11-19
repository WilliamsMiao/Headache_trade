"""
增强版配置加载器
支持YAML和JSON格式,环境变量替换,配置继承等高级特性
"""

import os
import re
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime
import threading
from copy import deepcopy

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("[WARN] PyYAML未安装，仅支持JSON配置文件")


class ConfigLoader:
    """
    配置加载器
    
    特性:
    - 支持YAML和JSON格式
    - 环境变量替换: ${ENV_VAR} 或 ${ENV_VAR:default}
    - 配置继承和覆盖
    - 热更新检测
    - 配置验证
    """
    
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
            self.config = {}
            self.config_file: Optional[Path] = None
            self.last_modified = None
            self.check_interval = 5  # 检查间隔(秒)
            self.last_check = datetime.now()
            self._env_pattern = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')
            self._initialized = True
    
    def load(self, config_path: Union[str, Path], 
             environment: Optional[str] = None,
             base_config: Optional[Dict] = None) -> Dict:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
            environment: 环境名称 (dev, test, prod等)
            base_config: 基础配置(用于继承)
            
        Returns:
            配置字典
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        self.config_file = config_path
        self.last_modified = config_path.stat().st_mtime
        
        # 加载配置文件
        if config_path.suffix in ['.yaml', '.yml']:
            if not YAML_AVAILABLE:
                raise ImportError("需要安装PyYAML: pip install pyyaml")
            raw_config = self._load_yaml(config_path)
        elif config_path.suffix == '.json':
            raw_config = self._load_json(config_path)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")
        
        # 合并基础配置
        if base_config:
            config = self._merge_configs(base_config, raw_config)
        else:
            config = raw_config
        
        # 加载环境特定配置
        if environment:
            env_config_path = self._get_env_config_path(config_path, environment)
            if env_config_path.exists():
                print(f"[LOG] 加载环境配置: {env_config_path}")
                if env_config_path.suffix in ['.yaml', '.yml']:
                    env_config = self._load_yaml(env_config_path)
                else:
                    env_config = self._load_json(env_config_path)
                config = self._merge_configs(config, env_config)
        
        # 替换环境变量
        config = self._replace_env_vars(config)
        
        # 验证配置
        self._validate_config(config)
        
        self.config = config
        print(f"[OK] 配置加载成功: {config_path}")
        
        return config
    
    def _load_yaml(self, path: Path) -> Dict:
        """加载YAML文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _load_json(self, path: Path) -> Dict:
        """加载JSON文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_env_config_path(self, base_path: Path, environment: str) -> Path:
        """获取环境特定配置文件路径"""
        stem = base_path.stem
        suffix = base_path.suffix
        return base_path.parent / f"{stem}.{environment}{suffix}"
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """
        深度合并配置字典
        
        Args:
            base: 基础配置
            override: 覆盖配置
            
        Returns:
            合并后的配置
        """
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def _replace_env_vars(self, config: Any) -> Any:
        """
        递归替换环境变量
        
        支持格式:
        - ${ENV_VAR}: 使用环境变量,如不存在则保持原样
        - ${ENV_VAR:default}: 使用环境变量,如不存在则使用默认值
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str):
            return self._replace_string_env_vars(config)
        else:
            return config
    
    def _replace_string_env_vars(self, text: str) -> str:
        """替换字符串中的环境变量"""
        def replacer(match):
            env_var = match.group(1)
            default_value = match.group(2)
            
            value = os.getenv(env_var)
            
            if value is not None:
                return value
            elif default_value is not None:
                return default_value
            else:
                return match.group(0)  # 保持原样
        
        return self._env_pattern.sub(replacer, text)
    
    def _validate_config(self, config: Dict):
        """
        验证配置
        
        可以在这里添加配置验证规则
        """
        required_sections = ['trading', 'risk_management']
        
        for section in required_sections:
            if section not in config:
                print(f"[WARN] 警告: 缺少必需的配置节: {section}")
    
    def reload_if_changed(self) -> bool:
        """
        检查并重新加载配置(如果文件已修改)
        
        Returns:
            是否重新加载了配置
        """
        if not self.config_file or not self.config_file.exists():
            return False
        
        now = datetime.now()
        
        # 控制检查频率
        if (now - self.last_check).total_seconds() < self.check_interval:
            return False
        
        self.last_check = now
        
        try:
            current_mtime = self.config_file.stat().st_mtime
            
            if current_mtime > self.last_modified:
                print("🔄 检测到配置文件变化,重新加载...")
                self.load(self.config_file)
                return True
        except Exception as e:
            print(f"[FAIL] 检查配置文件失败: {e}")
        
        return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值(支持点号分隔的路径)
        
        Args:
            key_path: 配置路径,如 "trading.symbol"
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
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值(仅在内存中,不保存到文件)
        
        Args:
            key_path: 配置路径
            value: 值
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
    
    def get_all(self) -> Dict:
        """获取所有配置"""
        self.reload_if_changed()
        return deepcopy(self.config)
    
    def save(self, output_path: Optional[Union[str, Path]] = None):
        """
        保存配置到文件
        
        Args:
            output_path: 输出路径,如果为None则覆盖原文件
        """
        if output_path is None:
            if self.config_file is None:
                raise ValueError("没有指定输出路径")
            output_path = self.config_file
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_path.suffix in ['.yaml', '.yml']:
            if not YAML_AVAILABLE:
                raise ImportError("需要安装PyYAML: pip install pyyaml")
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
        elif output_path.suffix == '.json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        else:
            raise ValueError(f"不支持的文件格式: {output_path.suffix}")
        
        print(f"[OK] 配置已保存: {output_path}")


# 全局配置加载器实例
config_loader = ConfigLoader()


# 便捷函数
def load_config(config_path: Union[str, Path], 
                environment: Optional[str] = None) -> Dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        environment: 环境名称(dev, test, prod等)
        
    Returns:
        配置字典
    """
    return config_loader.load(config_path, environment)


def get_config(key_path: str, default: Any = None) -> Any:
    """
    获取配置值
    
    Args:
        key_path: 配置路径,如 "trading.symbol"
        default: 默认值
        
    Returns:
        配置值
    """
    return config_loader.get(key_path, default)


def set_config(key_path: str, value: Any):
    """
    设置配置值(仅在内存中)
    
    Args:
        key_path: 配置路径
        value: 值
    """
    config_loader.set(key_path, value)


def reload_config() -> bool:
    """
    重新加载配置
    
    Returns:
        是否重新加载了配置
    """
    return config_loader.reload_if_changed()


def save_config(output_path: Optional[Union[str, Path]] = None):
    """
    保存配置到文件
    
    Args:
        output_path: 输出路径
    """
    config_loader.save(output_path)


# 导出
__all__ = [
    'ConfigLoader',
    'config_loader',
    'load_config',
    'get_config',
    'set_config',
    'reload_config',
    'save_config',
]
