#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户需要先配置 API 密钥才能访问 Arena 界面
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import pandas as pd
from dotenv import load_dotenv
import fcntl

app = Flask(__name__)
CORS(app)
app.secret_key = 'crypto_deepseek_secret_key_2024'

# 全局变量存储用户配置
user_config = {}
DASHBOARD_DATA_FILE = '/root/crypto_deepseek/data/dashboard_data.json'


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
            'status': 'active',
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    },
    'crypto_prices': {},
    'performance_history': [],
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
    """主页面 - 直接显示arena界面"""
    return render_template('arena.html')

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
                'overall': technical_data.get('trend', '震荡整理')
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