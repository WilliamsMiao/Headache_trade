# Crypto DeepSeek - 智能交易系统

基于 DeepSeek AI 的加密货币自动化交易系统，提供实时交易分析、策略执行和可视化仪表板。

## 🚀 快速开始

### 方法1：一键启动（推荐）
```bash
cd /root/crypto_deepseek
./start.sh
```

这将自动启动：
- 🤖 交易机器人（后台运行）
- 📊 Web仪表板（前台运行）

### 方法2：单独启动服务
```bash
# 只启动仪表板
python trading_dashboard.py

# 只启动交易机器人
python trading_bots/deepseek_trading_bot.py
```

### 访问界面
- **本地**: http://localhost:5000
- **外网**: http://8.217.194.162:5000

## ⚙️ 安装配置

### 1. 克隆项目
```bash
git clone https://github.com/WilliamsMiao/Headache_trade.git
cd Headache_trade
```

### 2. 创建虚拟环境
```bash
python3 -m venv myenv
source myenv/bin/activate  # Linux/Mac
# 或者
myenv\Scripts\activate     # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置API密钥
```bash
cp .env.example .env
nano .env  # 填写你的API密钥
```

需要配置：
- `DEEPSEEK_API_KEY` - DeepSeek API密钥
- `OKX_API_KEY` - OKX交易所API密钥
- `OKX_SECRET` - OKX交易所密钥
- `OKX_PASSWORD` - OKX交易所密码
- `CRYPTORACLE_API_KEY` - CryptoOracle API（可选）

## 📁 项目结构

```
crypto_deepseek/
├── start.sh                     # 🆕 一键启动脚本
├── .env.example                 # 配置模板
├── trading_dashboard.py         # 主仪表板（带登录）
├── trading_bots/
│   ├── deepseek_trading_bot.py  # 主要交易机器人
│   ├── deepseek_enhanced.py     # 增强版
│   ├── deepseek_basic.py        # 基础版
│   └── deepseek_simple.py       # 简化版
├── templates/
│   ├── login.html               # 登录配置页面
│   └── arena.html              # Arena 交易界面
├── scripts/                     # 辅助脚本
├── static/                      # 静态文件
└── requirements.txt             # 依赖包
```

## 🔐 使用流程

1. **访问登录页面**: 填写 API 配置
2. **验证连接**: 系统自动验证 OKX 交易所
3. **进入 Arena**: 验证成功后访问交易仪表板
4. **监控交易**: 查看实时数据和性能

## 📋 配置要求

- DeepSeek API Key
- OKX API Key / Secret / Password
- 钱包地址（可选）

## 🔒 安全说明

⚠️ **重要提醒：**
- `.env` 文件包含敏感信息，**绝不会**被上传到Git
- 所有API密钥从环境变量读取
- 建议为API密钥设置IP白名单
- 定期更换API密钥

## 🛠️ 脚本工具

- `start.sh` - 🆕 一键启动完整系统
- `scripts/start_dashboard.sh` - 单独启动仪表板
- `scripts/check_status.sh` - 检查服务状态
- `scripts/test_login.sh` - 测试登录功能

## 📚 相关文档

- `GITHUB_PUSH_GUIDE.md` - GitHub推送指南
- `部署完成总结.md` - 部署说明
- `OKX账户升级指南.md` - OKX配置指南

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

---

🎉 **享受智能交易系统！** 📈🚀

