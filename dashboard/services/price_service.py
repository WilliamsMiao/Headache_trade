"""
价格服务
负责获取加密货币实时价格
"""
from typing import Dict, Any
from dashboard.repositories.dashboard_repository import load_dashboard_data


def fetch_realtime_crypto_prices() -> Dict[str, Any]:
    """
    直接从OKX获取实时加密货币价格 - 独立于交易机器人
    
    Returns:
        加密货币价格字典，格式: {symbol: {'price': float, 'change': float}}
    """
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


def get_crypto_prices() -> Dict[str, Any]:
    """
    从文件获取加密货币价格
    
    Returns:
        加密货币价格字典
    """
    data = load_dashboard_data()
    if data and 'crypto_prices' in data:
        return data['crypto_prices']
    return {}
