"""
配置相关路由
"""
from flask import Blueprint, jsonify, request
from dashboard.services.config_service import load_trading_params, validate_api_keys
from dashboard.repositories.config_repository import (
    save_trading_params,
    list_config_history,
    rollback_config
)

bp = Blueprint('config', __name__)


@bp.route('/api/config/trading', methods=['GET', 'POST'])
def trading_config():
    """交易配置CRUD"""
    try:
        if request.method == 'GET':
            return jsonify(load_trading_params())
        
        payload = request.get_json() or {}
        saved = save_trading_params(payload)
        return jsonify({'success': True, 'data': saved})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/config/history', methods=['GET'])
def trading_config_history():
    """获取配置历史"""
    try:
        history = list_config_history()
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/config/rollback', methods=['POST'])
def trading_config_rollback():
    """回滚配置"""
    try:
        body = request.get_json() or {}
        name = body.get('name')
        if not name:
            return jsonify({'error': 'name required'}), 400
        
        payload = rollback_config(name)
        return jsonify({'success': True, 'data': payload})
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
