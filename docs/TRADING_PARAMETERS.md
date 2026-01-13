# 交易系统参数说明文档 (TRADING PARAMETERS GUIDE)

本文档详细列出了交易系统（回测与实盘）中的所有可配置参数。这些参数决定了策略的进出场逻辑、风控行为以及系统运行方式。

---

## 1. 策略核心参数 (Strategy Logic)
主要用于决定交易信号的触发条件，位于 `backtest_runner.py` 的配置字典中。

### 1.1 动量指标 (RSI)
用于判断超买超卖及趋势反转。
*   **`rsi_long_min`** (默认: 45): 做多信号的 RSI 下限。低于此值视为动能过弱。
*   **`rsi_long_max`** (默认: 75): 做多信号的 RSI 上限。高于此值视为超买，可能有回调风险。
*   **`rsi_short_min`** (默认: 25): 做空信号的 RSI 下限。
*   **`rsi_short_max`** (默认: 55): 做空信号的 RSI 上限。
*   **`rsi_extreme_high`** (默认: 75): 极端超买阈值，可能触发出场或反向信号。
*   **`rsi_extreme_low`** (默认: 25): 极端超卖阈值。

### 1.2 波动率指标 (ATR & Volatility)
用于判断市场状态（平静/高波）并动态调整止盈止损。
*   **`atr_pct_min`** (默认: 0.005): ATR百分比下限，低于此值视为极低波动。
*   **`atr_pct_max`** (默认: 0.030): ATR百分比上限，高于此值视为剧烈波动。
*   **`atr_high_threshold`** (默认: 0.020): 高波动率阈值，超过此值将使用宽松的止盈止损乘数。
*   **`atr_mid_threshold`** (默认: 0.015): 中等波动率阈值。
*   **`near_level_threshold`** (默认: 0.002): 价格接近支撑/阻力位的判定距离（0.2%）。

### 1.3 资金费率 (Funding Rate)
用于根据市场情绪辅助判断（负费率通常看多，正费率看空）。
*   **`funding_abs_max`** (默认: 0.0003): 资金费率绝对值上限，超过可能暂停交易。
*   **`funding_long_min`** (默认: -0.0001): 做多允许的最小资金费率。
*   **`funding_long_max`** (默认: 0.0002): 做多允许的最大资金费率。
*   **`funding_short_min`** (默认: -0.0002): 做空允许的最小资金费率。
*   **`funding_short_max`** (默认: 0.0001): 做空允许的最大资金费率。

### 1.4 趋势评分
*   **`trend_score_entry`** (默认: 65): DeepSeek 分析给出的最低入场分数（0-100）。

---

## 2. 风险管理参数 (Risk Management)
决定单笔交易的盈亏比和仓位管理。

### 2.1 动态止盈止损 (Dynamic TP/SL)
根据当前波动率 (`ATR`) 自动选择不同的乘数。
*   **高波动环境 (`> atr_high_threshold`)**:
    *   `sl_multiplier_high` (默认: 2.5): 止损距离 ATR 乘数。
    *   `tp_multiplier_high` (默认: 3.0): 止盈距离 ATR 乘数。
*   **中波动环境**:
    *   `sl_multiplier_mid` (默认: 2.0)
    *   `tp_multiplier_mid` (默认: 2.5)
*   **低波动环境**:
    *   `sl_multiplier_low` (默认: 1.8)
    *   `tp_multiplier_low` (默认: 2.2)

### 2.2 资金与杠杆 (Capital & Leverage)
*   **`initial_balance`** (默认: 100): 回测初始资金 (USDT)。
*   **`leverage`** (默认: 6): 交易杠杆倍数。
*   **`fee_rate`** (默认: 0.001): 单边交易手续费率 (0.1%)。
*   **`slippage`** (默认: 0.0001): 预估滑点 (0.01%)。

### 2.3 实盘风控 (Live Trading Specific)
位于 `trading_bots/config.py`。
*   **`base_risk_per_trade`**: 单笔亏损占总资金的百分比 (默认 2%)。
*   **`max_position_drawdown`**: 最大持仓回撤 (默认 3%)。
*   **`target_capital_utilization`**: 目标资金占用率 (默认 50%)。
*   **`PROTECTION_LEVELS`**: 轨道保护机制配置（Defensive/Balanced/Aggressive）。

### 2.4 利润锁定机制 (Lock Stop Loss)
用于在浮盈达到一定程度后，锁定部分利润，防止盈利回撤。
*   **`LOCK_STOP_LOSS_PROFIT_THRESHOLD`**: 触发利润锁定的最低浮盈比例 (如 0.01 即 1%)。
*   **`LOCK_STOP_LOSS_BUFFER`**: 锁定利润时的缓冲距离。
*   **`LOCK_STOP_LOSS_RATIO`**: 默认锁定比例。
*   **`LOCK_STOP_LOSS_RATIOS`**: 不同阶段的锁定比例配置。

---

## 3. 系统配置参数 (System Configuration)
决定机器人运行的基础环境。

*   **Symbol**: 交易对 (如 `BTC/USDT`).
*   **Timeframe**: K线周期 (如 `15m`).
*   **Contract Size**: 合约面值 (OKX BTC 通常为 0.01).
*   **Orbit Update Interval**: 保护逻辑更新频率 (秒)。

---

## 4. 可扩展参数区域 (Future Extensions)
在此预留未来可能加入的策略参数插槽，方便开发时直接取用。

### 4.1 趋势跟踪扩展 (Trend Following)
*   [ ] `ma_fast_period`: 快速移动平均周期 (如 9)。
*   [ ] `ma_slow_period`: 慢速移动平均周期 (如 21)。
*   [ ] `macd_signal_threshold`: MACD 柱线信号阈值。

### 4.2 动量增强 (Momentum)
*   [ ] `bollinger_width_threshold`: 布林带带宽阈值（用于过滤盘整）。
*   [ ] `volume_spike_multiplier`: 成交量突增倍数（用于确认突破）。

### 4.3 市场情绪 (Sentiment)
*   [ ] `sentiment_score_min`: AI 分析的新闻情绪最低分。
*   [ ] `long_short_ratio_limit`: 多空持仓比限制。

### 4.4 高级风控 (Advanced Risk)
*   [ ] `max_daily_trades`: 单日最大交易次数限制。
*   [ ] `trailing_stop_activation_pnl`: 移动止损激活的收益率门槛。
*   [ ] `time_based_exit_hours`: 持仓超过 X 小时强制平仓。

---

**使用指南:**
1.  **回测调参**: 修改 JSON 配置文件或 `scripts/backtest_runner.py` 中的 `config` 字典。
2.  **实盘配置**: 修改 `.env` 文件或 `trading_bots/config.py` 中的环境变量默认值。
