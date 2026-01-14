'use client';

import React from 'react';
import Header from '@/components/dashboard/Header';
import CryptoTickerBar from '@/components/dashboard/CryptoTickerBar';
import ModelSummaryCard from '@/components/dashboard/ModelSummaryCard';
import AccountEquityChart from '@/components/charts/AccountEquityChart';
import PerpKlineWithOrders from '@/components/charts/PerpKlineWithOrders';
import PositionsPanel from '@/components/dashboard/PositionsPanel';
import RecentTradesTable from '@/components/dashboard/RecentTradesTable';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashboardPageSkeleton } from '@/components/dashboard/skeletons';

export default function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboard(),
    refetchInterval: 5000,
  });

  if (isLoading) {
    return <DashboardPageSkeleton />;
  }

  // Assume single model for now or select first
  const modelKey = data?.models ? Object.keys(data.models)[0] : null;
  const modelData = modelKey && data ? data.models[modelKey] : null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="max-w-[1920px] mx-auto p-4 md:p-6 space-y-6">
        
        {/* 1. Header Area */}
        <Header />
        
        {/* 2. Top Info Area */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-stretch">
            {/* Model Card - Left */}
          <div className="lg:col-span-3 h-full">
                {isError ? (
                    <div className="h-full min-h-[200px] bg-red-900/20 border border-red-800 rounded-xl flex items-center justify-center text-red-500 p-4 text-center">
                        Connection Error
                    </div>
                ) : modelData ? (
                    <ModelSummaryCard modelData={modelData} />
                ) : (
                    <div className="h-full min-h-[200px] bg-slate-900 rounded-xl animate-pulse flex items-center justify-center text-slate-500">
                      No Model Data
                    </div>
                )}
            </div>
            
            {/* Ticker Bar & Stats - Right */}
            <div className="lg:col-span-9 h-full">
                <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-4 h-full flex flex-col gap-4">
                  <CryptoTickerBar />
                  {/* Stats Grid - Matching Skeleton Layout */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
                       {['Win Rate: 65%', 'Max DD: -12%', 'Sharpe: 2.1', 'Trades: 124'].map((stat, i) => (
                          <div key={i} className="bg-slate-950/50 border border-slate-800 p-4 rounded-lg shadow-sm h-[74px] flex flex-col justify-center gap-2">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider hover-data inline-flex items-center">{stat.split(':')[0]}</p>
                            <p className="text-xl font-bold text-slate-200 hover-data inline-flex items-center">{stat.split(':')[1]}</p>
                          </div>
                       ))}
                  </div>
                </div>
            </div>
        </div>

        {/* 3. Charts Area matching Skeleton Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 w-full">
          {/* Account Equity Chart */}
          <div className="xl:col-span-7 h-full min-h-[560px] xl:min-h-[600px]">
            <AccountEquityChart />
          </div>
            
          {/* Perp Kline Chart */}
          <div className="xl:col-span-5 h-full min-h-[560px] xl:min-h-[600px]">
            <PerpKlineWithOrders />
          </div>
        </div>

        {/* 4. Bottom Area - Positions & Tables */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
             <div className="h-full min-h-[400px]">
                 <PositionsPanel />
             </div>
             <div className="h-full min-h-[400px]">
                 <RecentTradesTable />
             </div>
        </div>
      </div>
    </div>
  );
}
