/**
 * 模型摘要卡片骨架（Model Summary Card Skeleton）
 * 
 * 布局结构：
 * - 外层：与 ModelSummaryCard.tsx 相同的卡片容器、内边距、最小高度
 * - 上方：模型图标和名称占位
 * - 中间：状态指示器占位
 * - 下方：2列网格显示关键指标占位
 * 
 * 对应真实页面中左侧 lg:col-span-3 的模型卡片区域
 */

import { SkeletonBox, SkeletonText } from './SkeletonPrimitives';

export function SummaryCardsSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl h-full flex flex-col justify-between min-h-[200px]">
      {/* 模型信息区域 */}
      <div className="space-y-4">
        {/* 模型图标和名称 */}
        <div className="flex items-center gap-3">
          <SkeletonBox className="w-12 h-12 rounded-lg" />
          <div className="space-y-2 flex-1">
            <SkeletonText className="w-32 h-5" />
            <SkeletonText className="w-24 h-3" />
          </div>
        </div>

        {/* 状态指示器 */}
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-950/50 rounded-lg border border-slate-800/50">
          <SkeletonBox className="w-2 h-2 rounded-full" />
          <SkeletonText className="w-28 h-4" />
        </div>
      </div>

      {/* 关键指标网格 */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-2">
            <SkeletonText className="w-20 h-3" />
            <SkeletonText className="w-24 h-6" />
          </div>
        ))}
      </div>

      {/* 底部操作按钮区域 */}
      <div className="mt-6 pt-4 border-t border-slate-800/50">
        <SkeletonBox className="w-full h-9 rounded-lg" />
      </div>
    </div>
  );
}
