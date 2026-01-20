"""
回测相关路由
"""
import threading
from flask import Blueprint, jsonify, request
from dashboard.services.backtest_service import backtest_manager

bp = Blueprint('backtest', __name__)


@bp.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """运行回测"""
    try:
        body = request.get_json() or {}
        job_id = backtest_manager.create_job(body)
        
        # 在后台线程中执行任务
        t = threading.Thread(
            target=backtest_manager.run_job,
            args=(job_id, body),
            daemon=True
        )
        t.start()
        
        # 返回任务信息
        job = backtest_manager.get_job(job_id)
        return jsonify(job)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/backtest/status/<job_id>', methods=['GET'])
def backtest_status(job_id):
    """获取回测状态"""
    try:
        job = backtest_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'job not found'}), 404
        return jsonify(job)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
