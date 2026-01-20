#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Flask应用入口
"""
import threading
import time
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from dashboard.config import (
    FLASK_SECRET_KEY,
    FLASK_HOST,
    FLASK_PORT,
    UPDATE_INTERVAL_SECONDS,
    UPDATE_ERROR_RETRY_SECONDS
)
from dashboard.services.dashboard_service import update_dashboard_data
from dashboard.routes import (
    dashboard_routes,
    config_routes,
    backtest_routes,
    log_routes,
    auth_routes
)

# 创建Flask应用
app = Flask(__name__)
CORS(app)
app.secret_key = FLASK_SECRET_KEY

# 注册路由蓝图
app.register_blueprint(dashboard_routes.bp)
app.register_blueprint(config_routes.bp)
app.register_blueprint(backtest_routes.bp)
app.register_blueprint(log_routes.bp)
app.register_blueprint(auth_routes.bp)


@app.route('/')
def index():
    """主页面 - 简单健康检查或重定向提示"""
    return jsonify({
        'service': 'Headache Trade Dashboard API',
        'status': 'ok',
        'endpoints': [
            '/api/dashboard',
            '/api/positions',
            '/api/trades',
            '/api/signals',
            '/api/chart-history'
        ],
    })


def background_updater():
    """后台数据更新线程"""
    while True:
        try:
            print(f"🔄 后台更新数据... {datetime.now().strftime('%H:%M:%S')}")
            update_dashboard_data()
            print(f"✅ 数据更新完成")
            time.sleep(UPDATE_INTERVAL_SECONDS)
        except Exception as e:
            print(f"❌ 后台更新错误: {e}")
            time.sleep(UPDATE_ERROR_RETRY_SECONDS)


if __name__ == '__main__':
    print("🚀 Alpha Arena 交易仪表板启动中...")
    print("📊 访问地址: http://localhost:{}".format(FLASK_PORT))
    print("📖 注意：Dashboard 现在是只读模式，仅用于展示交易机器人数据")
    
    # 启动后台更新线程
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    print("✅ 后台更新线程已启动")
    
    # 关闭debug模式避免重启导致线程丢失
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
