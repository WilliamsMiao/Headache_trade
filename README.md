# Headache Trade V3.1 - AI交易团队系统

Headache Trade V3.1 是一个基于多AI Agent协作的高级加密货币自动化交易系统。本项目采用"趋势为王，结构修边"的核心交易理念，通过AI交易团队（市场分析师、量化策略专家、风险管理专家、交易执行专家）协同工作，提供更智能、更全面的交易决策。

## ✨ V3.1 核心特性

- 🤖 **AI交易团队架构** - 四大专业AI技能协同工作：市场分析师、量化策略专家、风险管理专家、交易执行专家
- 🧠 **技能协调层** - 智能调度、结果聚合、异常熔断，确保系统稳定可靠
- 📊 **多时间框架分析** - 支持1m/5m/15m/1h/4h/1d多时间框架技术分析
- 🎯 **动态策略选择** - 根据市场状态自动选择最优策略（趋势跟踪/均值回归/套利等）
- 🛡️ **智能风险管理** - 动态仓位sizing、最大回撤控制、流动性风险评估、黑天鹅事件检测
- ⚡ **算法执行优化** - TWAP/VWAP算法执行、滑点优化、智能订单路由
- 🔄 **渐进式集成** - 不破坏现有系统，支持平滑迁移和回退机制
- 📈 **现代化 Web 仪表板** - 基于 Next.js + React 的全新前端，提供账户概览、实时日志、收益曲线及持仓监控
- 📱 **专业级 K 线图表** - 集成高性能 K 线图表组件，实时展示订单执行情况与价格走势

## 更新日志

### V3.1 (2026-01-15) - AI交易团队重大更新
- 🤖 **AI交易团队架构**: 引入多Agent协作系统，四大专业AI技能协同工作
  - **Market Analyst Skill**: 多时间框架技术分析、市场情绪分析、异常检测
  - **Quant Strategist Skill**: 动态策略选择、参数自适应优化、信号生成
  - **Risk Manager Skill**: 动态仓位sizing、最大回撤控制、流动性风险评估、黑天鹅检测
  - **Trade Executor Skill**: 智能订单路由、TWAP算法执行、滑点优化
- 🧠 **技能协调层**: 实现SkillCoordinator，负责技能调度、结果聚合、异常熔断
- 🔄 **上下文管理**: 实现ContextManager，维护跨技能共享的上下文数据
- 📡 **消息总线**: 实现MessageBus，支持技能间事件驱动通信
- 🔌 **适配层**: 实现DataAdapter和PerformanceMonitor，桥接新旧系统
- 🛡️ **熔断保护**: 实现CircuitBreaker，防止连续失败导致系统崩溃
- 📊 **性能监控**: 自动记录每个技能的执行时间、成功率等指标
- 🔙 **回退机制**: AI技能失败时自动降级到传统策略，确保系统稳定性

### V3.0 (2026-01-15)
- 🗂️ **项目结构规范化**: 重构项目目录结构，符合专业代码项目规范
  - 创建标准 `tests/` 目录，统一管理测试文件
  - 创建 `docs/reports/` 和 `docs/frontend/` 目录，分类管理文档
  - 清理不需要的备份文件和过时文档
- 📝 **文档完善**: 更新所有文档中的过时引用，确保文档与实际代码一致
- 🧹 **代码清理**: 删除过时备份文件，优化项目结构
- ✅ **命名规范**: 验证并确保所有Python文件符合snake_case命名规范
- 📚 **文档组织**: 优化文档分类，提升项目可维护性和专业性

### V2.1 (2026-01-14)
- 🎨 **全新前端架构**: 升级至 Next.js + TypeScript + Tailwind CSS 现代技术栈，替代旧有 Flask 前端。
- 📊 **专业级图表组件**: 新增 `PerpKlineWithOrders` 组件，支持永续期货 K 线图表与订单执行可视化。
- 🎯 **交易逻辑完善**: 优化持仓管理、订单执行流程，增强止损止盈的稳定性与执行效率。
- 📱 **响应式设计**: 完全适配桌面、平板、手机等多终端，提升用户体验。
- 🔧 **组件化架构**: 模块化的 React 组件设计，便于功能扩展与维护。
- 📈 **增强的数据展示**: 新增仪表板页面、加密货币行情条、实时订单状态展示。

### V2.0 (2026-01-13)
- 🚀 **全新AI优化引擎**: 集成DeepSeek AI进行策略参数优化，通过多轮迭代回测提升胜率和盈亏比。
- 📊 **策略管理工具**: 新增回测分析脚本 `analyze_backtest_results.py` 和自动配置工具 `apply_config.py`，实现从回测到实盘的闭环。
- 🛡️ **动态参数支持**: 实盘机器人支持从 `.env` 加载回测优化后的动态止盈止损和趋势强度参数。
- 📉 **风险看板**: 新增 `data/backtest_summary.csv` 自动汇总所有优化轨迹，直观对比策略表现。
- 🎯 **实战配置**: 预设经过迭代验证的 `opt_iter25` 配置（90% 极高胜率策略）。

### V1.0 (初始版本)
- 基础交易策略实现
- 简单风控机制
- 基本Web界面

## 📚 项目文档

为了帮助您更好地理解和使用本项目，我们提供了详细的文档：

- 📖 **[用户使用手册](docs/USER_GUIDE.md)** - 从环境搭建到高阶使用的完整指南（包含命令行操作）。
- 🚀 **[自动部署指南 (CI/CD)](docs/DEPLOYMENT.md)** - 详细说明如何配置 GitHub Actions 实现全自动部署。
- ⚙️ **[交易参数详解](docs/TRADING_PARAMETERS.md)** - 深入了解策略背后的各项参数设置。
- 🔧 **[CI/CD 故障排查](docs/CICD_TROUBLESHOOTING.md)** - 部署失败时的诊断和修复指南。

## 🚀 快速开始

### 1. 环境准备
确保您的系统已安装 Python 3.8+ 及 Git。

```bash
git clone <repository_url>
cd Headache_trade-1
```

### 2. 一键部署
运行部署脚本初始化环境及依赖：
```bash
./deploy.sh
```

### 3. 配置 API
复制环境配置模板并填入您的 API 密钥：
```bash
cp .env.example .env
nano .env
```
*必需配置项：*
- `DEEPSEEK_API_KEY`: DeepSeek 大模型接口密钥
- `OKX_API_KEY`, `OKX_SECRET`, `OKX_PASSWORD`: OKX 交易所 V5 API

*AI交易团队配置（可选）：*
- `AI_SKILLS_ENABLED=true`: 启用AI交易团队（默认启用）
- `AI_MARKET_ANALYST_ENABLED=true`: 启用市场分析师技能
- `AI_QUANT_STRATEGIST_ENABLED=true`: 启用量化策略专家技能
- `AI_RISK_MANAGER_ENABLED=true`: 启用风险管理专家技能
- `AI_TRADE_EXECUTOR_ENABLED=true`: 启用交易执行专家技能
- `AI_SKILL_TIMEOUT=5.0`: 技能执行超时时间（秒）
- `AI_CIRCUIT_BREAKER_ENABLED=true`: 启用熔断器保护
- `AI_FALLBACK_LEGACY=true`: AI失败时回退到传统策略

### 4. 启动系统
```bash
./run.sh
```
启动成功后：
- 🤖 **交易机器人**将在后台运行 (PID 记录于 `logs/bot.log`)
- 📊 **Web 仪表板**将启动在前台，访问地址：`http://localhost:5000`

## 📁 项目结构 (V3.1)

```text
Headache_trade/
├── run.sh                        # [入口] 系统一键启动脚本
├── deploy.sh                     # [入口] 环境部署脚本
├── restart_bot_safe.sh           # [工具] 安全重启脚本（保护现有持仓）
├── dashboard/                     # [后端] Python Web API 服务
│   ├── app.py                    # Flask应用入口
│   ├── routes/                   # API路由层
│   ├── services/                 # 业务逻辑层
│   └── repositories/             # 数据访问层
├── ai_skills/                    # [新] AI交易团队技能系统
│   ├── __init__.py               # 模块导出
│   ├── base_skill.py             # 基础技能抽象类
│   ├── coordinator.py            # 技能协调层
│   ├── context_manager.py        # 上下文管理器
│   ├── messaging.py              # 消息传递机制
│   ├── config.py                 # AI技能配置
│   ├── adapters.py               # 适配层（数据转换、性能监控）
│   ├── market_analyst.py         # 市场分析师技能
│   ├── quant_strategist.py       # 量化策略专家技能
│   ├── risk_manager.py          # 风险管理专家技能
│   ├── trade_executor.py         # 交易执行专家技能
│   └── README.md                 # AI技能系统使用说明
├── trading_bots/                 # [核心] 交易策略模块
│   ├── main_bot.py               # >>> V3.1 主策略引擎 (集成AI交易团队)
│   ├── risk.py                   # 完善的风控模块
│   ├── execution.py              # 增强的订单执行模块
│   ├── ai_commander.py           # AI 决策引擎（传统模式）
│   ├── signals.py                # 信号生成模块
│   └── indicators.py             # 技术指标计算
├── strategies/                   # [策略] 策略实现模块
│   ├── base_strategy.py          # 策略基类
│   ├── strategy_registry.py      # 策略注册表
│   ├── trend_strategy.py         # 趋势策略
│   ├── grid_strategy.py          # 网格策略
│   └── ...                       # 其他策略实现
├── frontend_dashboard/           # [前端] 现代化 Next.js 前端应用
│   ├── app/                      # Next.js 应用目录
│   │   ├── page.tsx              # 主页面
│   │   ├── layout.tsx            # 全局布局
│   │   └── dashboard/            # 交易仪表板页面
│   ├── components/               # React 组件库
│   │   ├── charts/               # 图表组件（K线、收益曲线等）
│   │   │   └── PerpKlineWithOrders.tsx  # 永续K线与订单展示
│   │   ├── dashboard/            # 仪表板组件
│   │   └── ui/                   # UI 基础组件
│   ├── lib/                      # 工具函数与 API 客户端
│   │   ├── api.ts                # 后端 API 调用
│   │   └── utils.ts              # 辅助函数
│   └── package.json              # Node.js 依赖配置
├── tests/                        # [测试] 测试文件目录
│   ├── test_strategies.py        # 策略测试
│   ├── test_ai_optimization.py   # AI优化测试
│   └── test_adaptive_optimization.py  # 自适应优化测试
├── docs/                         # [文档] 项目文档与优化记录
│   ├── reports/                  # 测试报告
│   ├── frontend/                 # 前端开发文档
│   ├── TRADING_PARAMETERS.md     # 交易参数说明
│   └── USER_GUIDE.md             # 用户使用指南
├── scripts/                      # [工具] 分析与回测工具
│   ├── analyze_backtest_results.py # 自动分析回测数据并汇总结果报告
│   ├── apply_config.py           # 一键应用最佳回测参数至实盘配置
│   ├── backtest_engine.py        # 回测引擎
│   ├── backtest_runner.py        # 回测运行器
│   └── check_status.sh           # 进程状态检测
├── data/                         # [数据] 本地数据存储
│   ├── backtest_summary.csv      # 回测汇总报告
│   ├── dashboard_data.json       # 仪表板数据
│   ├── ai_skills_context.json    # AI技能上下文（自动生成）
│   ├── ai_skills_performance.json # AI技能性能指标（自动生成）
│   ├── guidance.json             # 交易指导数据
│   ├── chart_history.json        # K线历史数据
│   └── backtest/                 # 回测结果存储
├── logs/                         # [日志] 运行日志目录
├── requirements.txt              # Python 依赖配置
├── README.md                     # 项目说明文档
└── venv/                         # Python 虚拟环境
```

## 🎨 前端仪表板

### 技术栈
- **框架**: Next.js 15 + React 18
- **样式**: Tailwind CSS + PostCSS
- **类型**: TypeScript
- **图表**: 自定义高性能 K 线组件

### 主要功能
1. **实时行情展示** - 加密货币行情条，实时更新币种价格与涨跌幅
2. **交易仪表板** - 账户总资产、收益、持仓列表、风险指标一览
3. **K 线图表与订单** - 支持永续期货 K 线实时展示与订单执行标记
4. **交易日志** - 实时展示机器人的交易信号、执行情况、风控事件

### 启动前端
```bash
cd frontend_dashboard
npm install
npm run dev
```
前端将在 `http://localhost:3000` 启动

## 🛠️ 运维管理

### 推荐操作
- **查看实时日志**:
  ```bash
  tail -f logs/bot.log
  ```
- **安全重启 (推荐)**:
  *并在重启前自动备份日志，且不会影响已有持仓*
  ```bash
  ./restart_bot_safe.sh
  ```

### 进程控制
- **手动停止**:
  ```bash
  # 停止交易机器人
  pkill -f main_bot.py
  
  # 停止 Web 仪表板
  pkill -f "dashboard/app.py"
  ```

## 🤖 AI交易团队架构

### 系统架构

```
┌─────────────────────────────────────────┐
│      Skill Coordinator (协调层)        │
│  • 技能调度 • 结果聚合 • 异常熔断      │
└─────────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼───┐ ┌───▼───┐ ┌───▼───┐
│Market │ │Quant │ │ Risk  │ │Trade  │
│Analyst│ │Strat │ │Manager│ │Executor│
└───────┘ └──────┘ └───────┘ └───────┘
```

### 四大AI技能

#### 1. Market Analyst Skill (市场分析师)
- **多时间框架分析**: 支持1m/5m/15m/1h/4h/1d多时间框架技术分析
- **市场情绪分析**: 集成Twitter/Reddit/Telegram情绪指标
- **异常检测**: 价格突变、流动性枯竭、极端波动率检测
- **输出**: 标准化市场状态报告（趋势强度、波动率、情绪得分、异常标志）

#### 2. Quant Strategist Skill (量化策略专家)
- **动态策略选择**: 根据市场状态自动选择最优策略（趋势跟踪/均值回归/套利/机器学习）
- **参数自适应优化**: 基于当前市场状态动态调整策略参数
- **多策略组合**: 支持多策略权重分配和信号置信度评估
- **输出**: 原始交易信号（方向、规模、入场/出场条件）

#### 3. Risk Manager Skill (风险管理专家)
- **动态仓位sizing**: 基于波动率和相关性动态调整仓位大小
- **最大回撤控制**: 单策略/整体组合的最大回撤监控
- **流动性风险评估**: 买卖价差、深度分析
- **黑天鹅事件检测**: 极端行情熔断机制
- **输出**: 风险调整后的最终交易信号

#### 4. Trade Executor Skill (交易执行专家)
- **智能订单路由**: 最优交易所选择（当前支持OKX，可扩展）
- **算法执行**: TWAP/VWAP/冰山订单算法
- **滑点优化**: 动态订单拆分，减少市场冲击
- **执行质量监控**: 实时跟踪执行时间、滑点、成交率
- **输出**: 执行报告（成交记录、性能指标）

### 数据流

```
1. 数据获取 → Market Analyst → 市场状态报告
2. 市场状态 + 历史数据 → Quant Strategist → 原始信号
3. 原始信号 + 组合状态 → Risk Manager → 最终信号
4. 最终信号 + 市场深度 → Trade Executor → 执行结果
5. 执行结果 → 反馈到上下文 → 下一个周期
```

### 核心机制

- **技能协调层**: 统一调度所有技能，管理执行流程
- **上下文管理**: 维护跨技能共享的上下文数据（市场状态、策略信号、风险参数）
- **消息总线**: 支持技能间事件驱动通信
- **熔断保护**: 技能连续失败时自动熔断，防止系统崩溃
- **回退机制**: AI技能失败时自动降级到传统策略，确保系统稳定性
- **性能监控**: 自动记录每个技能的执行时间、成功率等指标

### 配置说明

详细配置说明请参考 [AI技能系统文档](ai_skills/README.md)

## 🎯 策略详情

### 趋势判断标准
系统基于 15 分钟 K 线数据，结合以下指标计算趋势评分 (0-10):
1.  **MA 均线系统**: 多周期排列 (MA7, MA25, MA99)
2.  **MACD**: 零轴位置与金叉/死叉状态
3.  **RSI**: 相对强弱与背离检测
4.  **布林带**: 价格相对位置与开口方向

### 资金管理
- **基础仓位**: 默认 10% 账户权益
- **杠杆倍数**: 3x - 10x (动态调整)
- **调整逻辑**: AI 信心分 > 8 且趋势分 > 7 时触发加仓；ATR 剧烈波动时自动降维。
- **AI增强**: 通过Risk Manager Skill进行动态仓位sizing和风险控制

## 🔒用于生产环境的安全建议
1.  **Key 权限**: OKX API Key 务必仅开启 **"交易"** 与 **"读取"** 权限，**严禁开启"提币"权限**。
2.  **IP 白名单**: 建议将 API Key 绑定服务器 IP。
3.  **日志监控**: 定期检查 `logs/bot.log` 确保运行正常。
4.  **AI技能监控**: 定期检查 `data/ai_skills_performance.json` 监控AI技能执行情况。
5.  **熔断保护**: 确保 `AI_CIRCUIT_BREAKER_ENABLED=true` 启用熔断器保护。
6.  **回退机制**: 建议保持 `AI_FALLBACK_LEGACY=true` 确保AI失败时能回退到传统策略。

## 📄 License & 免责声明
本项目基于 MIT License 开源。
**风险提示**: 加密货币交易具有极高风险，本系统提供的策略与代码仅供参考与学习，作者不对任何交易损失负责。

---
**Headache Trade** - *Let AI handle the headache of trading.*
