from flask import Flask, jsonify, Response
from flask_cors import CORS
from services import exchange_service
from services.price_service import PriceService
from services.exchange_service import ExchangeService
from services.account_service import AccountService
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/symbol-prices', methods=['GET'])
def get_symbol_prices() -> Response:
    price_service = PriceService()
    prices = price_service.get_realtime_crypto_prices(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'XRP/USDT'])
    return jsonify(prices)

@app.route('/api/positions', methods=['GET'])
def get_account_positions() -> Response:
    api_key = os.getenv("OKX_API_KEY")
    secret = os.getenv("OKX_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    account_service = AccountService(api_key, secret, passphrase, "okx")
    positions = account_service.get_account_positions()
    return jsonify(positions)

if __name__ == '__main__':
    print("NEW Flask API started")
    # 启用debug模式和热重载
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=True)
