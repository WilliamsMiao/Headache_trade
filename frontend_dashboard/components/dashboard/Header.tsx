'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export default function Header() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboard(),
    refetchInterval: 5000,
  });

  const modelInfo = data ? Object.values(data.models)[0] : null;

  return (
    <header className="flex flex-col md:flex-row justify-between items-start md:items-center p-6 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
      <div>
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">
          Headache Trade <span className="text-slate-500 font-light text-lg">AI Dashboard</span>
        </h1>
        <div className="flex items-center gap-2 mt-1">
             <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
             <p className="text-xs text-slate-400">System Operational</p>
        </div>
      </div>
      
      <div className="flex items-center gap-6 mt-4 md:mt-0">
         {modelInfo && (
             <div className="hidden md:block text-right">
                 <p className="text-xs text-slate-500">Active Model</p>
                 <p className="text-sm font-semibold text-slate-200">{modelInfo.name}</p>
             </div>
         )}
         
         <div className="text-right">
             <p className="text-xs text-slate-500">Total Equity</p>
             <p className="text-xl font-bold font-mono text-white">
                ${modelInfo?.account_value.toLocaleString(undefined, {minimumFractionDigits: 2}) || '---'}
             </p>
         </div>

         <div className="text-right">
            <p className="text-xs text-slate-500">Today's PnL</p>
            <p className={`text-sm font-bold font-mono ${ (modelInfo?.change_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(modelInfo?.change_percent || 0) >= 0 ? '+' : ''}{modelInfo?.change_percent || 0}%
            </p>
         </div>
         
         <div className="h-8 w-px bg-slate-800 hidden md:block"></div>
         
         <div className="text-xs text-slate-500 text-right">
            <p>Last Update</p>
            <p className="font-mono text-slate-300">{data?.last_update?.split(' ')[1] || '--:--:--'}</p>
         </div>
      </div>
    </header>
  );
}
