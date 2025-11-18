# Headache Trade - 项目结构说明

## 📁 目录结构

```
Headache_trade/
│
├── 📄 README.md                    # 项目主说明文档
├── 📄 requirements.txt             # Python依赖列表
├── 📄 .gitignore                   # Git忽略文件配置
│
├── 📁 config/                      # ⚙️ 配置文件目录
│   ├── config_example.json        # 配置示例（基础版）
│   ├── config_full_example.json   # 配置示例（完整版）
│   └── .env.example               # 环境变量示例
│
├── 📁 trading_bots/                # 🤖 核心交易机器人代码
│   ├── __init__.py
│   │
│   ├── # 核心模块
│   ├── multi_strategy_bot.py      # 主交易程序（多策略）
│   ├── config.py                  # 配置管理器
│   ├── logger.py                  # 日志系统
│   ├── utils.py                   # 工具函数
│   │
│   ├── # AI集成
│   ├── ai_strategy_advisor.py     # AI策略顾问
│   ├── ai_analysis.py             # AI市场分析
│   │
│   ├── # 策略系统
│   ├── strategy_scheduler.py      # 策略调度器（AI增强）
│   ├── strategies/                # 策略实现
│   │   ├── __init__.py
│   │   ├── base_strategy.py       # 策略基类
│   │   ├── grid_strategy.py       # 网格交易策略
│   │   ├── trend_following.py     # 趋势跟随策略
│   │   ├── mean_reversion.py      # 均值回归策略
│   │   ├── breakout.py            # 突破策略
│   │   └── momentum.py            # 动量策略
│   │
│   ├── # 交易管理
│   ├── position_manager.py        # 持仓管理
│   ├── risk_management.py         # 风险管理
│   │
│   ├── # 市场分析
│   ├── market_analyzer.py         # 市场分析器
│   ├── indicators.py              # 技术指标库
│   │
│   ├── # 监控与通知
│   ├── monitoring_panel.py        # 性能监控面板
│   ├── web_dashboard.py           # Web仪表盘
│   ├── dingding_notifier.py       # 钉钉机器人通知
│   │
│   └── # 回测引擎
│       └── backtest_engine.py     # 回测引擎
│
├── 📁 backtest/                    # 📊 回测工具目录
│   ├── fetch_historical_data.py   # 历史数据获取工具
│   ├── auto_fetch_90d.py          # 自动获取90天数据
│   ├── optimized_backtest.py      # 优化版回测（趋势过滤）
│   ├── parameter_optimization.py  # 参数优化工具
│   ├── ultra_fast_backtest.py     # 超快速回测
│   ├── simple_backtest.py         # 简单回测
│   ├── detailed_diagnosis.py      # 详细诊断工具
│   └── diagnose_strategies.py     # 策略诊断工具
│
├── 📁 data/                        # 💾 数据文件目录
│   ├── historical_data_BTC_USDT_15m_90d.csv    # 90天15分钟数据
│   ├── historical_data_BTC_USDT_30d.csv        # 30天1小时数据
│   └── ...                                      # 其他历史数据
│
├── 📁 tests/                       # 🧪 测试文件目录
│   ├── test_all_features.py       # 完整功能测试
│   ├── test_utils.py              # 工具函数测试
│   ├── test_performance_report.json  # 测试报告
│   └── QUICK_START.py             # 快速开始脚本
│
├── 📁 scripts/                     # 🔧 脚本工具目录
│   ├── start.bat                  # Windows启动脚本
│   └── deployment/                # 部署脚本
│       ├── deploy.sh              # 部署脚本
│       ├── restart_safe.sh        # 安全重启脚本
│       └── run.sh                 # 运行脚本
│
├── 📁 templates/                   # 🎨 Web模板目录
│   ├── dashboard.html             # 仪表盘模板
│   ├── arena.html                 # 竞技场模板
│   └── login.html                 # 登录页模板
│
├── 📁 docs/                        # 📚 文档目录
│   ├── README.md                  # 主文档
│   ├── README_FULL.md             # 完整文档
│   ├── QUICK_REFERENCE.md         # 快速参考
│   ├── QUICK_START.md             # 快速入门
│   │
│   ├── # 架构与设计文档
│   ├── ARCHITECTURE.md            # 系统架构说明
│   ├── MULTI_STRATEGY_DESIGN.md   # 多策略设计文档
│   ├── MULTI_STRATEGY_GUIDE.md    # 多策略使用指南
│   ├── MODULAR_GUIDE.md           # 模块化开发指南
│   │
│   ├── # 功能文档
│   ├── AI_INTEGRATION_GUIDE.md    # AI集成指南
│   ├── NEW_FEATURES_GUIDE.md      # 新功能使用指南
│   │
│   ├── # 项目管理文档
│   ├── PROJECT_SUMMARY.md         # 项目总结
│   ├── PROJECT_COMPLETION_v2.md   # 项目完成报告v2
│   ├── CHANGELOG.md               # 更新日志
│   ├── DELIVERY_CHECKLIST.md      # 交付清单
│   ├── FINAL_REPORT.md            # 最终报告
│   │
│   └── # 优化文档
│       ├── OPTIMIZATION_SUMMARY.md     # 优化总结
│       └── LOW_PRIORITY_OPTIMIZATION.md # 低优先级优化项
│
└── 📁 trading_dashboard.py         # 🖥️ 独立仪表盘程序

```

## 📖 核心文件说明

### 🎯 主程序入口
- **`trading_bots/multi_strategy_bot.py`** - 多策略交易机器人主程序
- **`trading_dashboard.py`** - Web监控仪表盘

### ⚙️ 配置文件
- **`config/config_example.json`** - 基础配置示例
- **`config/config_full_example.json`** - 完整配置示例（包含所有策略）
- **`config/.env.example`** - API密钥等敏感信息配置模板

### 📊 回测工具
- **`backtest/optimized_backtest.py`** - 推荐使用，包含趋势过滤和优化的止盈止损
- **`backtest/parameter_optimization.py`** - 参数优化工具
- **`backtest/fetch_historical_data.py`** - 交互式数据获取工具

### 🧪 测试工具
- **`tests/test_all_features.py`** - 完整功能测试脚本
- **`tests/QUICK_START.py`** - 快速入门指南脚本

### 📚 文档
- **`docs/README.md`** - 主文档（从这里开始）
- **`docs/QUICK_START.md`** - 快速入门指南
- **`docs/AI_INTEGRATION_GUIDE.md`** - AI功能使用指南
- **`docs/NEW_FEATURES_GUIDE.md`** - 新功能详细说明

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置
```bash
# 复制配置示例
cp config/config_example.json config/config.json

# 编辑配置文件，填入API密钥
```

### 3. 运行回测
```bash
cd backtest
python optimized_backtest.py
```

### 4. 启动交易（模拟）
```bash
python trading_bots/multi_strategy_bot.py --test
```

### 5. 查看监控面板
```bash
python trading_dashboard.py
# 访问 http://localhost:5000
```

## 🗑️ 已清理的废弃文件

以下文件已被删除：
- `trading_bots/test_*.py` - 旧测试文件（已整合到tests/）
- `trading_bots/bot_modular.py` - 旧版模块化代码
- `trading_bots/deepseek_Fluc_reduce_version.py` - 废弃的旧版本
- `scripts/check_status.sh` - 废弃的状态检查脚本
- `scripts/test_dashboard.py` - 已整合到tests/

## 📝 注意事项

1. **配置文件**：实际的 `config.json` 不应提交到Git（已在.gitignore中）
2. **数据文件**：历史数据CSV文件不应提交到Git（太大）
3. **敏感信息**：API密钥等放在 `.env` 文件中（不提交到Git）
4. **回测数据**：使用 `backtest/fetch_historical_data.py` 下载最新数据

## 🔄 项目更新流程

1. 修改代码 → 运行测试 → 回测验证 → 小仓位实盘测试
2. 新增策略 → 在 `trading_bots/strategies/` 中创建
3. 更新文档 → 在 `docs/` 中更新对应文档
4. 提交代码 → 确保通过 `tests/test_all_features.py`

## 📞 技术支持

查看 `docs/` 目录下的详细文档，或运行：
```bash
python tests/QUICK_START.py
```
