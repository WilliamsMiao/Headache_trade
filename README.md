# Crypto DeepSeek - 智能交易系统

基于 DeepSeek AI 的加密货币自动化交易系统，提供实时交易分析、策略执行和可视化仪表板。

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
├── deploy.sh                     # 🆕 一键部署脚本
├── run.sh                        # 🆕 一键启动脚本
├── .env.example                  # 环境变量配置模板
├── trading_dashboard.py          # Web 仪表板
├── trading_bots/
│   └── deepseek_trading_bot.py   # 主交易机器人
├── templates/
│   ├── login.html               # 登录配置页面
│   └── arena.html              # Arena 交易界面
├── static/                      # 静态文件
├── data/                        # 数据文件
├── logs/                        # 日志文件
├── scripts/
│   ├── check_status.sh          # 状态检查脚本
│   └── test_dashboard.py        # 测试工具
└── requirements.txt             # Python 依赖包
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
pkill -f deepseek_trading_bot.py

# 停止仪表板
pkill -f trading_dashboard.py

# 重启系统
pkill -f deepseek_trading_bot.py && ./run.sh
```

## 📋 配置要求

### 必需配置
- DeepSeek API Key（用于 AI 分析）
- OKX API Key / Secret / Password（用于交易）

### 可选配置
- CryptoOracle API Key（用于情绪分析）
- 钱包地址（用于资金管理）

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
- **AI**: DeepSeek API
- **交易**: OKX API (CCXT)
- **数据**: Pandas, NumPy
- **前端**: HTML5, CSS3, JavaScript

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

---

🎉 **享受智能交易系统！** 📈🚀