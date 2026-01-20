"""
Dashboard配置和常量
集中管理所有路径、文件路径和应用配置
"""
import os
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据文件路径
DASHBOARD_DATA_FILE = os.path.join(PROJECT_ROOT, 'data/dashboard_data.json')
CHART_HISTORY_FILE = os.path.join(PROJECT_ROOT, 'data/chart_history.json')

# 配置备份目录
CONFIG_BACKUP_DIR = Path(PROJECT_ROOT) / 'data' / 'backtest' / 'configs'
CURRENT_CONFIG_FILE = CONFIG_BACKUP_DIR / 'current_trading_params.json'

# 日志目录和文件
LOG_DIR = Path(PROJECT_ROOT) / 'logs'
LOG_FILES = {
    'bot': LOG_DIR / 'bot.log',
    'dashboard': LOG_DIR / 'dashboard.log',
    'commander': LOG_DIR / 'commander.log',
    'backtest': LOG_DIR / 'backtest.log',
}

# Flask应用配置
FLASK_SECRET_KEY = 'crypto_deepseek_secret_key_2024'
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5001

# 后台更新配置
UPDATE_INTERVAL_SECONDS = 5
UPDATE_ERROR_RETRY_SECONDS = 10

# 性能历史记录限制
PERFORMANCE_HISTORY_LIMIT = 100

# 图表历史数据点限制（24小时历史，每15分钟一个点）
CHART_HISTORY_LIMIT = 96
