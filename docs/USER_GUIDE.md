# Headache Trade V2.0 使用者指南 (User Guide)

欢迎使用 **Headache Trade V2.0**。本指南将带您从零开始，逐步掌握如何部署、回测、优化及运行这个基于 AI 驱动的自动化交易系统。

---

## 📖 目录
1. [快速入门](#1-快速入门-quick-start)
2. [环境配置与部署](#2-环境配置与部署)
3. [回测与策略优化](#3-回测与策略优化)
4. [实盘交易与安全](#4-实盘交易与安全)
5. [可视化监控 (Web Dashboard)](#5-可视化监控)
6. [命令行操作指导 (CLI Reference)](#6-命令行操作指导)

---

## 1. 快速入门 (Quick Start)

只需三步，即可让系统跑起来：

1.  **初始化环境**:
    ```bash
    ./deploy.sh
    ```
2.  **设置密钥**:
    编辑 `.env` 文件，填入您的 OKX API 和 DeepSeek API Key。
3.  **启动系统**:
    ```bash
    ./run.sh
    ```
    启动后，访问 `http://localhost:5000` 查看实时监控界面。

---

## 2. 环境配置与部署

### 2.1 依赖安装
系统需要 Python 3.8+。建议在 Linux 或 macOS 上运行。`deploy.sh` 脚本会自动：
- 创建虚拟环境 (`venv`)
- 安装 `requirements.txt` 中的所有量化库（pandas, ta-lib, ccxt 等）
- 初始化必要的目录结构（logs, data, configs）

### 2.2 配置文件 (.env)
这是系统的核心安全文件。**切勿上传到 GitHub!**
- `OKX_API_KEY / SECRET / PASSWORD`: OKX 交易所凭证（建议申请仅限交易权限的 Key）。
- `DEEPSEEK_API_KEY`: 用于 AI 策略分析和自动参数优化的密钥。
- `TELEGRAM_BOT_TOKEN / CHAT_ID`: (可选) 用于接收实盘交易通知。

---

## 3. 回测与策略优化

在进入实盘之前，您**必须**通过回测验证策略。

### 3.1 运行基础回测
使用历史数据测试当前配置：
```bash
export PYTHONPATH=$PYTHONPATH:.
python scripts/backtest_runner.py --data-file data/backtest/historical_15m_14d.json
```

### 3.2 使用 AI 自动优化 (V2.0 亮点)
V2.0 引入了 AI 反馈循环，机器人可以根据回测结果自动改进自己：
```bash
python scripts/backtest_runner.py --config opt_iter24 --ai-feedback --data-file data/backtest/historical_15m_14d.json
```
- `--ai-feedback`: 开启 AI 分析，回测结束后会生成新的配置文件。
- 优化记录会保存在 `data/backtest/reports/` 目录下。

---

## 4. 实盘交易与安全

### 4.1 启动实盘
实盘机器人运行在后台：
```bash
nohup python trading_bots/main_bot.py > logs/bot.log 2>&1 &
```
*(注意：使用 `run.sh` 会自动处理这些操作)*

### 4.2 安全重启
如果您修改了策略，请使用安全重启脚本。它会确保在不打断持仓处理逻辑的情况下重启进程：
```bash
./restart_bot_safe.sh
```

### 4.3 风险控制
- **止损 (Stop Loss)**: 系统基于 ATR 自动设置硬性止损。
- **保护模式**: 如果市场波动超过 `atr_pct_max`，系统会自动进入防守模式，停止开新仓。

---

## 5. 可视化监控 (Web Dashboard)

启动 Dashboard 服务（`python -m dashboard` 或 `./start_services.sh`）后，您可以通过浏览器实时监控：
- **账户概览**: 实时显示账户余额、可用保证金。
- **持仓状态**: 展示当前持仓的入场价、强平价、未实现盈亏。
- **实时日志**: 无需终端，直接在网页查看机器人的决策逻辑。
- **收益曲线**: 基于回测和实盘记录生成的资产走势图。

---

## 6. 命令行操作指导 (CLI Reference)

以下是日常运维中最常用的命令汇总：

| 任务 | 命令 |
| :--- | :--- |
| **一键部署** | `./deploy.sh` |
| **一键启动 (Bot + Web)** | `./run.sh` |
| **安全重启机器人** | `./restart_bot_safe.sh` |
| **查看机器人日志** | `tail -f logs/bot.log` |
| **查看 Web 服务日志** | `tail -f logs/dashboard.log` |
| **运行 AI 优化回测** | `python scripts/backtest_runner.py --ai-feedback` |
| **手动停止所有进程** | `pkill -f main_bot.py && pkill -f "dashboard/app.py"` |
| **检查系统运行状态** | `./scripts/check_status.sh` |

---

## 💡 开发建议
- **先回测，后实盘**：回测期望值（Expectancy）为正之前，不要实盘。
- **观察 AI 分数**：在日志中关注 `trend_score`，这是判断趋势强度的关键。
- **备份配置**：`data/backtest/configs/` 中的优化结果是宝贵的财富，定期备份。

---
**Headache Trade** - *让 AI 处理交易的烦恼。*
