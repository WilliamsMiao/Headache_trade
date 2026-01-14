import {
  DashboardResponse,
  AccountEquityPoint,
  TradeSignal,
  Position,
  Trade,
  KlinePoint,
} from '../types/api';

// Helpers for dynamic mock generation
const rand = (min: number, max: number) => Math.random() * (max - min) + min;
const pick = <T,>(arr: T[]) => arr[Math.floor(Math.random() * arr.length)];
const side = () => (Math.random() > 0.5 ? 'long' : 'short');

export const generateMockDashboard = (): DashboardResponse => {
  const account = 11000 + rand(-500, 1200);
  const change = rand(-4, 6);
  return {
    models: {
      'DeepSeek Chat V3.1': {
        name: 'DeepSeek Chat V3.1',
        icon: 'AI',
        color: '#3B82F6',
        account_value: Number(account.toFixed(2)),
        change_percent: Number(change.toFixed(2)),
        positions: [],
        trades: [],
        trade_count: Math.floor(rand(120, 200)),
        status: change >= 0 ? 'active' : 'paused',
        last_update: new Date().toISOString(),
      },
    },
    crypto_prices: {
      BTC: { price: Number((92000 + rand(-1200, 1400)).toFixed(2)), change: Number(rand(-3, 3).toFixed(2)) },
      ETH: { price: Number((3400 + rand(-120, 160)).toFixed(2)), change: Number(rand(-3, 3).toFixed(2)) },
      SOL: { price: Number((145 + rand(-8, 10)).toFixed(2)), change: Number(rand(-6, 6).toFixed(2)) },
      BNB: { price: Number((620 + rand(-25, 25)).toFixed(2)), change: Number(rand(-3, 3).toFixed(2)) },
      DOGE: { price: Number((0.12 + rand(-0.02, 0.025)).toFixed(4)), change: Number(rand(-5, 5).toFixed(2)) },
      XRP: { price: Number((0.65 + rand(-0.06, 0.08)).toFixed(4)), change: Number(rand(-5, 5).toFixed(2)) },
    },
    performance_history: [],
    chart_history: [],
    last_update: new Date().toISOString(),
  };
};

export const generateMockChartHistory = (days = 60): AccountEquityPoint[] => {
  return Array.from({ length: days }, (_, i) => {
    const base = 10000;
    const drift = i * rand(50, 120) * (Math.random() > 0.3 ? 1 : -0.5);
    const noise = rand(-250, 320);
    const date = new Date();
    date.setDate(date.getDate() - (days - 1 - i));
    return {
      timestamp: date.toISOString().split('T')[0],
      equity: Number((base + drift + noise).toFixed(2)),
    };
  });
};

export const generateMockPositions = (count = 3): Position[] => {
  const symbols = ['BTCUSDT-PERP', 'ETHUSDT-PERP', 'SOLUSDT-PERP', 'BNBUSDT-PERP'];
  return Array.from({ length: count }, (_, i) => {
    const s = pick(symbols);
    const leverage = Math.floor(rand(2, 8));
    const price = rand(80, 95) * (s.startsWith('BTC') ? 1000 : s.startsWith('ETH') ? 50 : 1);
    const size = Number(rand(0.1, 2.5).toFixed(3));
    const pnl = rand(-180, 240);
    return {
      id: `pos_${i}_${Date.now()}`,
      symbol: s,
      side: side(),
      entry_price: Number(price.toFixed(2)),
      leverage,
      size,
      unrealized_pnl: Number(pnl.toFixed(2)),
      liquidation_price: Number((price * (Math.random() > 0.5 ? 0.72 : 1.35)).toFixed(2)),
      timestamp: new Date().toISOString(),
    };
  });
};

export const generateMockTrades = (count = 20): Trade[] => {
  const symbols = ['BTCUSDT-PERP', 'ETHUSDT-PERP', 'SOLUSDT-PERP', 'BNBUSDT-PERP'];
  return Array.from({ length: count }, (_, i) => {
    const s = pick(symbols);
    const opened = new Date(Date.now() - (i + 1) * 45 * 60 * 1000);
    const closed = new Date(opened.getTime() + rand(5, 40) * 60 * 1000);
    const entry = rand(80, 95) * (s.startsWith('BTC') ? 1000 : s.startsWith('ETH') ? 50 : 1);
    const exit = entry + rand(-0.04, 0.05) * entry;
    return {
      id: `trade_${i}_${Date.now()}`,
      symbol: s,
      side: side(),
      entry_price: Number(entry.toFixed(2)),
      exit_price: Number(exit.toFixed(2)),
      size: Number(rand(0.05, 3.5).toFixed(3)),
      pnl: Number((exit - entry).toFixed(2)),
      opened_at: opened.toISOString(),
      closed_at: closed.toISOString(),
    };
  });
};

export const generateMockSignals = (count = 4): TradeSignal[] => {
  const symbols = ['BTCUSDT-PERP', 'ETHUSDT-PERP', 'SOLUSDT-PERP'];
  return Array.from({ length: count }, (_, i) => {
    const s = pick(symbols);
    const entry = rand(80, 95) * (s.startsWith('BTC') ? 1000 : s.startsWith('ETH') ? 50 : 1);
    const stop = entry * (1 - rand(0.01, 0.04));
    const tp = entry * (1 + rand(0.01, 0.06));
    return {
      id: `sig_${i}_${Date.now()}`,
      symbol: s,
      side: side(),
      entry_price: Number(entry.toFixed(2)),
      stop_loss: Number(stop.toFixed(2)),
      take_profit: Number(tp.toFixed(2)),
      size: Number(rand(0.05, 2).toFixed(2)),
      timestamp: new Date(Date.now() - i * 10 * 60 * 1000).toISOString(),
      status: Math.random() > 0.5 ? 'open' : 'closed',
    };
  });
};

export const generateMockKlines = (count: number = 100): KlinePoint[] => {
  const klines: KlinePoint[] = [];
  let price = 92000;
  const now = Date.now();
  for (let i = count; i > 0; i--) {
    const open = price;
    const change = (Math.random() - 0.5) * 200;
    const close = open + change;
    const high = Math.max(open, close) + Math.random() * 50;
    const low = Math.min(open, close) - Math.random() * 50;
    klines.push({
      timestamp: new Date(now - i * 15 * 60000).toISOString(), // 15m intervals
      open,
      high,
      low,
      close,
      volume: Math.random() * 100,
    });
    price = close;
  }
  return klines;
};
