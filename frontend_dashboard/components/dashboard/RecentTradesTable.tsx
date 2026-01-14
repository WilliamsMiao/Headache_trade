'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { RecentTradesTableSkeleton } from '@/components/dashboard/skeletons';
import { DeltaFlash } from '@/components/ui/DeltaFlash';

export default function RecentTradesTable() {
  const { data: trades, isLoading, isError } = useQuery({
    queryKey: ['trades'],
    queryFn: () => api.getTrades(),
    refetchInterval: 15000,
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
    return <RecentTradesTableSkeleton />;
  }

  if (isError) {
      return (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-full items-center justify-center text-red-500 p-6">
             <p>Failed to load trades.</p>
        </div>
      )
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-full">
      <div className="p-4 border-b border-slate-800 flex justify-between items-center">
        <h3 className="font-semibold text-slate-100 hover-data inline-flex items-center">Recent Trades</h3>
      </div>
      {/* 设定块内滚动，避免长数据撑开页面 */}
      <div className="overflow-auto flex-1 max-h-[460px]">
        {/* table-auto 让列宽随内容自适应，配合单元格内的截断与缩减间距，避免出现横向滚动条 */}
        <table className="w-full text-left text-sm text-slate-400 table-auto">
          <thead className="bg-slate-950 text-slate-200 uppercase text-xs font-semibold sticky top-0">
            <tr>
              <th className="px-3 py-2 sm:px-4 sm:py-3">Time</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3">Symbol</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3">Side</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3 text-right">Size</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3 text-right">Entry</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3 text-right">Exit</th>
              <th className="px-3 py-2 sm:px-4 sm:py-3 text-right">PnL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {trades?.slice(0, 10).map((trade) => (
              <tr key={trade.id} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-3 py-2 sm:px-4 sm:py-3 whitespace-nowrap text-[11px] sm:text-xs">
                  <span className="hover-data inline-flex items-center">{trade.closed_at.split(' ')[1]}</span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 font-medium text-slate-200">
                  <span className="hover-data inline-flex items-center max-w-[120px] truncate">{trade.symbol}</span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 font-semibold">
                  <span className={`hover-data inline-flex items-center ${trade.side === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.side.toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 text-right font-mono text-[11px] sm:text-sm whitespace-nowrap">
                  <span className="hover-data inline-flex items-center justify-end w-full">{formatNumber(trade.size)}</span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 text-right font-mono text-slate-300 text-[11px] sm:text-sm whitespace-nowrap">
                  <span className="hover-data inline-flex items-center justify-end w-full">{formatNumber(trade.entry_price)}</span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 text-right font-mono text-slate-300 text-[11px] sm:text-sm whitespace-nowrap">
                  <span className="hover-data inline-flex items-center justify-end w-full">{formatNumber(trade.exit_price)}</span>
                </td>
                <td className="px-3 py-2 sm:px-4 sm:py-3 text-right font-mono font-bold text-[11px] sm:text-sm whitespace-nowrap">
                  <DeltaFlash value={trade.pnl} className={`hover-data inline-flex items-center justify-end w-full ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.pnl >= 0 ? '+' : ''}{formatNumber(trade.pnl)}
                  </DeltaFlash>
                </td>
              </tr>
            ))}
            {(!trades || trades.length === 0) && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-slate-600">No recent trades found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
