import {
  DashboardResponse,
  AccountEquityPoint,
  TradeSignal,
  Position,
  Trade,
  KlinePoint,
} from '../types/api';

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) {
    throw new Error(`API Error: ${res.statusText}`);
  }
  return res.json();
}

const normalizeSymbol = (symbol?: string) => {
  if (!symbol) return 'BTCUSDT-PERP';
  const cleaned = symbol.replace(/[:]/g, '').replace('/', '');
  if (cleaned.toUpperCase().includes('USDT') && !cleaned.includes('-')) {
    return `${cleaned.replace('USDTUSDT', 'USDT')}-PERP`;
  }
  return cleaned;
};

const normalizeSide = (side?: string): 'long' | 'short' => {
  const s = side?.toLowerCase() || '';
  if (s.includes('sell') || s.includes('short')) return 'short';
  return 'long';
};

const normalizeChartHistory = (payload: any): AccountEquityPoint[] => {
  const points = Array.isArray(payload)
    ? payload
    : payload?.chart_points || payload?.chart_history || [];

  return (points || [])
    .map((p: any, idx: number) => {
      const timestamp = p?.timestamp || p?.label || `point-${idx}`;
      const equity = Number(
        p?.equity ?? p?.value ?? p?.account_value ?? p?.balance ?? 0,
      );
      return { timestamp, equity };
    })
    .filter(p => p.timestamp);
};

const normalizePositions = (raw: any[]): Position[] =>
  (raw || []).map((p, idx) => ({
    id: p?.id || p?.position_id || p?.order_id || `pos-${idx}`,
    symbol: normalizeSymbol(p?.symbol),
    side: normalizeSide(p?.side),
    entry_price: Number(p?.entry_price ?? p?.price ?? 0),
    leverage: Number(p?.leverage ?? p?.current_leverage ?? 1),
    size: Number(p?.size ?? p?.amount ?? 0),
    unrealized_pnl: Number(p?.unrealized_pnl ?? p?.pnl ?? 0),
    liquidation_price: p?.liquidation_price ?? p?.liquidation ?? undefined,
    timestamp: p?.timestamp || p?.time || new Date().toISOString(),
  }));

const normalizeTrades = (raw: any[]): Trade[] => {
  const parseTs = (val: any, fallback: number) => {
    const ts = typeof val === 'number' ? val : Date.parse(val);
    return Number.isFinite(ts) ? ts : fallback;
  };

  const base = (raw || []).map((t, idx) => {
    const side = normalizeSide(t?.side);
    const entry = Number(t?.entry_price ?? t?.price ?? 0);
    const exitRaw = t?.exit_price ?? t?.close_price;
    const exit = exitRaw !== undefined ? Number(exitRaw) : entry;
    const size = Number(t?.size ?? t?.amount ?? 0);
    const ts = t?.timestamp || t?.closed_at || t?.opened_at || new Date().toISOString();
    const parsedTs = parseTs(ts, Date.now() + idx);

    return {
      id: t?.id || t?.trade_id || t?.order_id || `trade-${idx}`,
      symbol: normalizeSymbol(t?.symbol),
      side,
      entry_price: entry,
      exit_price: exit,
      size,
      pnl: Number.isFinite(Number(t?.pnl)) ? Number(t?.pnl) : null,
      opened_at: t?.opened_at || ts,
      closed_at: ts,
      _ts: parsedTs,
      _exitProvided: exitRaw !== undefined,
    } as any;
  });

  // Sort ascending by time for running PnL computation
  const sorted = base.sort((a, b) => a._ts - b._ts);

  let positionSize = 0; // positive: long, negative: short
  let avgPrice = 0;

  const withPnl = sorted.map(trade => {
    const isBuy = trade.side === 'long';
    let pnl = trade.pnl;
    let entryPrice = trade.entry_price;
    let exitPrice = trade.exit_price ?? trade.entry_price;

    // If backend already provides pnl or explicit exit, use it first
    if (pnl === null && trade._exitProvided) {
      const diff = exitPrice - entryPrice;
      pnl = (isBuy ? diff : -diff) * trade.size;
    }

    if (pnl === null) {
      const size = trade.size;

      if (positionSize === 0) {
        positionSize = isBuy ? size : -size;
        avgPrice = entryPrice;
        pnl = 0;
      } else if (positionSize > 0) {
        if (isBuy) {
          avgPrice = (avgPrice * positionSize + entryPrice * size) / (positionSize + size || 1);
          positionSize += size;
          pnl = 0;
        } else {
          const closeQty = Math.min(positionSize, size);
          entryPrice = avgPrice;
          exitPrice = trade.entry_price;
          pnl = (exitPrice - entryPrice) * closeQty;
          positionSize -= closeQty;

          if (size > closeQty) {
            const openQty = size - closeQty;
            positionSize = -openQty;
            avgPrice = trade.entry_price;
          } else if (positionSize === 0) {
            avgPrice = trade.entry_price;
          }
        }
      } else {
        // positionSize < 0 (short)
        if (!isBuy) {
          const absPos = Math.abs(positionSize);
          avgPrice = (avgPrice * absPos + entryPrice * size) / (absPos + size || 1);
          positionSize -= size;
          pnl = 0;
        } else {
          const closeQty = Math.min(Math.abs(positionSize), size);
          entryPrice = avgPrice;
          exitPrice = trade.entry_price;
          pnl = (entryPrice - exitPrice) * closeQty;
          positionSize += closeQty;

          if (size > closeQty) {
            const openQty = size - closeQty;
            positionSize = openQty;
            avgPrice = trade.entry_price;
          } else if (positionSize === 0) {
            avgPrice = trade.entry_price;
          }
        }
      }
    }

    return {
      id: trade.id,
      symbol: trade.symbol,
      side: trade.side,
      entry_price: Number(entryPrice),
      exit_price: Number(exitPrice),
      size: Number(trade.size),
      pnl: Number((pnl ?? 0).toFixed(2)),
      opened_at: trade.opened_at,
      closed_at: trade.closed_at,
    };
  });

  // Return latest first for UI tables
  return withPnl.sort((a, b) => new Date(b.closed_at).getTime() - new Date(a.closed_at).getTime());
};

const normalizeSignals = (raw: any[]): TradeSignal[] =>
  (raw || []).map((s, idx) => ({
    id: s?.id || s?.signal_id || `sig-${idx}`,
    symbol: normalizeSymbol(s?.symbol),
    side: normalizeSide(s?.side || s?.signal),
    entry_price: Number(s?.entry_price ?? s?.price ?? s?.take_profit ?? 0),
    stop_loss: typeof s?.stop_loss === 'number' ? s.stop_loss : undefined,
    take_profit: typeof s?.take_profit === 'number' ? s.take_profit : undefined,
    size: Number(s?.size ?? s?.amount ?? 0),
    timestamp: s?.timestamp || s?.time || new Date().toISOString(),
    status: (s?.status as TradeSignal['status']) || 'open',
  }));

const synthesizeKlinesFromEquity = (points: AccountEquityPoint[]): KlinePoint[] => {
  if (!points?.length) return [];

  return points.map((p, idx) => {
    const prev = idx > 0 ? points[idx - 1].equity : p.equity;
    const open = prev;
    const close = p.equity;
    const high = Math.max(open, close);
    const low = Math.min(open, close);

    return {
      timestamp: p.timestamp,
      open,
      high,
      low,
      close,
      volume: 0,
    };
  });
};

export const api = {
  getDashboard: async () => {
    const raw = await fetchJson<any>('/dashboard');
    const chart_history = normalizeChartHistory(raw?.chart_history);
    return { ...raw, chart_history } as DashboardResponse;
  },
  
  getChartHistory: async (interval: string = '1D') => {
    const raw = await fetchJson<any>(`/chart-history?interval=${interval}`);
    return normalizeChartHistory(raw);
  },
    
  getSignals: async () => {
    const raw = await fetchJson<any[]>('/signals');
    return normalizeSignals(raw);
  },
  
  getPositions: async () => {
    const raw = await fetchJson<any[]>('/positions');
    return normalizePositions(raw);
  },
  
  getTrades: async () => {
    const raw = await fetchJson<any[]>('/trades');
    return normalizeTrades(raw);
  },
  
  getKlines: async (symbol: string, interval: string) => {
    try {
      const live = await fetchJson<KlinePoint[] | any>(`/crypto-kline?symbol=${symbol}&interval=${interval}`);
      if (Array.isArray(live)) return live as KlinePoint[];
    } catch (err) {
      console.warn('Live kline fetch failed, falling back to equity history', err);
    }

    const equityHistory = await api.getChartHistory('ALL');
    return synthesizeKlinesFromEquity(equityHistory);
  },
};
