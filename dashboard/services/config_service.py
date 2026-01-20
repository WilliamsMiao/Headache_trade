"""
配置服务
负责配置验证和序列化
"""
import os
from typing import Dict, Any
from trading_bots import config as bot_config
from datetime import datetime
from dashboard.repositories.config_repository import load_trading_params as _load_trading_params


def validate_api_keys(config: Dict[str, Any]) -> bool:
    """
    验证API密钥有效性（仅验证格式，不用于交易）
    
    Args:
        config: 包含API密钥的配置字典
    
    Returns:
        验证是否通过
    """
    try:
        # 简单验证API密钥格式
        required_keys = ['deepseek_api_key', 'okx_api_key', 'okx_secret', 'okx_password']
        
        for key in required_keys:
            if not config.get(key) or len(config[key].strip()) < 10:
                return False
        
        return True
    except Exception as e:
        print(f"API密钥验证失败: {e}")
        return False


def serialize_trading_params() -> Dict[str, Any]:
    """
    从bot_config序列化交易参数
    
    Returns:
        序列化后的交易参数字典
    """
    cfg = bot_config.TRADE_CONFIG
    return {
        'symbol': cfg.get('symbol'),
        'timeframe': cfg.get('timeframe'),
        'leverage': cfg.get('leverage'),
        'fee_rate': bot_config.TRADING_FEE_RATE,
        'slippage': float(os.getenv('BOT_SLIPPAGE', '0.0001')),
        'risk': {
            'base_risk_per_trade': cfg['risk_management'].get('base_risk_per_trade'),
            'adaptive_risk_enabled': cfg['risk_management'].get('adaptive_risk_enabled', True),
            'target_utilization': cfg['risk_management'].get('target_capital_utilization'),
            'max_utilization': cfg['risk_management'].get('max_capital_utilization'),
            'max_leverage': cfg['risk_management'].get('max_leverage'),
            'lock_stop_loss_ratio': bot_config.LOCK_STOP_LOSS_RATIO,
            'lock_stop_loss_profit_threshold': bot_config.LOCK_STOP_LOSS_PROFIT_THRESHOLD / 100 if bot_config.LOCK_STOP_LOSS_PROFIT_THRESHOLD > 1 else bot_config.LOCK_STOP_LOSS_PROFIT_THRESHOLD,
        },
        'protection': {
            'orbit_update_interval': bot_config.ORBIT_UPDATE_INTERVAL,
            'orbit_min_trigger_time': bot_config.ORBIT_MIN_TRIGGER_TIME,
            'protection_levels': bot_config.PROTECTION_LEVELS,
        },
        'updated_at': datetime.utcnow().isoformat() + 'Z',
    }


def load_trading_params() -> Dict[str, Any]:
    """
    加载交易参数
    如果配置文件不存在，则返回默认配置
    
    Returns:
        交易参数字典
    """
    params = _load_trading_params()
    if not params:
        return serialize_trading_params()
    return params
