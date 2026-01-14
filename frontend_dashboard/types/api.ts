export interface DeepSeekModelData {
  name: string;
  icon: string;
  color: string;
  account_value: number;
  change_percent: number;
  positions: Position[];
  trades: Trade[];
  trade_count: number;
  status: 'active' | 'paused' | 'error';
  last_update: string;
}

export interface CryptoPrice {
  price: number;
  change: number;
}

export interface DashboardResponse {
  models: Record<string, DeepSeekModelData>;
  crypto_prices: Record<string, CryptoPrice>;
  performance_history: any[]; // Define more specifically if needed
  chart_history: AccountEquityPoint[];
  last_update: string;
}

export interface AccountEquityPoint {
  timestamp: string;    // ISO string
  equity: number;       // Account equity
}

export interface TradeSignal {
  id: string;
  symbol: string;       // e.g., BTCUSDT-PERP
  side: 'long' | 'short';
  entry_price: number;
  stop_loss?: number;
  take_profit?: number;
  size: number;
  timestamp: string;
  status: 'open' | 'closed' | 'cancelled';
}

export interface Position {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  entry_price: number;
  leverage: number;
  size: number;
  unrealized_pnl: number;
  liquidation_price?: number;
  timestamp: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  size: number;
  pnl: number;
  opened_at: string;
  closed_at: string;
}

export interface KlinePoint {
  timestamp: string; // or number (unix)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
