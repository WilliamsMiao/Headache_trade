/**
 * 骨架布局基础组件（Skeleton Primitives）
 * 
 * 这些是最底层的视觉占位元素，只负责样式，不涉及布局逻辑
 */

import { Skeleton } from "@/components/ui/skeleton";

export function SkeletonBox({ className }: { className?: string }) {
  return <Skeleton className={`rounded-md bg-slate-800/50 ${className || ''}`} />;
}

export function SkeletonText({ className }: { className?: string }) {
  return <Skeleton className={`h-4 rounded-sm bg-slate-800/50 ${className || ''}`} />;
}

export function SkeletonCircle({ className }: { className?: string }) {
  return <Skeleton className={`rounded-full bg-slate-800/50 ${className || ''}`} />;
}

/**
 * 闪烁动画效果（可选）
 * 用于增强加载感知
 */
export function ShimmerEffect() {
  return (
    <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-slate-700/20 to-transparent z-10 pointer-events-none" />
  );
}
