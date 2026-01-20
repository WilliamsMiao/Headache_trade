"use client";

import AccountEquityChart from "@/components/charts/AccountEquityChart";
import PerpKlineWithOrders from "@/components/charts/PerpKlineWithOrders";
import CryptoTickerBar from "@/components/dashboard/CryptoTickerBar";
import Header from "@/components/dashboard/Header";
import ModelSummaryCard from "@/components/dashboard/ModelSummaryCard";
import PositionsPanel from "@/components/dashboard/PositionsPanel";
import RecentTradesTable from "@/components/dashboard/RecentTradesTable";
import { api } from "@/lib/api";
import { DashboardResponse } from "@/types/api";
import { useQuery } from "@tanstack/react-query";

interface DashboardClientProps {
  initialData: DashboardResponse;
}

export default function DashboardClient({ initialData }: DashboardClientProps) {
  const { data = initialData } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.getDashboard(),
    refetchInterval: 5000,
    initialData,
  });

  const modelKey = Object.keys(data.models)[0];
  const modelData = data.models[modelKey];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="max-w-[1920px] mx-auto p-4 md:p-6 space-y-6">
        <CryptoTickerBar />
        {/* 1. Header Area */}
        <Header />

        {/* 2. Top Info Area */}
        <div className="w-full items-stretch">
          <ModelSummaryCard modelData={modelData} />
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
