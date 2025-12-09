import ccxt
from typing import Dict, List, Any, Optional, Union, TypedDict

class CryptoPrice(TypedDict):
    price: float
    change: Union[float, int]


class ExchangeService:
    def __init__(self, api_key: str, secret: str, exchange_name: str = "binance") -> None:
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class(
            {
                "apiKey": api_key,
                "secret": secret,
            }
        )

    def fetch_balance(self) -> Any:
        return self.exchange.fetch_balance()

    def get_realtime_crypto_prices(self, symbols: List[str]) -> Dict[str, CryptoPrice]:
        try:
            prices: Dict[str, CryptoPrice] = {}
            for symbol in symbols:
                ticker = self.exchange.fetch_ticker(symbol)
                prices[symbol] = {
                    "price": ticker["last"],
                    "change": ticker["percentage"] if ticker["percentage"] else 0,
                }
            return prices
        except Exception as e:
            print(f"❌ 获取实时价格失败: {e}")
            return {}

    def fetch_ticker(self, symbol: str) -> Any:
        return self.exchange.fetch_ticker(symbol)

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: Optional[float] = None) -> Any:
        return self.exchange.create_order(symbol, order_type, side, amount, price)
