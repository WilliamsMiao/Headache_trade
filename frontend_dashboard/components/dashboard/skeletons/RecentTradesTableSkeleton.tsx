/**
 * 近期成交表格骨架（Recent Trades Table Skeleton）
 * 
 * 布局结构：
 * - 外层：与 RecentTradesTable.tsx 相同的卡片容器，最小高度 min-h-[400px]
 * - 顶部：标题栏 + 筛选控制占位
 * - 表头：时间、交易对、方向、数量、价格等列标题
 * - 表体：8行成交记录占位，每行包含对应列的数据占位
 * 
 * 对应页面底部右侧的成交记录表格区域
 */

import { SkeletonBox, SkeletonText } from './SkeletonPrimitives';

export function RecentTradesTableSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-full min-h-[400px] w-full">
      {/* 标题栏 */}
      <div className="p-4 border-b border-slate-800 flex justify-between items-center">
        <SkeletonText className="w-36 h-6" />
        <div className="flex gap-2">
          <SkeletonBox className="w-20 h-8 rounded-md" />
          <SkeletonBox className="w-8 h-8 rounded-md" />
        </div>
      </div>
      
      {/* 表格主体 */}
      <div className="flex-1 overflow-auto">
        <div className="p-4 space-y-3">
          {/* 表头 */}
          <div className="grid grid-cols-5 gap-4 px-3 py-2 text-xs font-semibold text-slate-500 border-b border-slate-800/50">
            <SkeletonText className="w-12 h-3" /> {/* Time */}
            <SkeletonText className="w-16 h-3" /> {/* Symbol */}
            <SkeletonText className="w-10 h-3" /> {/* Side */}
            <SkeletonText className="w-14 h-3" /> {/* Quantity */}
            <SkeletonText className="w-12 h-3" /> {/* Price */}
          </div>
          
          {/* 表体行 */}
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div 
              key={i} 
              className="grid grid-cols-5 gap-4 px-3 py-3 border-b border-slate-800/30 last:border-0 items-center hover:bg-slate-950/50 transition-colors"
            >
              {/* 时间列 */}
              <SkeletonText className="w-16 h-3" />
              
              {/* 交易对列 */}
              <SkeletonText className="w-20 h-4" />
              
              {/* 方向列 */}
              <SkeletonBox className="w-12 h-5 rounded" />
              
              {/* 数量列 */}
              <SkeletonText className="w-16 h-3" />
              
              {/* 价格列 */}
              <SkeletonText className="w-20 h-4" />
            </div>
          ))}
        </div>
      </div>

      {/* 底部分页控制（可选）*/}
      <div className="p-3 border-t border-slate-800 flex justify-between items-center bg-slate-950/30">
        <SkeletonText className="w-32 h-3" />
        <div className="flex gap-2">
          <SkeletonBox className="w-8 h-8 rounded-md" />
          <SkeletonBox className="w-8 h-8 rounded-md" />
          <SkeletonBox className="w-8 h-8 rounded-md" />
        </div>
      </div>
    </div>
  );
}
