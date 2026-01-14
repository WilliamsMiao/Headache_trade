/**
 * 持仓面板骨架（Positions Panel Skeleton）
 * 
 * 布局结构：
 * - 外层：与 PositionsPanel.tsx 相同的卡片容器，最小高度 min-h-[400px]
 * - 顶部：标题栏占位
 * - 主体：3个持仓卡片占位，每个卡片包含：
 *   - 顶部：交易对 + 方向标签
 *   - 底部：2列网格显示仓位详情（数量、价格、盈亏等）
 * 
 * 对应页面底部左侧的持仓表格区域
 */

import { SkeletonBox, SkeletonText } from './SkeletonPrimitives';

export function PositionsTableSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-full min-h-[400px] w-full">
      {/* 标题栏 */}
      <div className="p-4 border-b border-slate-800 flex justify-between items-center">
        <SkeletonText className="w-40 h-6" />
        <SkeletonBox className="w-8 h-8 rounded-md" />
      </div>
      
      {/* 持仓列表 */}
      <div className="flex-1 p-4 space-y-4 overflow-auto">
        {[1, 2, 3].map((i) => (
          <div 
            key={i} 
            className="bg-slate-950/50 rounded-lg p-4 border border-slate-800/50 space-y-3"
          >
            {/* 顶部：交易对和方向 */}
            <div className="flex justify-between items-center">
              <SkeletonText className="w-24 h-5" />
              <SkeletonBox className="w-16 h-6 rounded-md" />
            </div>
            
            {/* 持仓详情网格 */}
            <div className="grid grid-cols-2 gap-4">
              {/* 左列：数量和入场价 */}
              <div className="space-y-3">
                <div className="space-y-1">
                  <SkeletonText className="w-16 h-3" />
                  <SkeletonText className="w-20 h-4" />
                </div>
                <div className="space-y-1">
                  <SkeletonText className="w-20 h-3" />
                  <SkeletonText className="w-24 h-4" />
                </div>
              </div>
              
              {/* 右列：当前价和盈亏 */}
              <div className="space-y-3 flex flex-col items-end">
                <div className="space-y-1 text-right">
                  <SkeletonText className="w-20 h-3" />
                  <SkeletonText className="w-24 h-4" />
                </div>
                <div className="space-y-1 text-right">
                  <SkeletonText className="w-16 h-3" />
                  <SkeletonText className="w-20 h-5" />
                </div>
              </div>
            </div>
            
            {/* 操作按钮 */}
            <div className="flex gap-2 pt-2 border-t border-slate-800/50">
              <SkeletonBox className="flex-1 h-8 rounded-md" />
              <SkeletonBox className="flex-1 h-8 rounded-md" />
            </div>
          </div>
        ))}
      </div>

      {/* 底部摘要（可选）*/}
      <div className="p-4 border-t border-slate-800 bg-slate-950/30">
        <div className="flex justify-between items-center">
          <SkeletonText className="w-32 h-4" />
          <SkeletonText className="w-24 h-5" />
        </div>
      </div>
    </div>
  );
}
