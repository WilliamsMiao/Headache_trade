import ccxt
import os
from typing import TypedDict, Optional, Any, cast


class BalanceDict(TypedDict):
    """Balance amounts for each currency."""
    pass  # Dynamic keys like 'BTC', 'ETH', etc. with float values

class AccountBalance(TypedDict):
    """Complete account balance structure from exchange."""
    free: dict[str, float]   # Available balances
    used: dict[str, float]   # Locked/used balances
    total: dict[str, float]  # Total balances (free + used)

class AccountPosition(TypedDict):
    """Individual account position with specific fields."""
    accAvgPx: float     # Account average price
    cashBal: float      # Cash balance
    ccy: str          # Currency
    totalPnl: float     # Total profit and loss
AccountPositions = list[AccountPosition]  # List of positions

class AccountService:
    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None, 
                 passphrase: Optional[str] = None, exchange_name: str = "okx"):
        # Use provided credentials or fall back to environment variables
        api_key = api_key or os.getenv("OKX_API_KEY") or os.getenv("API_KEY")
        secret = secret or os.getenv("OKX_SECRET") or os.getenv("API_SECRET")
        passphrase = passphrase or os.getenv("OKX_PASSPHRASE") or os.getenv("API_PASSPHRASE")
        
        exchange_config = {
            'apiKey': api_key,
            'secret': secret,
        }
        
        # Add passphrase for exchanges that require it (like OKX)
        if passphrase:
            exchange_config['password'] = passphrase
            
        self.exchange = getattr(ccxt, exchange_name)(exchange_config)

    def get_account_balance(self) -> AccountBalance:
        """
        Get complete account balance information from the exchange.
        
        Returns:
            AccountBalance: Structured balance with exact shape:
                {
                    'free': {'BTC': 1.0, 'USDT': 500.0},     # Available
                    'used': {'BTC': 0.25, 'USDT': 100.0},    # Locked
                    'total': {'BTC': 1.25, 'USDT': 600.0}    # Total
                }
        """
        # Cast external API response to our typed structure
        return cast(AccountBalance, self.exchange.fetch_balance())
    
    def get_account_positions(self) -> AccountPositions:
        """
        Get account positions with specific fields only.
        
        Returns:
            AccountPositions: List of positions with fields:
                [{
                    'accAvgPx': '43250.5',   # Account average price
                    'cashBal': '1000.50',    # Cash balance  
                    'ccy': 'USDT'            # Currency
                }, ...]
                Empty list [] if no positions or on error.
        """
        try:
            balance = self.exchange.fetch_balance()
            
            # Extract positions from OKX response structure
            if 'info' in balance and 'data' in balance['info'] and balance['info']['data']:
                details = balance['info']['data'][0].get('details', []) if isinstance(balance['info']['data'], list) else balance['info']['data'].get('details', [])
                
                positions = []
                for detail in details:
                    if float(detail.get('cashBal', '0')) > 0:  # Only positive balances
                        # Create typed dictionary - mypy will check required fields
                        position: AccountPosition = {
                            'accAvgPx': detail.get('accAvgPx', 0),
                            'cashBal': detail.get('cashBal', 0),
                            'ccy': detail.get('ccy', ''),
                            'totalPnl': detail.get('totalPnl', 0),
                        }
                        positions.append(position)
                return positions
            return []
        except Exception as e:
            print(f"❌ 获取账户持仓失败: {e}")
            return []
        
def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY")
    secret = os.getenv("OKX_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    
    account_service = AccountService(api_key, secret, passphrase, "okx")
    
    balance = account_service.get_account_balance()
    print("Account Balance:", balance)
    
    positions = account_service.get_account_positions()
    print("Account Positions:", positions)

if __name__ == "__main__":
    main()