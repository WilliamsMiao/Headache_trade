'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CryptoTickerSkeleton } from '@/components/dashboard/skeletons';
import { DeltaFlash } from '@/components/ui/DeltaFlash';

export default function CryptoTickerBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboard(),
    refetchInterval: 5000,
  });

  if (isLoading) {
    return <CryptoTickerSkeleton />;
  }
  
  if (isError) {
      return (
        <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide">
            <div className="flex-shrink-0 flex items-center gap-3 bg-red-900/20 px-4 py-2 rounded-lg border border-red-800 shadow-sm min-w-[200px] text-red-400 text-sm">
                API Error: Retry in 5s
            </div>
        </div>
      )
  }

  const prices = data?.crypto_prices || {};

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-3 pb-1">
      {Object.entries(prices).map(([symbol, { price, change }]) => (
        <div key={symbol} className="flex items-center justify-between gap-3 bg-slate-900 px-4 py-3 rounded-lg border border-slate-800 shadow-sm h-full">
           <div className="font-bold text-slate-200 hover-data inline-flex items-center">{symbol}</div>
           <div className="flex flex-col items-end">
             <DeltaFlash value={price} className="text-sm font-mono text-slate-100 hover-data inline-flex items-center">
              ${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
             </DeltaFlash>
             <DeltaFlash value={change} className={`text-xs font-medium hover-data inline-flex items-center ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {change >= 0 ? '+' : ''}{Number(change).toFixed(2)}%
             </DeltaFlash>
           </div>
        </div>
      ))}
    </div>
  );
}
