"""
Dashboard相关路由
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from dashboard.services.dashboard_service import (
    get_dashboard_data,
    get_current_position,
    get_trades,
    get_signals,
    get_technical_analysis
)
from dashboard.repositories.chart_repository import load_chart_history, save_chart_history
from dashboard.config import CHART_HISTORY_LIMIT

bp = Blueprint('dashboard', __name__)


@bp.route('/api/dashboard')
def get_dashboard():
    """获取仪表板数据"""
    return jsonify(get_dashboard_data())


@bp.route('/api/models')
def get_models():
    """获取模型数据"""
    data = get_dashboard_data()
    return jsonify(data['models'])


@bp.route('/api/crypto-prices')
def get_crypto_prices():
    """获取加密货币价格"""
    data = get_dashboard_data()
    return jsonify(data['crypto_prices'])


@bp.route('/api/performance-history')
def get_performance_history():
    """获取性能历史"""
    data = get_dashboard_data()
    return jsonify(data['performance_history'])


@bp.route('/api/positions')
def get_positions():
    """获取持仓信息"""
    try:
        position = get_current_position()
        if position:
            return jsonify([position])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/trades')
def get_trades_route():
    """获取交易历史"""
    try:
        trades = get_trades()
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/signals')
def get_signals_route():
    """获取交易信号历史"""
    try:
        signals = get_signals()
        return jsonify(signals)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/chart-history')
def get_chart_history():
    """获取图表历史数据"""
    try:
        chart_history = load_chart_history()
        return jsonify({
            'chart_points': chart_history,
            'total_points': len(chart_history),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/save-chart-history', methods=['POST'])
def save_chart_history_route():
    """保存图表历史数据"""
    try:
        data = request.get_json()
        chart_points = data.get('chart_points', [])
        
        # 限制数据点数量，保持最近N个点
        if len(chart_points) > CHART_HISTORY_LIMIT:
            chart_points = chart_points[-CHART_HISTORY_LIMIT:]
        
        save_chart_history(chart_points)
        
        return jsonify({
            'success': True,
            'message': f'图表历史已保存，共{len(chart_points)}个数据点',
            'total_points': len(chart_points)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/technical-analysis')
def get_technical_analysis_route():
    """获取技术分析数据"""
    try:
        analysis = get_technical_analysis()
        if 'error' in analysis:
            return jsonify(analysis), 500
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
