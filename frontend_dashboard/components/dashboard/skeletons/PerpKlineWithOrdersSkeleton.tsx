/**
 * 永续合约K线图骨架（Perpetual Kline with Orders Skeleton）
 * 
 * 布局结构：
 * - 外层：与 PerpKlineWithOrders.tsx 相同的卡片容器，固定高度 h-[500px]
 * - 顶部：币种选择器 + 时间粒度按钮占位
 * - 中间：K线图主体区域 + 右侧订单信息面板（仅在 xl 尺寸显示）
 * - K线区域：模拟20根蜡烛图占位，带上下影线效果
 * 
 * 对应页面主内容区右侧/下方的 xl:col-span-4 区域
 */

import { SkeletonBox, ShimmerEffect } from './SkeletonPrimitives';

export function PerpKlineWithOrdersSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col h-[500px] w-full">
      {/* 顶部控制栏 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4">
        {/* 币种选择器 + 交易对下拉框占位 */}
        <div className="flex gap-3">
          <SkeletonBox className="h-9 w-32 rounded-lg" />
          <SkeletonBox className="h-9 w-24 rounded-lg" />
        </div>
        
        {/* 时间粒度按钮占位 */}
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonBox key={i} className="h-8 w-10 rounded-md" />
          ))}
        </div>
      </div>

      {/* K线图主体 + 侧边栏 */}
      <div className="flex-1 flex gap-3 relative">
        {/* 闪烁动画效果 */}
        <ShimmerEffect />

        {/* K线图区域 */}
        <div className="flex-1 bg-slate-900/30 border border-slate-800/50 rounded-lg relative overflow-hidden flex items-end justify-around px-4 pb-8 pt-4">
          {/* 模拟20根K线蜡烛图 */}
          {[...Array(20)].map((_, i) => {
            // 生成确定性的高度变化（20%-80%）
            const bodyHeight = 20 + ((i * 13 + 7) % 60);
            const wickTop = Math.min(5 + (i % 15), 15);
            const wickBottom = Math.min(5 + ((i * 7) % 12), 12);
            const isGreen = i % 3 !== 0; // 绿涨红跌比例约 2:1
            
            return (
              <div 
                key={i} 
                className="relative flex flex-col items-center justify-end"
                style={{ height: '100%', width: '3%' }}
              >
                {/* 上影线 */}
                <div 
                  className={`w-[1px] ${isGreen ? 'bg-emerald-700/60' : 'bg-red-700/60'}`}
                  style={{ height: `${wickTop}%` }}
                />
                
                {/* 蜡烛主体 */}
                <div 
                  className={`w-full rounded-sm ${
                    isGreen 
                      ? 'bg-slate-800 border border-slate-700' 
                      : 'bg-slate-750 border border-slate-700'
                  }`}
                  style={{ height: `${bodyHeight}%` }}
                />
                
                {/* 下影线 */}
                <div 
                  className={`w-[1px] ${isGreen ? 'bg-emerald-700/60' : 'bg-red-700/60'}`}
                  style={{ height: `${wickBottom}%` }}
                />
              </div>
            );
          })}
        </div>
        
        {/* 右侧订单信息面板（仅在 xl 及以上显示）*/}
        <div className="hidden xl:flex w-48 flex-col gap-3">
          {/* 当前持仓卡片占位 */}
          <div className="bg-slate-900/50 border border-slate-800/50 rounded-lg p-3 space-y-2 h-28">
            <SkeletonBox className="h-4 w-24" />
            <SkeletonBox className="h-6 w-full" />
            <SkeletonBox className="h-4 w-20" />
          </div>
          
          {/* 待处理订单卡片占位 */}
          <div className="bg-slate-900/50 border border-slate-800/50 rounded-lg p-3 space-y-2 h-28">
            <SkeletonBox className="h-4 w-28" />
            <SkeletonBox className="h-6 w-full" />
            <SkeletonBox className="h-4 w-16" />
          </div>
          
          {/* 市场信息卡片占位 */}
          <div className="flex-1 bg-slate-900/50 border border-slate-800/50 rounded-lg p-3">
            <div className="space-y-3">
              <SkeletonBox className="h-4 w-20" />
              <SkeletonBox className="h-5 w-full" />
              <SkeletonBox className="h-4 w-full" />
              <SkeletonBox className="h-4 w-3/4" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
