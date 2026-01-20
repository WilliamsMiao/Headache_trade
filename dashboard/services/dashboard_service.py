"""
Dashboard服务
负责聚合和更新仪表板数据
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
from dashboard.repositories.dashboard_repository import load_dashboard_data
from dashboard.repositories.chart_repository import load_chart_history
from dashboard.services.price_service import fetch_realtime_crypto_prices
from dashboard.config import PERFORMANCE_HISTORY_LIMIT


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
    'chart_history': [],
    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}


def get_dashboard_data() -> Dict[str, Any]:
    """
    获取完整的仪表板数据
    
    Returns:
        仪表板数据字典
    """
    return dashboard_data


def get_model_performance() -> Dict[str, Any]:
    """
    从文件计算模型性能
    
    Returns:
        模型性能数据
    """
    data = load_dashboard_data()
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


def get_current_position() -> Optional[Dict[str, Any]]:
    """
    从文件获取当前持仓
    
    Returns:
        持仓信息字典，如果没有持仓则返回None
    """
    data = load_dashboard_data()
    if data and 'position' in data:
        return data['position']
    return None


def get_trades() -> List[Dict[str, Any]]:
    """
    获取交易历史
    
    Returns:
        交易历史列表
    """
    data = load_dashboard_data()
    if data is None:
        return []
    
    trades = data.get('trades', [])
    
    # 为前端添加symbol字段（如果没有）
    for trade in trades:
        if 'symbol' not in trade:
            trade['symbol'] = 'BTC/USDT'
    
    return trades


def get_signals() -> List[Dict[str, Any]]:
    """
    获取交易信号历史
    
    Returns:
        信号历史列表（最近20个）
    """
    data = load_dashboard_data()
    if data and 'signals' in data:
        return data['signals'][-20:]
    return []


def get_technical_analysis() -> Dict[str, Any]:
    """
    获取技术分析数据
    
    Returns:
        技术分析数据字典
    """
    data = load_dashboard_data()
    if not data:
        return {
            'error': '无法读取技术分析数据'
        }
    
    # 从文件数据构建技术分析响应
    price_data = data.get('price_data', {})
    technical_data = data.get('technical_analysis', {})
    
    return {
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
    }


def update_dashboard_data() -> None:
    """
    从文件更新仪表板数据 + 独立获取实时价格
    这个函数会被后台线程定期调用
    """
    global dashboard_data
    
    try:
        # 1. 独立获取实时加密货币价格（不依赖交易机器人）
        realtime_prices = fetch_realtime_crypto_prices()
        if realtime_prices:
            dashboard_data['crypto_prices'] = realtime_prices
            print(f"✅ 实时价格更新: BTC=${realtime_prices.get('BTC', {}).get('price', 0):.2f}")
        
        # 2. 从文件读取交易机器人的其他数据（账户、持仓、信号等）
        file_data = load_dashboard_data()
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
        chart_history = load_chart_history()
        dashboard_data['chart_history'] = chart_history
        
        # 添加性能历史记录
        dashboard_data['performance_history'].append({
            'timestamp': file_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'account_value': file_data.get('account', {}).get('total_value', 10000.0),
            'change_percent': file_data.get('account', {}).get('change_percent', 0.0)
        })
        
        # 保持最近N条记录
        if len(dashboard_data['performance_history']) > PERFORMANCE_HISTORY_LIMIT:
            dashboard_data['performance_history'] = dashboard_data['performance_history'][-PERFORMANCE_HISTORY_LIMIT:]
        
        dashboard_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        print(f"❌ 更新数据失败: {e}")
