#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户需要先配置 API 密钥才能访问 Arena 界面
"""

import os
import json
import time
import threading
import uuid
import subprocess
import sys
import multiprocessing
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Response
from flask_cors import CORS
import pandas as pd
from dotenv import load_dotenv
import fcntl

from trading_bots import config as bot_config

app = Flask(__name__)
CORS(app)
app.secret_key = 'crypto_deepseek_secret_key_2024'

# 全局变量存储用户配置
user_config = {}

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DATA_FILE = os.path.join(PROJECT_ROOT, 'data/dashboard_data.json')
CHART_HISTORY_FILE = os.path.join(PROJECT_ROOT, 'data/chart_history.json')

CONFIG_BACKUP_DIR = Path(PROJECT_ROOT) / 'data' / 'backtest' / 'configs'
CURRENT_CONFIG_FILE = CONFIG_BACKUP_DIR / 'current_trading_params.json'
LOG_DIR = Path(PROJECT_ROOT) / 'logs'
LOG_FILES = {
    'bot': LOG_DIR / 'bot.log',
    'dashboard': LOG_DIR / 'dashboard.log',
    'commander': LOG_DIR / 'commander.log',
    'backtest': LOG_DIR / 'backtest.log',
}

backtest_jobs = {}
backtest_jobs_lock = threading.Lock()


def load_dashboard_data_from_file():
    """从JSON文件读取Dashboard数据"""
    try:
        if not os.path.exists(DASHBOARD_DATA_FILE):
            print("⚠️ Dashboard数据文件不存在，使用默认数据")
            return None
        
        with open(DASHBOARD_DATA_FILE, 'r', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享锁
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
        
        return data
    except Exception as e:
        print(f"❌ 读取Dashboard数据失败: {e}")
        return None


def load_chart_history_from_file():
    """从JSON文件读取图表历史数据"""
    try:
        if not os.path.exists(CHART_HISTORY_FILE):
            print("⚠️ 图表历史文件不存在，创建新文件")
            return []
        
        with open(CHART_HISTORY_FILE, 'r', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享锁
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
        
        return data.get('chart_points', [])
    except Exception as e:
        print(f"❌ 读取图表历史失败: {e}")
        return []


def save_chart_history_to_file(chart_points):
    """保存图表历史数据到JSON文件"""
    try:
        os.makedirs(os.path.dirname(CHART_HISTORY_FILE), exist_ok=True)
        
        # 确保数据按时间顺序排列（旧到新）
        sorted_points = sorted(chart_points, key=lambda x: x['timestamp'])
        
        data = {
            'chart_points': sorted_points,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_points': len(sorted_points)
        }
        
        with open(CHART_HISTORY_FILE, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            json.dump(data, f, ensure_ascii=False, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
        
        print(f"✅ 图表历史已保存: {len(sorted_points)} 个数据点 (已按时间排序)")
    except Exception as e:
        print(f"❌ 保存图表历史失败: {e}")


def validate_api_keys(config):
    """验证API密钥有效性（仅验证格式，不用于交易）"""
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


def serialize_trading_params():
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


def load_trading_params():
    if CURRENT_CONFIG_FILE.exists():
        try:
            with CURRENT_CONFIG_FILE.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as exc:
            print(f"⚠️ 读取当前配置失败，使用默认: {exc}")
    return serialize_trading_params()


def backup_trading_params(snapshot=None):
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    payload = snapshot or load_trading_params()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = CONFIG_BACKUP_DIR / f"trading_params_{ts}.json"
    with backup_path.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return backup_path


def save_trading_params(new_params):
    backup_trading_params()
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with CURRENT_CONFIG_FILE.open('w', encoding='utf-8') as f:
        payload = {**new_params, 'updated_at': datetime.utcnow().isoformat() + 'Z'}
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def list_config_history():
    entries = []
    if not CONFIG_BACKUP_DIR.exists():
        return entries
    for p in CONFIG_BACKUP_DIR.glob('trading_params_*.json'):
        entries.append({
            'name': p.name,
            'path': str(p.relative_to(PROJECT_ROOT)),
            'timestamp': p.stat().st_mtime,
            'size': p.stat().st_size,
        })
    entries.sort(key=lambda x: x['timestamp'], reverse=True)
    for item in entries:
        item['timestamp'] = datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
    return entries


def rollback_config(name: str):
    target = CONFIG_BACKUP_DIR / name
    if not target.exists():
        raise FileNotFoundError(f"未找到备份: {name}")
    with target.open('r', encoding='utf-8') as f:
        payload = json.load(f)
    with CURRENT_CONFIG_FILE.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def tail_log(path: Path, limit: int = 200):
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-limit:]


def log_stream_generator(path: Path, log_type: str, poll_seconds: float = 1.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                payload = json.dumps({
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'level': 'INFO',
                    'source': log_type,
                    'message': line.strip(),
                })
                yield f"data: {payload}\n\n"
            else:
                time.sleep(poll_seconds)


def run_backtest_job(job_id: str, payload: dict):
    with backtest_jobs_lock:
        backtest_jobs[job_id] = {
            'id': job_id,
            'status': 'running',
            'started_at': datetime.utcnow().isoformat() + 'Z',
            'ai_feedback': bool(payload.get('ai_feedback', False)),
            'config_name': payload.get('config') or 'default',
        }

    log_path = LOG_FILES.get('backtest')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, 'scripts', 'backtest_runner.py'), '--days', str(payload.get('days', 30))]
    if payload.get('config'):
        cmd += ['--config', str(payload['config'])]

    env = os.environ.copy()
    if payload.get('initial_balance'):
        env['BACKTEST_INITIAL_BALANCE'] = str(payload['initial_balance'])
    if payload.get('leverage'):
        env['BACKTEST_LEVERAGE'] = str(payload['leverage'])

    try:
        with log_path.open('a', encoding='utf-8') as lf:
            lf.write(f"\n[{datetime.utcnow().isoformat()}Z] job {job_id} start cmd: {' '.join(cmd)}\n")
            proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, stdout=lf, stderr=lf, text=True)
        status = 'completed' if proc.returncode == 0 else 'failed'
        with backtest_jobs_lock:
            backtest_jobs[job_id] = {
                **backtest_jobs.get(job_id, {}),
                'status': status,
                'finished_at': datetime.utcnow().isoformat() + 'Z',
                'message': f'return code {proc.returncode}',
            }
    except Exception as exc:
        with backtest_jobs_lock:
            backtest_jobs[job_id] = {
                **backtest_jobs.get(job_id, {}),
                'status': 'failed',
                'finished_at': datetime.utcnow().isoformat() + 'Z',
                'message': str(exc),
            }


# 全局数据存储
dashboard_data = {
    'models': {
        'DeepSeek Chat V3.1': {
            'name': 'DeepSeek Chat V3.1',
            'icon': '🐋',
            'color': '#3B82F6',
            'account_value': 10000.0,
            'change_percent': 0.0,
            'positions': [],
            'trades': [],
            'trade_count': 0,
            'status': 'active',
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    },
    'crypto_prices': {},
    'performance_history': [],
    'chart_history': [],  # 新增图表历史数据
    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}

# 已移除交易所初始化函数 - Dashboard现在是只读模式

# 已移除交易所初始化函数 - Dashboard现在是只读模式

def get_crypto_prices():
    """从文件获取加密货币价格"""
    data = load_dashboard_data_from_file()
    if data and 'crypto_prices' in data:
        return data['crypto_prices']
    return {}

def get_current_position():
    """从文件获取当前持仓"""
    data = load_dashboard_data_from_file()
    if data and 'position' in data:
        return data['position']
    return None

def calculate_model_performance():
    """从文件计算模型性能"""
    data = load_dashboard_data_from_file()
    if data and 'account' in data:
        account = data['account']
        position = data.get('position')
        
        return {
            'account_value': account['total_value'],
            'change_percent': account['change_percent'],
            'position': position,
            'balance': account['balance']
        }
    
    # 默认值
    return {
        'account_value': 10000.0,
        'change_percent': 0.0,
        'position': None,
        'balance': 10000.0
    }

def fetch_realtime_crypto_prices():
    """直接从OKX获取实时加密货币价格 - 独立于交易机器人"""
    try:
        import ccxt
        exchange = ccxt.okx()
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'XRP/USDT']
        prices = {}
        
        for symbol in symbols:
            try:
                ticker = exchange.fetch_ticker(symbol)
                base_symbol = symbol.split('/')[0]
                prices[base_symbol] = {
                    'price': ticker['last'],
                    'change': ticker['percentage'] if ticker['percentage'] else 0
                }
            except Exception as e:
                print(f"⚠️ 获取{symbol}价格失败: {e}")
        
        return prices
    except Exception as e:
        print(f"❌ 获取实时价格失败: {e}")
        return {}

def update_dashboard_data():
    """从文件更新仪表板数据 + 独立获取实时价格"""
    global dashboard_data
    
    try:
        # 1. 独立获取实时加密货币价格（不依赖交易机器人）
        realtime_prices = fetch_realtime_crypto_prices()
        if realtime_prices:
            dashboard_data['crypto_prices'] = realtime_prices
            print(f"✅ 实时价格更新: BTC=${realtime_prices.get('BTC', {}).get('price', 0):.2f}")
        
        # 2. 从文件读取交易机器人的其他数据（账户、持仓、信号等）
        file_data = load_dashboard_data_from_file()
        if not file_data:
            print("⚠️ 无法读取Dashboard数据文件，仅使用实时价格")
            return
        
        # 更新模型性能
        if 'account' in file_data:
            account = file_data['account']
            model_data = dashboard_data['models']['DeepSeek Chat V3.1']
            
            model_data['account_value'] = account['total_value']
            model_data['change_percent'] = account['change_percent']
            model_data['last_update'] = file_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # 更新持仓信息
            if file_data.get('position'):
                model_data['positions'] = [file_data['position']]
            else:
                model_data['positions'] = []
            
            # 更新交易信息
            model_data['trades'] = file_data.get('trades', [])
            model_data['trade_count'] = len(file_data.get('trades', []))
        
        # 3. 加载图表历史数据
        chart_history = load_chart_history_from_file()
        dashboard_data['chart_history'] = chart_history
        
        # 添加性能历史记录
        dashboard_data['performance_history'].append({
            'timestamp': file_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'account_value': file_data.get('account', {}).get('total_value', 10000.0),
            'change_percent': file_data.get('account', {}).get('change_percent', 0.0)
        })
        
        # 保持最近100条记录
        if len(dashboard_data['performance_history']) > 100:
            dashboard_data['performance_history'] = dashboard_data['performance_history'][-100:]
        
        dashboard_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        print(f"❌ 更新数据失败: {e}")

def background_updater():
    """后台数据更新线程"""
    while True:
        try:
            print(f"🔄 后台更新数据... {datetime.now().strftime('%H:%M:%S')}")
            update_dashboard_data()
            print(f"✅ 数据更新完成，crypto_prices: {len(dashboard_data.get('crypto_prices', {}))} 个币种")
            time.sleep(5)  # 改为每5秒更新一次，与前端同步
        except Exception as e:
            print(f"❌ 后台更新错误: {e}")
            time.sleep(10)

@app.route('/')
def index():
    """主页面 - 简单健康检查或重定向提示"""
    return jsonify({
        'service': 'Headache Trade Dashboard API',
        'status': 'ok',
        'endpoints': ['/api/dashboard', '/api/positions', '/api/trades', '/api/signals', '/api/chart-history'],
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录配置页面"""
    if request.method == 'POST':
        config = {
            'deepseek_api_key': request.form.get('deepseek_api_key'),
            'okx_api_key': request.form.get('okx_api_key'),
            'okx_secret': request.form.get('okx_secret'),
            'okx_password': request.form.get('okx_password'),
            'wallet_address': request.form.get('wallet_address')
        }
        
        # 验证配置
        if not all([config['deepseek_api_key'], config['okx_api_key'], config['okx_secret'], config['okx_password']]):
            return jsonify({'success': False, 'message': '请填写所有必需的 API 配置'})
        
        # 验证API密钥格式（不进行实际连接）
        if validate_api_keys(config):
            # 保存配置到会话
            session['logged_in'] = True
            session['config'] = config
            global user_config
            user_config = config
            
            return jsonify({'success': True, 'message': '配置成功！正在跳转到 Arena 界面...'})
        else:
            return jsonify({'success': False, 'message': 'API 配置格式验证失败，请检查您的密钥是否正确'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    global user_config
    user_config = {}
    return redirect(url_for('index'))

@app.route('/api/dashboard')
def get_dashboard_data():
    """获取仪表板数据"""
    # 移除登录检查，直接返回数据
    return jsonify(dashboard_data)

@app.route('/api/models')
def get_models():
    """获取模型数据"""
    # 移除登录检查，直接返回数据
    return jsonify(dashboard_data['models'])

@app.route('/api/crypto-prices')
def get_crypto_prices_api():
    """获取加密货币价格"""
    # 移除登录检查，直接返回数据
    return jsonify(dashboard_data['crypto_prices'])

@app.route('/api/performance-history')
def get_performance_history():
    """获取性能历史"""
    # 移除登录检查，直接返回数据
    return jsonify(dashboard_data['performance_history'])

@app.route('/api/positions')
def get_positions():
    """获取持仓信息"""
    # 移除登录检查，直接返回数据
    try:
        position = get_current_position()
        if position:
            return jsonify([position])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """获取交易历史 - 从dashboard_data.json读取"""
    try:
        data = load_dashboard_data_from_file()
        if data is None:
            return jsonify([])
        
        trades = data.get('trades', [])
        
        # 为前端添加symbol字段（如果没有）
        for trade in trades:
            if 'symbol' not in trade:
                trade['symbol'] = 'BTC/USDT'
        
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals')
def get_signals():
    """获取交易信号历史"""
    # 移除登录检查，直接返回数据
    try:
        data = load_dashboard_data_from_file()
        if data and 'signals' in data:
            return jsonify(data['signals'][-20:])  # 最近20个信号
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-history')
def get_chart_history():
    """获取图表历史数据"""
    try:
        chart_history = load_chart_history_from_file()
        return jsonify({
            'chart_points': chart_history,
            'total_points': len(chart_history),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/trading', methods=['GET', 'POST'])
def trading_config_api():
    try:
        if request.method == 'GET':
            return jsonify(load_trading_params())

        payload = request.get_json() or {}
        saved = save_trading_params(payload)
        return jsonify({'success': True, 'data': saved})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/history', methods=['GET'])
def trading_config_history():
    try:
        return jsonify(list_config_history())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/rollback', methods=['POST'])
def trading_config_rollback():
    try:
        body = request.get_json() or {}
        name = body.get('name')
        if not name:
            return jsonify({'error': 'name required'}), 400
        payload = rollback_config(name)
        return jsonify({'success': True, 'data': payload})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest/run', methods=['POST'])
def run_backtest_api():
    try:
        body = request.get_json() or {}
        job_id = str(uuid.uuid4())
        with backtest_jobs_lock:
            backtest_jobs[job_id] = {
                'id': job_id,
                'status': 'queued',
                'ai_feedback': bool(body.get('ai_feedback', False)),
                'config_name': body.get('config') or 'default',
            }
        t = threading.Thread(target=run_backtest_job, args=(job_id, body), daemon=True)
        t.start()
        with backtest_jobs_lock:
            return jsonify(backtest_jobs[job_id])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest/status/<job_id>', methods=['GET'])
def backtest_status(job_id):
    try:
        if job_id not in backtest_jobs:
            return jsonify({'error': 'job not found'}), 404
        with backtest_jobs_lock:
            return jsonify(backtest_jobs[job_id])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs_api():
    try:
        log_type = request.args.get('type', 'bot')
        limit = int(request.args.get('limit', '200'))
        path = LOG_FILES.get(log_type, LOG_FILES['bot'])
        lines = tail_log(path, limit)
        entries = []
        for line in lines:
            entries.append({
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': 'INFO',
                'source': log_type,
                'message': line.strip(),
            })
        return jsonify(entries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs/stream')
def stream_logs():
    log_type = request.args.get('type', 'bot')
    path = LOG_FILES.get(log_type, LOG_FILES['bot'])
    return Response(log_stream_generator(path, log_type), mimetype='text/event-stream')

@app.route('/api/save-chart-history', methods=['POST'])
def save_chart_history():
    """保存图表历史数据"""
    try:
        data = request.get_json()
        chart_points = data.get('chart_points', [])
        
        # 限制数据点数量，保持最近96个点（24小时历史）
        if len(chart_points) > 96:
            chart_points = chart_points[-96:]
        
        save_chart_history_to_file(chart_points)
        
        return jsonify({
            'success': True,
            'message': f'图表历史已保存，共{len(chart_points)}个数据点',
            'total_points': len(chart_points)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/technical-analysis')
def get_technical_analysis():
    """获取技术分析数据"""
    # 移除登录检查，直接返回数据
    try:
        data = load_dashboard_data_from_file()
        if not data:
            return jsonify({'error': '无法读取技术分析数据'}), 500
        
        # 从文件数据构建技术分析响应
        price_data = data.get('price_data', {})
        technical_data = data.get('technical_analysis', {})
        
        return jsonify({
            'price': price_data.get('price', 0),
            'timestamp': price_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'technical_data': {
                'rsi': technical_data.get('rsi', 50),
                'macd': technical_data.get('macd', 0),
                'sma_20': price_data.get('price', 0)  # 简化处理
            },
            'trend_analysis': {
                'overall': technical_data.get('trend', '震荡整理'),
                'trend_strength': technical_data.get('trend_strength', 'N/A'),
                'price_level': technical_data.get('price_level', 'N/A')
            },
            'levels_analysis': {}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Alpha Arena 交易仪表板启动中...")
    print("📊 访问地址: http://localhost:5001")
    print("📖 注意：Dashboard 现在是只读模式，仅用于展示交易机器人数据")
    
    # 启动后台更新线程
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    print("✅ 后台更新线程已启动")
    
    # 关闭debug模式避免重启导致线程丢失
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)