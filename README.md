# Crypto DeepSeek - 智能交易系统

基于 DeepSeek AI 的加密货币自动化交易系统，采用"趋势为王，结构修边"的交易理念，提供实时交易分析、策略执行和可视化仪表板。

## ✨ 核心特性

- 🤖 **AI驱动交易决策** - 基于DeepSeek AI的智能市场分析
- 📊 **趋势为王策略** - 量化趋势强度，动态调整仓位和风险
- 🎯 **智能仓位管理** - 根据信心等级和趋势强度自动调整仓位大小
- 🛡️ **动态风控系统** - 实时价格监控，自动止盈止损
- 📈 **可视化仪表板** - 实时查看交易状态、收益曲线和交易记录
- ⚡ **自动化执行** - 15分钟周期自动分析并执行交易

## 🚀 快速开始

### 一键部署（首次使用）
```bash
cd /root/crypto_deepseek
./deploy.sh
```

### 一键启动
```bash
./run.sh
```

这将自动启动：
- 🤖 交易机器人（后台运行）
- 📊 Web仪表板（前台运行）

### 访问界面
- **本地**: http://localhost:5000
- **外网**: http://your-server-ip:5000

## ⚙️ 配置说明

### 1. API 密钥配置
```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

需要配置的 API 密钥：
- `DEEPSEEK_API_KEY` - DeepSeek API密钥（从 https://platform.deepseek.com/ 获取）
- `OKX_API_KEY` - OKX交易所API密钥
- `OKX_SECRET` - OKX交易所密钥
- `OKX_PASSWORD` - OKX交易所密码
- `CRYPTORACLE_API_KEY` - CryptoOracle API（可选）

### 2. 系统要求
- Python 3.8+
- Linux 系统（推荐 Ubuntu 20.04+）
- 网络连接（用于访问 API 和交易所）

## 📁 项目结构

```
crypto_deepseek/
├── deploy.sh                     # 一键部署脚本
├── run.sh                        # 一键启动脚本
├── restart_safe.sh               # 安全重启脚本
├── .env.example                  # 环境变量配置模板
├── .env                          # 实际配置文件（用户创建，不提交到Git）
├── requirements.txt              # Python 依赖包
├── README.md                     # 项目文档
├── trading_dashboard.py          # Web 仪表板
├── trading_bots/
│   └── deepseek_Fluc_reduce_version.py  # 主交易机器人（趋势为王策略）
├── templates/                    # HTML模板
│   ├── login.html               # 登录配置页面
│   └── arena.html              # Arena 交易界面
├── static/                      # 静态文件
│   ├── css/                     # CSS样式文件
│   └── js/                      # JavaScript文件
├── data/                        # 数据文件
│   ├── chart_history.json       # 图表历史数据
│   ├── dashboard_data.json      # 仪表板数据
│   └── initial_balance.json    # 初始余额记录
├── logs/                        # 日志文件
│   ├── bot.log                  # 交易机器人日志
│   └── dashboard.log            # 仪表板日志
├── scripts/                     # 工具脚本
│   ├── check_status.sh          # 状态检查脚本
│   └── test_dashboard.py        # 测试工具
└── venv/                        # Python虚拟环境
```

## 🔐 使用流程

1. **部署系统**: 运行 `./deploy.sh` 完成环境配置
2. **配置 API**: 编辑 `.env` 文件填写 API 密钥
3. **启动系统**: 运行 `./run.sh` 启动服务
4. **访问界面**: 浏览器打开 http://localhost:5000
5. **配置交易**: 在登录页面填写 API 配置
6. **开始交易**: 验证成功后进入 Arena 交易界面

## 🛠️ 管理命令

### 基本操作
```bash
# 部署系统（首次使用）
./deploy.sh

# 启动系统
./run.sh

# 查看交易机器人日志
tail -f logs/bot.log

# 检查系统状态
./scripts/check_status.sh
```

### 进程管理
```bash
# 停止交易机器人
pkill -f deepseek_Fluc_reduce_version.py

# 停止仪表板
pkill -f trading_dashboard.py

# 重启系统（推荐使用安全重启脚本）
./restart_safe.sh

# 或手动重启
pkill -f deepseek_Fluc_reduce_version.py && ./run.sh
```

## 📋 配置要求

### 必需配置
- DeepSeek API Key（用于 AI 分析）
- OKX API Key / Secret / Password（用于交易）

### 可选配置
- CryptoOracle API Key（用于情绪分析，增强交易信号）

## 🔒 安全说明

⚠️ **重要提醒：**
- `.env` 文件包含敏感信息，**绝不会**被上传到 Git
- 所有 API 密钥从环境变量读取
- 建议为 API 密钥设置 IP 白名单
- 定期更换 API 密钥
- 不要在公共场合泄露密钥

## 🐛 故障排除

### 常见问题

1. **部署失败**
   ```bash
   # 检查 Python 版本
   python3 --version
   
   # 手动安装依赖
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **启动失败**
   ```bash
   # 检查配置文件
   cat .env
   
   # 查看错误日志
   tail -f logs/bot.log
   ```

3. **API 连接失败**
   - 检查网络连接
   - 验证 API 密钥是否正确
   - 确认 API 权限设置

## 📚 技术栈

- **后端**: Python 3.8+, Flask
- **AI**: DeepSeek API（智能市场分析）
- **交易**: OKX API (CCXT)
- **数据**: Pandas, NumPy（技术指标计算）
- **前端**: HTML5, CSS3, JavaScript
- **调度**: Schedule（定时任务）

## 🎯 交易策略

### 趋势为王理念
- **趋势强度量化**: 通过多周期均线、MACD、RSI等技术指标量化趋势强度（0-10分）
- **结构修边**: 结合价格结构、布林带位置等优化入场时机
- **智能仓位**: 根据趋势强度和AI信心等级动态调整仓位（0.5x - 1.5x）
- **动态风控**: 基于ATR（平均真实波幅）动态设置止盈止损，实时价格监控

### 交易周期
- **分析周期**: 15分钟K线
- **数据范围**: 24小时历史数据（96根K线）
- **执行频率**: 每15分钟自动分析并执行交易

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

---

🎉 **享受智能交易系统！** 📈🚀