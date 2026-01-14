# 🔧 服务器部署修复指南

## 问题分析

你在服务器上启动前端时遇到了以下问题：
- ✅ 后端服务成功启动 (端口5001)
- ✅ 前端服务成功启动 (端口3000)  
- ❌ 但无法通过**公网地址**访问前端

**根本原因**：
- 前端输出信息只显示 `127.0.0.1:3000`（localhost），用户误以为只能本地访问
- 实际上前端已经配置了 `--hostname 0.0.0.0`，可以通过公网访问
- 问题可能是防火墙或云服务商安全组阻止了访问

---

## 🛠️ 已修复内容

### 1. **改进 `start_services.sh` 输出信息**
```bash
# 旧输出
Frontend: http://127.0.0.1:3000 (logs: /root/Headache_trade-1/logs/frontend.log)

# 新输出
========================================
🎉 Services started successfully!

📍 本地访问地址 (Local):
   后端API: http://127.0.0.1:5001
   前端界面: http://127.0.0.1:3000

🌐 公网访问地址 (Public):
   查询公网IP: curl ifconfig.me
   后端API: http://<你的服务器IP>:5001
   前端界面: http://<你的服务器IP>:3000

📋 日志文件位置:
   后端日志: /root/Headache_trade-1/logs/dashboard.log
   前端日志: /root/Headache_trade-1/logs/frontend.log

🔧 故障排查:
   1. 检查端口: netstat -tlnp | grep -E '(3000|5001)'
   2. 检查防火墙: sudo ufw status
   3. 检查Next.js: ps aux | grep 'next dev'
========================================
```

### 2. **新增诊断脚本** `scripts/diagnose_frontend.sh`
```bash
./scripts/diagnose_frontend.sh
```
这个脚本会自动检查：
- ✅ Node.js 和 npm 是否安装
- ✅ 前端依赖是否完整
- ✅ 端口 3000/5001 是否正在监听
- ✅ 防火墙是否允许这些端口
- ✅ 显示你的公网 IP 地址
- ✅ 显示完整的访问地址

### 3. **更新文档** `STARTUP_GUIDE.md`
添加了常见问题 Q5：在服务器上启动但无法通过公网访问前端的解决方案

---

## 🚀 部署步骤

在你的服务器上执行以下命令：

### 方案 A：一键快速部署（推荐）
```bash
cd ~/Headache_trade-1

# 拉取最新代码
git pull origin main

# 停止旧服务
pkill -f "trading_dashboard.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

# 确保前端依赖已安装
cd frontend_dashboard
npm install  # 如果已安装可以跳过
cd ..

# 启动新服务
./start_services.sh
```

### 方案 B：使用脚本自动部署
```bash
cd ~/Headache_trade-1
chmod +x SERVER_DEPLOY.sh
./SERVER_DEPLOY.sh
```

---

## 📋 部署后检查清单

### 1. 运行诊断脚本
```bash
./scripts/diagnose_frontend.sh
```
应该看到：
- ✅ Node.js 已安装
- ✅ npm 已安装  
- ✅ Next.js 已安装
- ✅ 端口 3000 正在监听
- ✅ 端口 5001 正在监听
- ✅ 防火墙规则（如有）

### 2. 查看实时日志
```bash
# 后端日志
tail -f logs/dashboard.log

# 前端日志（另一个终端）
tail -f logs/frontend.log
```

### 3. 测试连接
```bash
# 本地连接
curl http://127.0.0.1:3000

# 公网连接（使用你的实际IP）
curl http://<你的服务器IP>:3000
```

### 4. 浏览器访问
获取公网 IP：
```bash
curl ifconfig.me
```

然后在浏览器访问：
```
http://<你的服务器IP>:3000
```

---

## 🔒 防火墙配置

### Ubuntu (UFW)
```bash
# 查看防火墙状态
sudo ufw status

# 启用防火墙（如果未启用）
sudo ufw enable

# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 允许应用端口
sudo ufw allow 3000/tcp  # 前端
sudo ufw allow 5001/tcp  # 后端API

# 验证
sudo ufw status numbered
```

### 云服务商（阿里云/腾讯云/AWS）
需要在云服务商后台配置**安全组**：
1. 进入 ECS 实例/服务器管理
2. 找到"安全组"或"防火墙"设置
3. 添加入站规则：
   - 协议：TCP
   - 端口：3000（前端）
   - 来源：0.0.0.0/0（允许所有IP）
4. 重复步骤 3，添加端口 5001（后端）
5. 保存配置

---

## 🐛 常见问题解决

### 问题1: 端口被占用
```bash
# 查找占用端口的进程
lsof -i :3000
lsof -i :5001

# 杀死进程
kill -9 <PID>

# 重新启动服务
./start_services.sh
```

### 问题2: Next.js 找不到
```bash
# 安装前端依赖
cd frontend_dashboard
npm install
cd ..

# 重新启动
./start_services.sh
```

### 问题3: 防火墙阻止
```bash
# 查看防火墙状态
sudo ufw status

# 允许端口
sudo ufw allow 3000/tcp
sudo ufw allow 5001/tcp

# 重新启动服务
./start_services.sh
```

### 问题4: 前端显示"连接被拒绝"
```bash
# 检查后端是否运行
ps aux | grep trading_dashboard

# 查看后端日志
tail -f logs/dashboard.log

# 如果后端未启动，手动启动
python3 trading_dashboard.py > logs/dashboard.log 2>&1 &
```

---

## 📊 完整架构图

```
互联网用户 (你的浏览器)
    ↓
公网 IP:3000
    ↓
服务器防火墙 (允许 3000 和 5001)
    ↓
Next.js 前端 (端口 3000)
    ↓
Flask 后端API (端口 5001)
    ↓
交易机器人 (可选)
    ↓
OKX 交易所 API
```

---

## ✅ 验证部署成功

部署完成后，你应该能够：

1. **本地访问**（服务器上执行）
   ```bash
   curl http://127.0.0.1:3000  # 应该返回 HTML
   curl http://127.0.0.1:5001  # 应该返回 JSON
   ```

2. **公网访问**（任何地方）
   ```
   http://<你的服务器IP>:3000  # 看到前端界面
   ```

3. **查看日志**（无错误信息）
   ```bash
   tail logs/frontend.log
   tail logs/dashboard.log
   ```

4. **进程正在运行**
   ```bash
   ps aux | grep -E "(next dev|trading_dashboard)"
   ```

---

## 📞 需要进一步帮助？

1. **运行诊断脚本**获取详细信息
   ```bash
   ./scripts/diagnose_frontend.sh
   ```

2. **查看完整文档**
   - [STARTUP_GUIDE.md](../STARTUP_GUIDE.md) - 启动指南
   - [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) - 部署文档
   - [docs/DEPLOYMENT_CHECKLIST.md](../docs/DEPLOYMENT_CHECKLIST.md) - 检查清单

3. **检查日志输出**
   ```bash
   tail -100 logs/frontend.log
   tail -100 logs/dashboard.log
   ```

4. **GitHub 提交记录**
   查看最新的提交信息了解最新修改

---

## 修复总结

| 项目 | 旧状态 | 新状态 |
|------|--------|--------|
| 启动输出 | 只显示 localhost | 显示本地+公网地址 ✨ |
| 故障排查 | 无指导 | 输出包含排查建议 ✨ |
| 诊断工具 | 无 | 新增 diagnose_frontend.sh ✨ |
| 文档 | 无针对性指导 | 添加服务器部署详细说明 ✨ |
| 防火墙配置 | 无说明 | 文档包含详细配置 ✨ |

**修复日期**: 2026-01-14  
**GitHub 提交**: `🐛 修复: 前端无法通过公网访问的问题`
