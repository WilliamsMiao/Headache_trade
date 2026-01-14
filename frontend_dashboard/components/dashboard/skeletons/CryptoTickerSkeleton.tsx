/**
 * 加密货币价格条骨架（Crypto Ticker Bar Skeleton）
 * 
 * 布局结构：
 * - 外层：横向滚动容器，与 CryptoTickerBar.tsx 完全一致
 * - 内层：6个币种卡片占位，每个卡片包含：
 *   - 币种图标（圆形占位）
 *   - 币名和价格（右对齐文本占位）
 * 
 * 固定高度 h-[66px]，固定最小宽度 min-w-[140px]
 */

import { SkeletonBox, SkeletonText, SkeletonCircle } from './SkeletonPrimitives';

export function CryptoTickerSkeleton() {
  return (
    <div className="w-full overflow-hidden">
      <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide">
        {/* 渲染6个币种卡片占位 */}
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div 
            key={i} 
            className="flex-shrink-0 flex items-center gap-3 bg-slate-900 px-4 py-2 rounded-lg border border-slate-800 shadow-sm min-w-[140px] h-[66px]"
          >
            {/* 币种图标占位 */}
            <SkeletonCircle className="h-8 w-8" />
            
            {/* 币名和价格信息占位 */}
            <div className="flex flex-col items-end gap-1 flex-1">
              <SkeletonText className="w-16 h-4" />
              <SkeletonText className="w-12 h-3" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
