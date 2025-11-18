"""
Web Dashboard
基于 Flask 的实时交易监控面板
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import json
from datetime import datetime
from typing import Optional

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading_bot_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局监控面板实例
monitor = None
bot_status = {
    'running': False,
    'start_time': None,
    'current_strategy': None,
    'market_state': None
}


def init_dashboard(performance_monitor):
    """初始化仪表板"""
    global monitor
    monitor = performance_monitor


@app.route('/')
def index():
    """主页"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """获取系统状态"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    data = monitor.get_dashboard_data()
    data['bot_status'] = bot_status
    
    return jsonify(data)


@app.route('/api/trades')
def api_trades():
    """获取交易历史"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    limit = request.args.get('limit', 50, type=int)
    trades = list(monitor.trade_history)[-limit:]
    
    return jsonify({
        'trades': trades,
        'total': len(monitor.trade_history)
    })


@app.route('/api/equity')
def api_equity():
    """获取权益曲线"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    limit = request.args.get('limit', 200, type=int)
    equity = list(monitor.equity_history)[-limit:]
    
    return jsonify({
        'equity_curve': equity
    })


@app.route('/api/strategies')
def api_strategies():
    """获取策略表现"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    data = monitor.get_dashboard_data()
    
    return jsonify({
        'strategies': data['strategy_performance']
    })


@app.route('/api/alerts')
def api_alerts():
    """获取警告信息"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    limit = request.args.get('limit', 20, type=int)
    alerts = list(monitor.alerts)[-limit:]
    
    return jsonify({
        'alerts': alerts,
        'total': len(monitor.alerts)
    })


@app.route('/api/risk')
def api_risk():
    """获取风险检查"""
    if monitor is None:
        return jsonify({'error': 'Monitor not initialized'}), 503
    
    risk_check = monitor.check_risk_limits()
    
    return jsonify(risk_check)


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print('Client connected')
    emit('status', {'message': 'Connected to trading bot'})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print('Client disconnected')


def broadcast_update(event_type: str, data: dict):
    """广播更新到所有客户端"""
    socketio.emit(event_type, data)


def broadcast_trade(trade: dict):
    """广播新交易"""
    broadcast_update('new_trade', trade)


def broadcast_equity(equity: dict):
    """广播权益更新"""
    broadcast_update('equity_update', equity)


def broadcast_alert(alert: dict):
    """广播警告"""
    broadcast_update('new_alert', alert)


def broadcast_strategy_switch(switch: dict):
    """广播策略切换"""
    broadcast_update('strategy_switch', switch)


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """运行 Dashboard 服务器"""
    print(f"\n{'='*60}")
    print(f"🌐 Web Dashboard 启动")
    print(f"{'='*60}")
    print(f"访问地址: http://localhost:{port}")
    print(f"局域网访问: http://<your-ip>:{port}")
    print(f"{'='*60}\n")
    
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def run_dashboard_background(host='0.0.0.0', port=5000):
    """在后台线程运行 Dashboard"""
    thread = threading.Thread(
        target=run_dashboard,
        args=(host, port, False),
        daemon=True
    )
    thread.start()
    return thread


class DashboardConnector:
    """Dashboard 连接器 - 供交易机器人使用"""
    
    def __init__(self, performance_monitor, host='0.0.0.0', port=5000):
        self.monitor = performance_monitor
        self.host = host
        self.port = port
        self.thread = None
        
        # 初始化全局 monitor
        init_dashboard(performance_monitor)
    
    def start(self):
        """启动 Dashboard"""
        self.thread = run_dashboard_background(self.host, self.port)
        print(f"✅ Dashboard 已在后台启动 (http://localhost:{self.port})")
    
    def update_bot_status(self, running: bool, strategy: str = None, market_state: str = None):
        """更新机器人状态"""
        global bot_status
        
        bot_status['running'] = running
        if running and bot_status['start_time'] is None:
            bot_status['start_time'] = datetime.now()
        if strategy:
            bot_status['current_strategy'] = strategy
        if market_state:
            bot_status['market_state'] = market_state
        
        broadcast_update('bot_status', bot_status)
    
    def notify_trade(self, trade: dict):
        """通知新交易"""
        broadcast_trade(trade)
    
    def notify_equity(self, equity: float):
        """通知权益更新"""
        broadcast_equity({
            'timestamp': datetime.now(),
            'equity': equity
        })
    
    def notify_alert(self, level: str, message: str):
        """通知警告"""
        broadcast_alert({
            'timestamp': datetime.now(),
            'level': level,
            'message': message
        })
    
    def notify_strategy_switch(self, from_strategy: str, to_strategy: str, reason: str):
        """通知策略切换"""
        broadcast_strategy_switch({
            'timestamp': datetime.now(),
            'from': from_strategy,
            'to': to_strategy,
            'reason': reason
        })


if __name__ == '__main__':
    # 测试运行
    from monitoring_panel import PerformanceMonitor
    
    test_monitor = PerformanceMonitor()
    init_dashboard(test_monitor)
    
    run_dashboard(debug=True)
