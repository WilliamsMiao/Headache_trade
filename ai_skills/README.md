# AI交易团队技能系统

## 概述

AI交易团队技能系统是一个多Agent协作的量化交易架构，通过四个专业AI技能（市场分析师、量化策略专家、风险管理专家、交易执行专家）协同工作，提供更智能、更全面的交易决策。

## 架构

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

## 核心组件

### 1. Market Analyst Skill (市场分析师)
- **功能**: 多时间框架技术分析、市场情绪分析、异常检测
- **输入**: 原始市场数据
- **输出**: 标准化市场状态报告

### 2. Quant Strategist Skill (量化策略专家)
- **功能**: 动态策略选择、参数优化、信号生成
- **输入**: 市场分析报告
- **输出**: 原始交易信号

### 3. Risk Manager Skill (风险管理专家)
- **功能**: 动态仓位sizing、最大回撤控制、流动性风险评估、黑天鹅检测
- **输入**: 原始交易信号、市场分析
- **输出**: 风险调整后的交易信号

### 4. Trade Executor Skill (交易执行专家)
- **功能**: 智能订单路由、算法执行（TWAP）、滑点优化
- **输入**: 风险调整后的信号
- **输出**: 执行报告

## 配置

通过环境变量配置AI技能系统：

```bash
# 启用/禁用AI技能系统
AI_SKILLS_ENABLED=true

# 技能开关
AI_MARKET_ANALYST_ENABLED=true
AI_QUANT_STRATEGIST_ENABLED=true
AI_RISK_MANAGER_ENABLED=true
AI_TRADE_EXECUTOR_ENABLED=true

# 技能超时时间（秒）
AI_SKILL_TIMEOUT=5.0

# 熔断器配置
AI_CIRCUIT_BREAKER_ENABLED=true
AI_CIRCUIT_BREAKER_THRESHOLD=5
AI_CIRCUIT_BREAKER_RESET=300

# 回退机制
AI_FALLBACK_LEGACY=true
```

## 使用方式

系统会自动集成到主交易循环中。如果AI技能系统启用，主循环会优先使用AI团队进行决策；如果失败或未启用，会自动回退到传统策略。

## 数据流

1. **数据获取** → Market Analyst → 市场状态报告
2. **市场状态** → Quant Strategist → 原始交易信号
3. **原始信号** → Risk Manager → 风险调整后的信号
4. **最终信号** → Trade Executor → 执行结果
5. **执行结果** → 反馈到上下文 → 下一个周期

## 性能监控

系统会自动记录每个技能的执行时间、成功率等指标，保存在 `data/ai_skills_performance.json`。

## 上下文管理

共享上下文保存在 `data/ai_skills_context.json`，包含：
- 市场状态
- 策略信号历史
- 风险参数
- 持仓信息
- 性能指标

## 消息总线

技能间通过消息总线进行通信，支持事件驱动的协作模式。

## 回退机制

- 每个技能都有独立的开关
- 技能失败时自动降级到传统策略
- 熔断器防止连续失败
- 保留现有系统作为备用

## 注意事项

1. 首次使用前确保所有依赖已安装
2. 建议先在测试模式（`BOT_TEST_MODE=true`）下运行
3. 监控性能指标，根据实际情况调整配置
4. 保持传统策略系统可用，作为备用
