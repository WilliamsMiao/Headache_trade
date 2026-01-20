# 骨架布局系统使用指南

## 概述

本系统实现了一套完整的骨架布局（Skeleton Layout），采用**布局优先**的设计理念，确保在数据加载过程中页面不会出现布局跳动。

## 设计原则

### 1. 布局一致性（Layout Consistency）
- 骨架组件的外层容器与真实组件**完全一致**
- 相同的 `grid`、`flex`、`gap`、`min-h` 等布局属性
- 相同的响应式断点（`md:`、`lg:`、`xl:`）

### 2. 结构映射（1:1 Mapping）
- 每个骨架组件对应一个真实组件
- 内层只做视觉占位（灰色条、矩形），不影响布局
- 数据加载前后，页面结构保持不变

### 3. 视觉反馈（Visual Feedback）
- 使用 `animate-pulse` 提供加载动画
- 可选的 `shimmer` 闪烁效果增强感知
- 保持与真实内容相似的视觉层次

## 组件架构

```
components/dashboard/skeletons/
├── index.tsx                          # 统一导出
├── SkeletonPrimitives.tsx            # 基础组件（Box、Text、Circle、Shimmer）
├── DashboardHeaderSkeleton.tsx       # 顶部栏骨架
├── SummaryCardsSkeleton.tsx          # 模型摘要卡片骨架
├── CryptoTickerSkeleton.tsx          # 加密货币价格条骨架
├── StatCardsSkeleton.tsx             # 统计卡片网格骨架
├── AccountEquityChartSkeleton.tsx    # 账户价值图骨架
├── PerpKlineWithOrdersSkeleton.tsx   # 永续合约K线图骨架
├── PositionsTableSkeleton.tsx        # 持仓表格骨架
├── RecentTradesTableSkeleton.tsx     # 成交记录表格骨架
└── DashboardPageSkeleton.tsx         # 页面级骨架组合
```

## 使用方法

### 页面级使用

在 `page.tsx` 中，数据加载时渲染完整的页面骨架：

```tsx
import { DashboardPageSkeleton } from '@/components/dashboard/skeletons';

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboard(),
  });

  if (isLoading) {
    return <DashboardPageSkeleton />;
  }

  return (
    // 真实页面内容
  );
}
```

### 组件级使用

在单个组件中使用对应的骨架组件：

```tsx
import { AccountEquityChartSkeleton } from '@/components/dashboard/skeletons';

export function AccountEquityChart() {
  const { data, isLoading } = useQuery(...);

  if (isLoading) {
    return <AccountEquityChartSkeleton />;
  }

  return (
    // 真实图表内容
  );
}
```

## 骨架组件详解

### 1. DashboardHeaderSkeleton
**位置**：页面顶部粘性栏  
**布局**：`flex justify-between`，左侧标题+状态，右侧模型信息+权益  
**高度**：与真实 Header 一致

### 2. SummaryCardsSkeleton
**位置**：顶部信息区左侧（`lg:col-span-3`）  
**布局**：卡片容器，内部垂直布局，包含模型信息、状态、指标网格  
**最小高度**：`min-h-[200px]`

### 3. CryptoTickerSkeleton
**位置**：顶部信息区右上方  
**布局**：横向滚动容器，6个币种卡片占位  
**固定高度**：`h-[66px]`

### 4. StatCardsSkeleton
**位置**：Crypto Ticker 下方  
**布局**：`grid-cols-2 md:grid-cols-4`，4个统计卡片  
**固定高度**：`h-[74px]`

### 5. AccountEquityChartSkeleton
**位置**：主图表区左侧/上方（`xl:col-span-8`）  
**布局**：卡片容器，包含标题栏、时间粒度按钮、图表区、坐标轴  
**固定高度**：`h-[500px]`  
**特色**：带网格线和闪烁效果的图表占位

### 6. PerpKlineWithOrdersSkeleton
**位置**：主图表区右侧/下方（`xl:col-span-4`）  
**布局**：卡片容器，包含控制栏、K线图区、右侧信息面板  
**固定高度**：`h-[500px]`  
**特色**：20根蜡烛图占位，带上下影线效果

### 7. PositionsTableSkeleton
**位置**：底部左侧（`xl:col-span-1`）  
**布局**：卡片容器，标题栏 + 3个持仓卡片  
**最小高度**：`min-h-[400px]`

### 8. RecentTradesTableSkeleton
**位置**：底部右侧（`xl:col-span-1`）  
**布局**：卡片容器，标题栏 + 表头 + 8行记录  
**最小高度**：`min-h-[400px]`

## 布局对应关系

| 真实组件 | 骨架组件 | 位置 | 栅格 |
|---------|---------|------|------|
| Header | DashboardHeaderSkeleton | 顶部 | - |
| ModelSummaryCard | SummaryCardsSkeleton | 左上 | lg:col-span-3 |
| CryptoTickerBar | CryptoTickerSkeleton | 右上 | lg:col-span-9 |
| StatCards | StatCardsSkeleton | 右上下方 | grid-cols-4 |
| AccountEquityChart | AccountEquityChartSkeleton | 中左 | xl:col-span-8 |
| PerpKlineWithOrders | PerpKlineWithOrdersSkeleton | 中右 | xl:col-span-4 |
| PositionsPanel | PositionsTableSkeleton | 底左 | xl:col-span-1 |
| RecentTradesTable | RecentTradesTableSkeleton | 底右 | xl:col-span-1 |

## 扩展和自定义

### 修改骨架样式

编辑对应的骨架组件文件，修改 `SkeletonText` 和 `SkeletonBox` 的宽度、高度：

```tsx
<SkeletonText className="w-32 h-6" /> // 调整占位条尺寸
```

### 添加新的骨架组件

1. 在 `skeletons/` 目录创建新文件
2. 导入基础组件：`SkeletonBox`, `SkeletonText`, `ShimmerEffect`
3. 确保外层布局与真实组件一致
4. 在 `index.tsx` 中导出

### 调整动画效果

修改 `SkeletonPrimitives.tsx` 中的 `ShimmerEffect` 组件：

```tsx
<div className="... animate-[shimmer_2s_infinite] ..." />
//                          ↑ 动画名称  ↑ 持续时间  ↑ 循环方式
```

## 性能考虑

- 骨架组件是纯展示组件，无状态，无副作用
- 首次渲染即完整，无需等待数据
- 切换到真实内容时，由于布局一致，重排（reflow）开销极小
- 建议在 `isLoading` 状态下使用，避免短暂闪现

## 常见问题

### Q: 骨架和真实内容切换时仍有跳动？
**A**: 检查骨架组件的外层容器是否与真实组件完全一致，特别注意：
- `min-h-[xxx]` 是否相同
- `grid-cols-x` 和 `gap-x` 是否匹配
- 响应式断点 `md:`, `lg:`, `xl:` 是否一致

### Q: 如何调整加载动画速度？
**A**: 修改 `tailwind.config.ts` 中的 `shimmer` 动画持续时间，或直接在组件中调整 `animate-pulse` 的持续时间。

### Q: 骨架组件可以复用吗？
**A**: 可以。基础组件（`SkeletonBox`, `SkeletonText`）可以在任何地方复用。区域级骨架组件（如 `AccountEquityChartSkeleton`）建议仅在对应的真实组件中使用，以保持一致性。

## 总结

本骨架布局系统通过**布局优先**的设计，确保了数据加载时的流畅体验。所有骨架组件都与真实组件保持1:1的结构映射，使得页面在加载过程中始终保持稳定的布局，无跳动，提升用户体验。
