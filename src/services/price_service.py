import ccxt
from typing import List, Dict


class PriceService:
    def __init__(self) -> None:
       self.exchange = ccxt.okx()

    def get_realtime_crypto_prices(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        try:
            prices = {}
            for symbol in symbols:
                ticker = self.exchange.fetch_ticker(symbol)
                prices[symbol] = {
                    "price": ticker["last"],
                    "change": ticker["percentage"] if ticker["percentage"] else 0,
                }
            print(prices)
            return prices
        except Exception as e:
            print(f"❌ 获取实时价格失败: {e}")
            return {}