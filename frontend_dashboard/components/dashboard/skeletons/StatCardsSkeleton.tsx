/**
 * 统计卡片网格骨架（Stat Cards Skeleton）
 * 
 * 布局结构：
 * - 外层：2列（移动端）/ 4列（桌面端）网格
 * - 每个卡片：固定高度 h-[74px]，包含标题和数值占位
 * 
 * 对应页面中 Crypto Ticker 下方的关键指标卡片区域
 * 例如：Win Rate、Max DD、Sharpe、Trades 等
 */

import { SkeletonText } from './SkeletonPrimitives';

export function StatCardsSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
      {[1, 2, 3, 4].map((i) => (
        <div 
          key={i} 
          className="bg-slate-900 border border-slate-800 p-4 rounded-lg shadow-sm h-[74px] flex flex-col justify-center gap-2"
        >
          {/* 指标标题占位 */}
          <SkeletonText className="w-20 h-3" />
          
          {/* 指标数值占位 */}
          <SkeletonText className="w-24 h-6" />
        </div>
      ))}
    </div>
  );
}
