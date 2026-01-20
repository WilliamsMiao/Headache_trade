"""
允许dashboard作为模块运行: python -m dashboard
"""
import threading
from dashboard.app import app
from dashboard.services.dashboard_service import update_dashboard_data
from dashboard.config import (
    FLASK_HOST,
    FLASK_PORT,
    UPDATE_INTERVAL_SECONDS,
    UPDATE_ERROR_RETRY_SECONDS
)
import time
from datetime import datetime


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
