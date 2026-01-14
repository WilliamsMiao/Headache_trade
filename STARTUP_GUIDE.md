# 🚀 Headache Trade V2 启动指南

## 📋 脚本用途一览表

| 脚本名 | 用途 | 使用场景 | 推荐度 |
|--------|------|----------|--------|
| `./deploy.sh` | 🔧 **一键部署安装** | 首次部署或重新安装环境 | ⭐⭐⭐⭐⭐ |
| `./start_services.sh` | 🌐 **启动前端+后端服务** | 启动Web界面和API服务 | ⭐⭐⭐⭐⭐ |
| `./run.sh` | 🤖 **启动交易Bot** | 启动自动化交易机器人 | ⭐⭐⭐⭐⭐ |
| `./restart_bot_safe.sh` | 🔄 **安全重启Bot** | 重启交易Bot，保留持仓 | ⭐⭐⭐⭐ |
| `./scripts/check_status.sh` | ✅ **检查系统状态** | 诊断服务运行状态 | ⭐⭐⭐ |

---

## 🎯 快速启动流程（新手必看）

### 第一步：首次部署（只需执行一次）
```bash
./deploy.sh
```
**这个脚本会做什么？**
- ✅ 创建 Python 虚拟环境 (venv)
- ✅ 安装所有 Python 依赖包
- ✅ 安装 Node.js 依赖包
- ✅ 创建配置文件模板 (.env)
- ✅ 初始化日志目录

**完成后需要做：**
1. 编辑 `.env` 文件，填入你的 API 密钥
   ```bash
   nano .env  # 或使用其他编辑器
   ```

---

### 第二步：启动系统

#### 方案A：只启动 Web 界面（推荐日常使用）
```bash
./start_services.sh
```
**会启动：**
- 🌐 Flask 后端服务 (端口 5001)
- 🖥️ Next.js 前端界面 (端口 3000)

**访问地址：**
- 前端界面：http://localhost:3000
- 后端API：http://localhost:5001

**适用场景：**
- 查看交易数据和图表
- 运行回测
- 调整交易参数
- 查看日志

---

#### 方案B：启动实盘交易 Bot
```bash
./run.sh
```
**会启动：**
- 🤖 交易机器人主程序
- 📊 自动执行交易策略
- 🛡️ 实时风险管理

**⚠️ 注意：**
- 启动前确保已配置好 OKX API 密钥
- 建议先在测试环境运行
- 会开始实际交易操作

---

#### 方案C：完整系统（Web + 交易Bot）
```bash
# 先启动 Web 服务
./start_services.sh

# 然后在另一个终端启动交易 Bot
./run.sh
```

---

## 🔧 常用操作

### 重启交易 Bot（不影响持仓）
```bash
./restart_bot_safe.sh
```
- ✅ 会先检查当前持仓和订单
- ✅ 安全停止旧进程
- ✅ 启动新进程
- ✅ 不会取消现有订单或平仓

### 检查系统状态
```bash
./scripts/check_status.sh
```
- 显示进程运行状态
- 显示端口监听状态
- 检查网络连接
- 显示外网访问地址

### 停止所有服务
```bash
# 停止 Web 服务
pkill -f "trading_dashboard.py"
pkill -f "next dev"

# 停止交易 Bot
pkill -f "main_bot.py"
```

---

## 📁 日志文件位置

```
logs/
├── dashboard.log        # 后端API日志
├── frontend.log         # 前端开发日志
├── bot_YYYYMMDD.log    # 交易Bot日志
└── backtest_YYYYMMDD.log # 回测日志
```

查看实时日志：
```bash
# 查看后端日志
tail -f logs/dashboard.log

# 查看交易Bot日志
tail -f logs/bot_*.log
```

---

## ❓ 常见问题

### Q1: 部署时遇到权限问题？
```bash
chmod +x *.sh
chmod +x scripts/*.sh
```

### Q2: Python 虚拟环境激活失败？
```bash
# 手动激活
source venv/bin/activate

# 或重新部署
./deploy.sh
```

### Q3: 端口被占用？
```bash
# 查找占用端口的进程
lsof -i :5001
lsof -i :3000

# 杀死进程
kill -9 <PID>
```

### Q4: 忘记哪个脚本是干什么的？
看本文档最上方的 **脚本用途一览表** 😊

### Q5: 在服务器上启动了但无法通过公网访问前端？
```bash
# 1. 确认服务运行中
ps aux | grep -E "(trading_dashboard|next dev)" | grep -v grep

# 2. 确认端口监听
netstat -tlnp | grep -E "(3000|5001)"

# 3. 检查防火墙（以 iptables 为例）
sudo iptables -L -n | grep -E "(3000|5001)"

# 4. 开放端口（如需要）
sudo ufw allow 3000/tcp
sudo ufw allow 5001/tcp

# 5. 查看前端日志找到具体错误
tail -f logs/frontend.log

# 6. 如果提示 "next: not found"，说明前端依赖未安装
cd frontend_dashboard && npm install && cd ..
```

**云服务商配置** (阿里云/腾讯云/AWS等):
- 进入安全组/防火墙设置
- 添加入站规则：允许端口 3000 和 5001
- 使用**公网IP**而不是localhost访问

---

## 🎓 推荐启动顺序

**新用户（第一次使用）：**
1. `./deploy.sh` - 部署环境
2. 编辑 `.env` 配置文件
3. `./start_services.sh` - 启动 Web 界面
4. 通过浏览器熟悉界面
5. 运行几次回测测试参数
6. `./run.sh` - 开启实盘交易（可选）

**老用户（日常使用）：**
1. `./start_services.sh` - 启动 Web 界面
2. `./run.sh` - 启动交易Bot（如需自动交易）

**需要更新代码后：**
1. 停止所有服务
2. `git pull` 拉取最新代码
3. `./deploy.sh` - 重新部署（更新依赖）
4. 重新启动服务

---

## 💡 最佳实践

1. **使用 tmux 或 screen 管理后台服务**
   ```bash
   # 创建会话
   tmux new -s trading
   
   # 启动服务
   ./start_services.sh
   
   # 分离会话：Ctrl+B 然后按 D
   # 重新连接：tmux attach -t trading
   ```

2. **定期备份配置和数据**
   ```bash
   cp .env .env.backup
   cp -r data data_backup_$(date +%Y%m%d)
   ```

3. **监控日志文件大小**
   ```bash
   # 定期清理旧日志
   find logs -name "*.log" -mtime +30 -delete
   ```

---

## 📞 需要帮助？

- 📖 查看 [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - 详细用户指南
- 🚀 查看 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - 部署文档
- ⚙️ 查看 [docs/TRADING_PARAMETERS.md](docs/TRADING_PARAMETERS.md) - 参数说明
- 🔧 查看 [docs/CICD_TROUBLESHOOTING.md](docs/CICD_TROUBLESHOOTING.md) - 故障排查

---

**总结：记住这三个最重要的命令！**
```bash
./deploy.sh           # 部署（只需一次）
./start_services.sh   # 启动Web界面（前端3000 + 后端5001）
./run.sh              # 启动交易Bot（自动交易）
```

---

## 🔄 重要更新说明 (2026-01-14)

项目已从单体应用（端口5000）升级为**前后端分离架构**：

| 变化 | 旧版本 | 新版本 |
|------|--------|--------|
| **前端** | Flask 模板 (端口5000) | Next.js (端口3000) ✨ |
| **后端** | 同上 | Flask API (端口5001) ✨ |
| **启动命令** | `./run.sh` 启动所有 | `./start_services.sh` 启动Web<br>`./run.sh` 仅启动Bot |

**如果你是老用户**：请更新浏览器书签到 `http://localhost:3000`

详见：[SCRIPTS_UPDATE_LOG.md](docs/SCRIPTS_UPDATE_LOG.md)
