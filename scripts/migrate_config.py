#!/usr/bin/env python
"""
配置迁移工具
将旧的JSON配置文件转换为新的YAML格式
"""

import json
import argparse
from pathlib import Path
from typing import Dict

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("[FAIL] 需要安装PyYAML: pip install pyyaml")
    exit(1)


def load_json_config(json_path: Path) -> Dict:
    """加载JSON配置文件"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def migrate_config(old_config: Dict) -> Dict:
    """
    迁移配置结构
    将旧格式转换为新格式
    """
    new_config = {}
    
    # 交易所配置
    if 'exchange' in old_config or 'api_key' in old_config:
        new_config['exchange'] = {
            'name': old_config.get('exchange', 'binance'),
            'api_key': old_config.get('api_key', 'YOUR_API_KEY'),
            'api_secret': old_config.get('api_secret', 'YOUR_API_SECRET'),
            'testnet': False,
            'timeout': old_config.get('api', {}).get('exchange_timeout', 10),
            'enable_rate_limit': True,
            'proxy': old_config.get('proxy')
        }
    
    # 交易配置
    trading = {}
    if 'symbol' in old_config:
        trading['symbol'] = old_config['symbol']
    if 'check_interval' in old_config:
        trading['check_interval'] = old_config['check_interval']
    
    # 从trading节点获取
    if 'trading' in old_config:
        old_trading = old_config['trading']
        trading.update({
            'symbol': old_trading.get('symbol', 'BTC/USDT:USDT'),
            'timeframe': old_trading.get('timeframe', '15m'),
            'max_position_pct': old_trading.get('max_position_pct', 0.8),
            'min_position_pct': old_trading.get('min_position_pct', 0.1),
            'default_leverage': old_trading.get('default_leverage', 2),
            'min_confidence': old_trading.get('min_confidence', 60),
        })
    
    if trading:
        new_config['trading'] = trading
    
    # AI配置
    if 'ai' in old_config:
        old_ai = old_config['ai']
        new_config['ai'] = {
            'enabled': old_ai.get('enabled', True),
            'provider': 'deepseek',
            'api_key': old_ai.get('deepseek_api_key', 'YOUR_DEEPSEEK_API_KEY'),
            'api_base_url': 'https://api.deepseek.com',
            'model': 'deepseek-chat',
            'timeout': old_config.get('api', {}).get('deepseek_timeout', 30),
            'max_retries': old_config.get('api', {}).get('max_retries', 3),
            'ai_weight': old_ai.get('ai_weight', 0.6),
            'technical_weight': old_ai.get('technical_weight', 0.4),
        }
    
    # 风险管理配置
    if 'risk_management' in old_config:
        old_risk = old_config['risk_management']
        new_config['risk_management'] = {
            'base_risk_pct': old_risk.get('base_risk_pct', 0.01),
            'max_risk_pct': old_risk.get('max_risk_pct', 0.02),
            'max_position_per_strategy': old_risk.get('max_position_per_strategy', 0.5),
            'max_total_risk': old_risk.get('max_total_risk', 0.02),
            'min_account_balance': old_risk.get('min_account_balance', 100),
            'min_risk_reward_ratio': old_risk.get('min_risk_reward_ratio', 1.5),
            'trailing_stop_activation': old_risk.get('trailing_stop_activation', 0.5),
            'trailing_stop_distance': old_risk.get('trailing_stop_distance', 0.3),
        }
    
    # 策略调度器配置
    if 'scheduler' in old_config:
        old_scheduler = old_config['scheduler']
        new_config['scheduler'] = {
            'min_switch_interval_hours': old_scheduler.get('min_switch_interval_hours', 6),
            'min_confidence_for_switch': old_scheduler.get('min_confidence_for_switch', 60),
            'use_ai': old_scheduler.get('use_ai', True),
            'enable_auto_switch': True,
        }
    
    # 策略配置
    if 'strategies' in old_config:
        old_strategies = old_config['strategies']
        new_strategies = {}
        
        # 网格策略
        if 'grid' in old_strategies:
            old_grid = old_strategies['grid']
            new_strategies['grid'] = {
                'enabled': old_grid.get('enabled', True),
                'grid_count': old_grid.get('grid_count', 10),
                'grid_spacing_pct': 0.01,
                'risk_per_grid': old_grid.get('risk_per_grid', 0.003),
                'price_range_pct': 0.1,
            }
        
        # 趋势策略
        if 'trend' in old_strategies:
            old_trend = old_strategies['trend']
            new_strategies['trend_following'] = {
                'enabled': old_trend.get('enabled', True),
                'donchian_entry_period': old_trend.get('donchian_entry_period', 20),
                'donchian_exit_period': old_trend.get('donchian_exit_period', 10),
                'ema_fast': 12,
                'ema_slow': 26,
                'adx_period': 14,
                'adx_threshold': old_trend.get('adx_threshold', 25),
                'max_pyramid_adds': old_trend.get('max_pyramid_adds', 3),
                'pyramid_interval_atr': old_trend.get('pyramid_interval_atr', 0.5),
                'risk_per_trade': old_trend.get('risk_per_trade', 0.01),
            }
        
        # 均值回归策略
        if 'mean_reversion' in old_strategies:
            old_mr = old_strategies['mean_reversion']
            new_strategies['mean_reversion'] = {
                'enabled': old_mr.get('enabled', False),
                'rsi_oversold': old_mr.get('rsi_oversold', 30),
                'rsi_overbought': old_mr.get('rsi_overbought', 70),
                'bb_period': 20,
                'bb_std': old_mr.get('bb_std', 2.0),
                'atr_period': 14,
            }
        
        new_config['strategies'] = new_strategies
    
    # 技术指标配置
    if 'indicators' in old_config:
        old_indicators = old_config['indicators']
        new_config['indicators'] = {
            'atr_period': old_indicators.get('atr_period', 14),
            'rsi_period': old_indicators.get('rsi_period', 14),
            'macd_fast': old_indicators.get('macd_fast', 12),
            'macd_slow': old_indicators.get('macd_slow', 26),
            'macd_signal': old_indicators.get('macd_signal', 9),
            'bb_period': old_indicators.get('bb_period', 20),
            'bb_std': old_indicators.get('bb_std', 2),
            'ema_periods': [12, 26, 50, 200],
            'adx_period': 14,
        }
    
    # API配置
    if 'api' in old_config:
        old_api = old_config['api']
        new_config['api'] = {
            'deepseek_timeout': old_api.get('deepseek_timeout', 30),
            'exchange_timeout': old_api.get('exchange_timeout', 10),
            'sentiment_api_timeout': old_api.get('sentiment_api_timeout', 10),
            'max_retries': old_api.get('max_retries', 3),
            'retry_delay': 1,
        }
    
    # 性能配置
    if 'performance' in old_config:
        old_perf = old_config['performance']
        new_config['performance'] = {
            'enable_cache': old_perf.get('enable_cache', True),
            'cache_ttl': old_perf.get('cache_ttl', 60),
            'use_async_api': old_perf.get('use_async_api', False),
            'dashboard_update_interval': old_perf.get('dashboard_update_interval', 5),
            'max_workers': 4,
        }
    
    # 日志配置
    if 'logging' in old_config:
        old_logging = old_config['logging']
        new_config['logging'] = {
            'level': old_logging.get('level', old_logging.get('log_level', 'INFO')),
            'console_level': old_logging.get('console_level', 'INFO'),
            'file_level': old_logging.get('file_level', 'DEBUG'),
            'log_dir': 'logs',
            'rotation': old_logging.get('rotation', '00:00'),
            'retention': old_logging.get('retention', '30 days'),
            'format': '{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}',
            'backtrace': True,
            'diagnose': True,
        }
    
    # 添加新功能的默认配置
    new_config['notifications'] = {
        'enabled': False,
        'dingding': {
            'enabled': False,
            'webhook_url': '${DINGDING_WEBHOOK:}',
            'secret': '${DINGDING_SECRET:}',
        },
        'telegram': {
            'enabled': False,
            'bot_token': '${TELEGRAM_BOT_TOKEN:}',
            'chat_id': '${TELEGRAM_CHAT_ID:}',
        }
    }
    
    new_config['database'] = {
        'enabled': False,
        'type': 'sqlite',
        'path': 'data/trading.db',
    }
    
    new_config['web'] = {
        'enabled': True,
        'host': '0.0.0.0',
        'port': 8050,
        'debug': False,
        'auth_required': False,
    }
    
    new_config['backtest'] = {
        'initial_capital': 10000,
        'commission_rate': 0.001,
        'slippage_rate': 0.0005,
        'enable_margin': True,
        'enable_short': True,
    }
    
    new_config['development'] = {
        'debug_mode': False,
        'mock_exchange': False,
        'save_signals': True,
        'save_trades': True,
    }
    
    return new_config


def save_yaml_config(config: Dict, yaml_path: Path):
    """保存为YAML配置文件"""
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(yaml_path, 'w', encoding='utf-8') as f:
        # 添加文件头注释
        f.write("# Headache Trade 配置文件\n")
        f.write("# 从JSON配置自动迁移生成\n\n")
        
        yaml.dump(config, f, default_flow_style=False, 
                 allow_unicode=True, sort_keys=False, indent=2)
    
    print(f"[成功] YAML配置已保存: {yaml_path}")


def main():
    parser = argparse.ArgumentParser(description='配置迁移工具')
    parser.add_argument('input', help='输入JSON配置文件路径')
    parser.add_argument('-o', '--output', help='输出YAML配置文件路径')
    parser.add_argument('--backup', action='store_true', help='备份原配置文件')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"[错误] 配置文件不存在: {input_path}")
        return 1
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.yaml')
    
    # 备份原文件
    if args.backup:
        backup_path = input_path.with_suffix('.json.bak')
        import shutil
        shutil.copy2(input_path, backup_path)
        print(f"[备份] 已备份原配置: {backup_path}")
    
    # 加载旧配置
    print(f"[读取配置] {input_path}")
    old_config = load_json_config(input_path)
    
    # 迁移配置
    print("[迁移中] 转换配置结构...")
    new_config = migrate_config(old_config)
    
    # 保存新配置
    save_yaml_config(new_config, output_path)
    
    print(f"\n[成功] 配置迁移完成!")
    print(f"   输入: {input_path}")
    print(f"   输出: {output_path}")
    print(f"\n[提示] 请检查并更新以下配置项:")
    print("   - exchange.api_key")
    print("   - exchange.api_secret")
    print("   - ai.api_key")
    print("   - notifications.*")
    
    return 0


if __name__ == '__main__':
    exit(main())
