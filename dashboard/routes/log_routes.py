"""
日志相关路由
"""
from flask import Blueprint, jsonify, request, Response
from dashboard.config import LOG_FILES
from dashboard.services.log_service import (
    tail_log,
    log_stream_generator,
    format_log_entries
)

bp = Blueprint('logs', __name__)


@bp.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    try:
        log_type = request.args.get('type', 'bot')
        limit = int(request.args.get('limit', '200'))
        path = LOG_FILES.get(log_type, LOG_FILES['bot'])
        lines = tail_log(path, limit)
        entries = format_log_entries(lines, log_type)
        return jsonify(entries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/logs/stream')
def stream_logs():
    """流式日志（Server-Sent Events）"""
    log_type = request.args.get('type', 'bot')
    path = LOG_FILES.get(log_type, LOG_FILES['bot'])
    return Response(
        log_stream_generator(path, log_type),
        mimetype='text/event-stream'
    )
