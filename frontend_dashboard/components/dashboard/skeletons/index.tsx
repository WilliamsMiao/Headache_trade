/**
 * Skeleton Layout System
 * 
 * 设计理念：布局优先（Layout-First Approach）
 * 
 * 1. 每个骨架组件的外层容器与真实组件完全一致（相同的 grid、flex、gap、min-h）
 * 2. 内层只做视觉占位（灰色条、矩形等），不影响布局结构
 * 3. 保证数据加载前后页面不跳动，骨架与真实内容是1:1映射
 */

export * from './SkeletonPrimitives';
export * from './DashboardHeaderSkeleton';
export * from './SummaryCardsSkeleton';
export * from './CryptoTickerSkeleton';
export * from './StatCardsSkeleton';
export * from './AccountEquityChartSkeleton';
export * from './PerpKlineWithOrdersSkeleton';
export * from './PositionsTableSkeleton';
export * from './RecentTradesTableSkeleton';
export * from './DashboardPageSkeleton';
