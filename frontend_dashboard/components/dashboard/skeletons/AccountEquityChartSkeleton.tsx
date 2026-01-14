/**
 * 账户价值图表骨架（Account Equity Chart Skeleton）
 * 
 * 布局结构：
 * - 外层：与 AccountEquityChart.tsx 相同的卡片容器，固定高度 h-[500px]
 * - 顶部：标题 + 时间粒度按钮（1H/4H/1D/1W/ALL）占位
 * - 中间：图表区域，包含：
 *   - 左侧 Y 轴刻度占位
 *   - 中间主绘图区（带网格线和闪烁效果）
 * - 底部：X 轴时间标签占位
 * 
 * 对应页面主内容区左侧/上方的 xl:col-span-8 区域
 */

import { SkeletonBox, SkeletonText, ShimmerEffect } from './SkeletonPrimitives';

export function AccountEquityChartSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col h-[500px] w-full">
      {/* 图表头部：标题 + 时间粒度控制 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        {/* 标题占位 */}
        <SkeletonText className="h-6 w-48" />
        
        {/* 时间粒度按钮组占位 */}
        <div className="flex gap-2">
          {['1H', '4H', '1D', '1W', 'ALL'].map((label) => (
            <SkeletonBox key={label} className="h-9 w-12 rounded-md" />
          ))}
        </div>
      </div>
      
      {/* 图表主体区域 */}
      <div className="flex-1 flex gap-4 relative">
        {/* 闪烁动画效果 */}
        <ShimmerEffect />

        {/* Y轴刻度占位 */}
        <div className="w-12 h-full flex flex-col justify-between py-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <SkeletonText key={i} className="h-3 w-full" />
          ))}
        </div>
        
        {/* 主绘图区域 */}
        <div className="flex-1 bg-slate-900/50 rounded-lg relative overflow-hidden border border-slate-800/50">
          {/* 横向网格线 */}
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div 
              key={`h-${i}`}
              className="absolute w-full h-px bg-slate-800/50" 
              style={{ top: `${i * 20}%` }}
            />
          ))}
          
          {/* 纵向网格线 */}
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <div 
              key={`v-${i}`}
              className="absolute h-full w-px bg-slate-800/50" 
              style={{ left: `${i * 16.66}%` }}
            />
          ))}

          {/* 模拟折线图路径（可选装饰） */}
          <div className="absolute inset-0 flex items-center justify-center opacity-20">
            <svg className="w-full h-3/4" viewBox="0 0 100 40" preserveAspectRatio="none">
              <path
                d="M 0,35 L 10,32 L 20,28 L 30,25 L 40,22 L 50,20 L 60,18 L 70,20 L 80,17 L 90,15 L 100,12"
                fill="none"
                stroke="currentColor"
                strokeWidth="0.5"
                className="text-slate-700"
              />
            </svg>
          </div>
        </div>
      </div>
      
      {/* X轴时间标签占位 */}
      <div className="h-6 w-full pl-16 flex justify-between items-center mt-3 gap-2">
        {[1, 2, 3, 4, 5, 6, 7].map((i) => (
          <SkeletonText key={i} className="h-3 w-16" />
        ))}
      </div>
    </div>
  );
}
