/**
 * 顶部栏骨架（Dashboard Header Skeleton）
 * 
 * 布局结构：
 * - 外层：与 Header.tsx 相同的 sticky 顶栏、flex 布局
 * - 左侧：标题和状态指示器占位
 * - 右侧：模型信息、权益、PnL、分隔符、按钮占位
 * 
 * 保证与真实 Header 组件的高度、内边距、间距完全一致
 */

import { SkeletonBox, SkeletonText, SkeletonCircle } from './SkeletonPrimitives';

export function DashboardHeaderSkeleton() {
  return (
    <header className="flex flex-col md:flex-row justify-between items-start md:items-center p-6 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
      {/* 左侧：标题区域骨架 */}
      <div>
        {/* 主标题占位 */}
        <div className="flex items-center gap-2">
          <SkeletonText className="w-64 h-7" />
        </div>
        
        {/* 系统状态指示器占位 */}
        <div className="flex items-center gap-2 mt-1">
          <SkeletonCircle className="w-2 h-2" />
          <SkeletonText className="w-32 h-3" />
        </div>
      </div>
      
      {/* 右侧：信息和控制区域骨架 */}
      <div className="flex items-center gap-6 mt-4 md:mt-0">
        {/* 活跃模型信息占位 */}
        <div className="hidden md:block text-right space-y-1">
          <SkeletonText className="w-20 h-3" />
          <SkeletonText className="w-32 h-4" />
        </div>
        
        {/* 总权益占位 */}
        <div className="text-right space-y-1">
          <SkeletonText className="w-24 h-3" />
          <SkeletonText className="w-32 h-6" />
        </div>

        {/* 今日PnL占位 */}
        <div className="text-right space-y-1">
          <SkeletonText className="w-20 h-3" />
          <SkeletonText className="w-16 h-5" />
        </div>
        
        {/* 分隔线 */}
        <div className="h-8 w-px bg-slate-800 hidden md:block"></div>
        
        {/* 刷新按钮占位 */}
        <SkeletonBox className="w-9 h-9 rounded-lg" />
      </div>
    </header>
  );
}
