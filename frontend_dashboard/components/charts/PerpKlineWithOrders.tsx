'use client';

import React, { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { KlinePoint, TradeSignal, Position } from '@/types/api';
import { PerpKlineWithOrdersSkeleton } from '@/components/dashboard/skeletons/PerpKlineWithOrdersSkeleton';

const SUPPORTED_SYMBOLS = ['BTCUSDT-PERP', 'ETHUSDT-PERP', 'SOLUSDT-PERP'];
const INTERVALS = ['1m', '5m', '15m', '1H', '4H'];

export default function PerpKlineWithOrders() {
  const [symbol, setSymbol] = useState('BTCUSDT-PERP');
  const [interval, setInterval] = useState('15m');

  // Parallel fetching
  const klineQuery = useQuery({
    queryKey: ['klines', symbol, interval],
    queryFn: () => api.getKlines(symbol, interval),
    refetchInterval: 60000,
  });

  const signalsQuery = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getSignals(),
    refetchInterval: 15000,
  });
  
  const positionsQuery = useQuery({
      queryKey: ['positions'],
      queryFn: () => api.getPositions(),
      refetchInterval: 15000,
  });

  if (klineQuery.isLoading) {
      // 骨架布局保持与真实组件一致，加载时占位不跳动
      return <PerpKlineWithOrdersSkeleton />;
  }

  // Filter signals/orders relevant to current symbol
  const activeSignals = signalsQuery.data?.filter(s => s.symbol === symbol) || [];
  const currentPosition = positionsQuery.data?.find(p => p.symbol === symbol);

  const getOption = (klines: KlinePoint[]) => {
    if (!klines || klines.length === 0) return {};

    // ECharts candle data format: [open, close, low, high]
    // Note: ECharts usually expects [open, close, low, high] (or similar, checking docs)
    // Actually [open, close, lowest, highest]
    const dates = klines.map(k => k.timestamp);
    const dataValues = klines.map(k => [k.open, k.close, k.low, k.high]);
    const volumes = klines.map((k, i) => [i, k.volume, k.open > k.close ? -1 : 1]);

    // Construct MarkPoints (Entries)
    const markPointData = activeSignals.map(sig => ({
        name: sig.side.toUpperCase(),
        coord: [sig.timestamp, sig.entry_price], // Assuming chart uses 'time' axis or we match timestamp
        // If axis is category (index based), we might need to find the index of the timestamp.
        // For simplicity, let's assume we use 'time' axis or find index mismatch.
        // If using category axis, we must find closest index.
        xAxis: sig.timestamp, 
        yAxis: sig.entry_price,
        value: sig.size,
        itemStyle: { color: sig.side === 'long' ? '#10b981' : '#ef4444' }
    }));
    
    // Construct MarkLines (SL/TP)
    const markLineData: any[] = [];
    
    // Add current position levels
    if (currentPosition) {
        markLineData.push({
            yAxis: currentPosition.entry_price,
            label: { formatter: 'Entry' },
            lineStyle: { color: '#fbbf24', type: 'dashed' } // Amber
        });
        if(currentPosition.liquidation_price) {
             markLineData.push({
                yAxis: currentPosition.liquidation_price,
                label: { formatter: 'Liq' },
                lineStyle: { color: '#ef4444', onClick: () => {} } // Red
            });           
        }
    }
    
    // Add active signal SL/TP
    activeSignals.forEach(sig => {
        if(sig.status === 'open') {
             if (sig.stop_loss) {
                markLineData.push({
                    yAxis: sig.stop_loss,
                    label: { formatter: 'SL' },
                    lineStyle: { color: '#ef4444' }
                });
            }
            if (sig.take_profit) {
                markLineData.push({
                    yAxis: sig.take_profit,
                    label: { formatter: 'TP' },
                    lineStyle: { color: '#10b981' }
                });
            }
        }
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      grid: [
        { left: 60, right: 16, height: '60%', top: '10%' },
        { left: 60, right: 16, top: '75%', height: '15%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { lineStyle: { color: '#475569' } },
          axisLabel: { show: false }, // Hide x-axis labels on main chart to avoid clutter if sync with vol
          splitLine: { show: false }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          axisLabel: { color: '#94a3b8' },
          axisLine: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
        { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: '2%', borderColor: '#334155' }
      ],
      series: [
        {
          name: symbol,
          type: 'candlestick',
          data: dataValues,
          itemStyle: {
            color: '#10b981', // Up color
            color0: '#ef4444', // Down color
            borderColor: '#10b981',
            borderColor0: '#ef4444'
          },
          markPoint: {
            data: markPointData,
            symbol: 'arrow',
            symbolSize: 20,
            symbolOffset: [0, -10],
            label: { show: false }
          },
          markLine: {
            symbol: ['none', 'none'],
            data: markLineData,
            label: { show: true, position: 'end', color: '#fff' }
          }
        },
        {
            name: 'Volume',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volumes.map(v => v[1]), // Just volume
            itemStyle: {
                color: (params: any) => {
                    return dataValues[params.dataIndex][0] < dataValues[params.dataIndex][1] 
                        ? '#10b981' : '#ef4444';
                }
            }
        }
      ]
    };
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 rounded-xl border border-slate-800 shadow-xl overflow-hidden">
      {/* Controls */}
      <div className="flex flex-wrap justify-between items-center p-4 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-4">
            <div className="relative">
                <select 
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="appearance-none bg-slate-800 text-slate-100 font-bold py-1.5 px-4 pr-8 rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    {SUPPORTED_SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                </div>
            </div>
            {currentPosition && (
                <div className={`text-xs px-2 py-1 rounded ${currentPosition.unrealized_pnl >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {currentPosition.side.toUpperCase()} PnL: {currentPosition.unrealized_pnl.toFixed(2)}
                </div>
            )}
        </div>
        
        <div className="flex gap-1 bg-slate-950 p-1 rounded-lg mt-2 sm:mt-0">
             {INTERVALS.map(int => (
                <button
                  key={int}
                  onClick={() => setInterval(int)}
                  className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                    interval === int 
                    ? 'bg-slate-800 text-blue-400' 
                    : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {int}
                </button>
              ))}
        </div>
      </div>

      <div className="flex-1 relative min-h-[400px]">
        {klineQuery.isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center text-slate-500">
                Loading {symbol}...
            </div>
        ) : (
            <ReactECharts
                option={getOption(klineQuery.data || [])}
                style={{ height: '100%', width: '100%' }}
                theme="dark"
            />
        )}
      </div>
    </div>
  );
}
