'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { PositionsTableSkeleton } from '@/components/dashboard/skeletons';
import { DeltaFlash } from '@/components/ui/DeltaFlash';

export default function PositionsPanel() {
  const { data: positions, isLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions(),
    refetchInterval: 5000,
  });

  const formatNumber = (value: number | string | undefined | null, decimals = 2) => {
    if (value === undefined || value === null) return '-';
    const num = Number(value);
    if (Number.isNaN(num)) return '-';
    return num.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  if (isLoading) {
    return <PositionsTableSkeleton />;
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-full">
      <div className="p-4 border-b border-slate-800">
        <h3 className="font-semibold text-slate-100 flex items-center gap-2">
          <span className="hover-data inline-flex items-center">Active Positions</span>
          <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full hover-chip">{positions?.length || 0}</span>
        </h3>
      </div>
      <div className="p-4 grid gap-4 overflow-auto max-h-[400px]">
        {positions?.map((pos) => (
          <div key={pos.id} className="bg-slate-950/50 rounded-lg p-3 border border-slate-800/50 hover:border-slate-700 transition">
            <div className="flex justify-between items-center mb-2">
            <div className="font-bold text-slate-100 hover-data inline-flex items-center">{pos.symbol}</div>
            <div className={`text-xs font-bold px-2 py-0.5 rounded hover-chip ${pos.side === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-500'}`}>
                    {pos.side.toUpperCase()} {pos.leverage}x
                </div>
            </div>
            
            <div className="grid grid-cols-2 gap-y-2 text-sm">
                <div className="flex flex-col">
                    <span className="text-slate-500 text-xs">Size</span>
              <span className="font-mono text-slate-300 hover-data inline-flex items-center">{formatNumber(pos.size, 4)}</span>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-slate-500 text-xs">Unrealized PnL</span>
              <DeltaFlash value={pos.unrealized_pnl} className={`font-mono font-bold hover-data inline-flex items-center ${pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pos.unrealized_pnl >= 0 ? '+' : ''}{formatNumber(pos.unrealized_pnl)}
              </DeltaFlash>
                </div>
                
                <div className="flex flex-col">
                    <span className="text-slate-500 text-xs">Entry Price</span>
              <span className="font-mono text-slate-300 hover-data inline-flex items-center">{formatNumber(pos.entry_price, 2)}</span>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-slate-500 text-xs">Liquidation</span>
              <span className="font-mono text-orange-400 hover-data inline-flex items-center">{pos.liquidation_price ? formatNumber(pos.liquidation_price, 2) : '-'}</span>
                </div>
            </div>
          </div>
        ))}
        {(!positions || positions.length === 0) && (
            <div className="text-center py-6 text-slate-600 italic">No active positions</div>
        )}
      </div>
    </div>
  );
}
