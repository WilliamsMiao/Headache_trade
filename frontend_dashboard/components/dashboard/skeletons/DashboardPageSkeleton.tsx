/**
 * 仪表盘页面级骨架布局（Dashboard Page Skeleton Layout）
 * 
 * 这是页面级的骨架组合组件，整合了所有区域的骨架布局
 * 
 * 布局结构（与 page.tsx 完全一致）：
 * 
 * 1. 顶部栏区域（Header）
 *    - DashboardHeaderSkeleton
 * 
 * 2. 顶部信息区（Grid: lg:grid-cols-12）
 *    - 左侧 lg:col-span-3：模型摘要卡片
 *    - 右侧 lg:col-span-9：Crypto价格条 + 统计卡片网格
 * 
 * 3. 主图表区（Grid: xl:grid-cols-12）
 *    - 左侧 xl:col-span-8：账户价值图
 *    - 右侧 xl:col-span-4：永续合约K线图
 * 
 * 4. 底部表格区（Grid: xl:grid-cols-2）
 *    - 左侧：持仓面板
 *    - 右侧：近期成交表格
 * 
 * 关键原则：
 * - 所有栅格布局、间距、内边距与真实页面完全一致
 * - 骨架渲染时，页面结构已经完整，数据加载不会导致布局跳动
 * - 可以通过 isLoading 状态在骨架和真实内容之间平滑切换
 */

import { DashboardHeaderSkeleton } from './DashboardHeaderSkeleton';
import { SummaryCardsSkeleton } from './SummaryCardsSkeleton';
import { CryptoTickerSkeleton } from './CryptoTickerSkeleton';
import { StatCardsSkeleton } from './StatCardsSkeleton';
import { AccountEquityChartSkeleton } from './AccountEquityChartSkeleton';
import { PerpKlineWithOrdersSkeleton } from './PerpKlineWithOrdersSkeleton';
import { PositionsTableSkeleton } from './PositionsTableSkeleton';
import { RecentTradesTableSkeleton } from './RecentTradesTableSkeleton';

export function DashboardPageSkeleton() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-500/30">
      <div className="max-w-[1920px] mx-auto p-4 md:p-6 space-y-6">
        
        {/* ========== 1. 顶部栏区域 ========== */}
        {/* 布局：粘性顶栏，包含标题、状态、模型信息、权益等 */}
        <DashboardHeaderSkeleton />

        {/* ========== 2. 顶部信息区域 ========== */}
        {/* 布局：lg 断点下 12列网格，左侧3列模型卡，右侧9列价格和统计 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full">
          {/* 左侧：模型摘要卡片区域 */}
          <div className="lg:col-span-3 h-full">
            <SummaryCardsSkeleton />
          </div>
          
          {/* 右侧：Crypto价格条 + 统计卡片 */}
          <div className="lg:col-span-9 flex flex-col gap-4">
            {/* Crypto 价格横向滚动条 */}
            <CryptoTickerSkeleton />
            
            {/* 统计卡片网格（Win Rate、Max DD、Sharpe、Trades） */}
            <StatCardsSkeleton />
          </div>
        </div>

        {/* ========== 3. 主图表区域 ========== */}
        {/* 布局：xl 断点下 12列网格，左侧8列账户价值图，右侧4列K线图 */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 w-full">
          {/* 左侧/上方：账户价值图区域 */}
          <div className="xl:col-span-8 h-full min-h-[500px]">
            <AccountEquityChartSkeleton />
          </div>
          
          {/* 右侧/下方：永续合约K线图区域 */}
          <div className="xl:col-span-4 h-full min-h-[500px]">
            <PerpKlineWithOrdersSkeleton />
          </div>
        </div>

        {/* ========== 4. 底部表格区域 ========== */}
        {/* 布局：xl 断点下 2列网格，左侧持仓，右侧成交 */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
          {/* 左侧：持仓面板 */}
          <div className="h-full min-h-[400px]">
            <PositionsTableSkeleton />
          </div>
          
          {/* 右侧：近期成交表格 */}
          <div className="h-full min-h-[400px]">
            <RecentTradesTableSkeleton />
          </div>
        </div>

      </div>
    </div>
  );
}
