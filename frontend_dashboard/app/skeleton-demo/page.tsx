'use client';

/**
 * 骨架布局演示页面
 * 
 * 用于测试和预览所有骨架组件的视觉效果
 * 访问路径：/skeleton-demo
 */

import React, { useState } from 'react';
import { DashboardPageSkeleton } from '@/components/dashboard/skeletons';
import { DashboardHeaderSkeleton } from '@/components/dashboard/skeletons/DashboardHeaderSkeleton';
import { SummaryCardsSkeleton } from '@/components/dashboard/skeletons/SummaryCardsSkeleton';
import { CryptoTickerSkeleton } from '@/components/dashboard/skeletons/CryptoTickerSkeleton';
import { StatCardsSkeleton } from '@/components/dashboard/skeletons/StatCardsSkeleton';
import { AccountEquityChartSkeleton } from '@/components/dashboard/skeletons/AccountEquityChartSkeleton';
import { PerpKlineWithOrdersSkeleton } from '@/components/dashboard/skeletons/PerpKlineWithOrdersSkeleton';
import { PositionsTableSkeleton } from '@/components/dashboard/skeletons/PositionsTableSkeleton';
import { RecentTradesTableSkeleton } from '@/components/dashboard/skeletons/RecentTradesTableSkeleton';

export default function SkeletonDemoPage() {
  const [view, setView] = useState<'full' | 'components'>('full');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* 控制面板 */}
      <div className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 p-4">
        <div className="max-w-[1920px] mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-white">骨架布局演示</h1>
            <p className="text-sm text-slate-400 mt-1">Skeleton Layout Demo</p>
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={() => setView('full')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                view === 'full'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              完整页面
            </button>
            <button
              onClick={() => setView('components')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                view === 'components'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              分组件
            </button>
          </div>
        </div>
      </div>

      {/* 内容区 */}
      {view === 'full' ? (
        <DashboardPageSkeleton />
      ) : (
        <div className="max-w-[1920px] mx-auto p-6 space-y-12">
          
          {/* Header 组件 */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">顶部栏骨架</h2>
              <p className="text-sm text-slate-400">DashboardHeaderSkeleton</p>
            </div>
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-4">
              <DashboardHeaderSkeleton />
            </div>
          </section>

          {/* Model + Ticker 组合 */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">顶部信息区骨架</h2>
              <p className="text-sm text-slate-400">SummaryCards + CryptoTicker + StatCards</p>
            </div>
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-4">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-3">
                  <SummaryCardsSkeleton />
                </div>
                <div className="lg:col-span-9 flex flex-col gap-4">
                  <CryptoTickerSkeleton />
                  <StatCardsSkeleton />
                </div>
              </div>
            </div>
          </section>

          {/* Charts 组合 */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">主图表区骨架</h2>
              <p className="text-sm text-slate-400">AccountEquityChart + PerpKlineWithOrders</p>
            </div>
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-4">
              <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
                <div className="xl:col-span-8">
                  <AccountEquityChartSkeleton />
                </div>
                <div className="xl:col-span-4">
                  <PerpKlineWithOrdersSkeleton />
                </div>
              </div>
            </div>
          </section>

          {/* Tables 组合 */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">底部表格区骨架</h2>
              <p className="text-sm text-slate-400">PositionsTable + RecentTradesTable</p>
            </div>
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-4">
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <PositionsTableSkeleton />
                <RecentTradesTableSkeleton />
              </div>
            </div>
          </section>

          {/* 单个组件展示 */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">单个组件示例</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-2">模型卡片</h3>
                <SummaryCardsSkeleton />
              </div>
              
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-2">价格条</h3>
                <CryptoTickerSkeleton />
              </div>
              
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-2">统计卡片</h3>
                <StatCardsSkeleton />
              </div>
            </div>
          </section>

        </div>
      )}
    </div>
  );
}
