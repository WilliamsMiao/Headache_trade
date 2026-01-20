# ✅ CI/CD 部署后检查清单

## 部署完成后必做检查

### 1️⃣ 检查代码是否更新
```bash
cd ~/Headache_trade-1
git log -1  # 查看最新提交
```
**预期结果**: 应该显示你刚才推送的最新提交信息

---

### 2️⃣ 检查虚拟环境
```bash
cd ~/Headache_trade-1
source venv/bin/activate
python --version  # 应该显示 Python 3.x
pip list | grep ccxt  # 检查关键依赖
```
**预期结果**: 虚拟环境激活成功，依赖包已安装

---

### 3️⃣ 检查配置文件
```bash
cat ~/Headache_trade-1/.env | head -5
```
**预期结果**: `.env` 文件存在且包含正确的 API 密钥

---

### 4️⃣ 检查服务是否启动

#### 检查后端服务 (Flask - 端口 5001)
```bash
ps aux | grep "dashboard/app.py" | grep -v grep
netstat -tlnp | grep 5001
curl http://localhost:5001/health  # 如果有健康检查接口
```
**预期结果**: 
- 进程正在运行
- 端口 5001 正在监听
- API 能正常响应

#### 检查前端服务 (Next.js - 端口 3000)
```bash
ps aux | grep "next dev" | grep -v grep
netstat -tlnp | grep 3000
curl http://localhost:3000
```
**预期结果**: 
- 进程正在运行
- 端口 3000 正在监听
- 返回 HTML 内容

---

### 5️⃣ 检查日志文件
```bash
# 查看后端日志（最近20行）
tail -n 20 ~/Headache_trade-1/logs/dashboard.log

# 查看前端日志
tail -n 20 ~/Headache_trade-1/logs/frontend.log

# 检查是否有错误
grep -i error ~/Headache_trade-1/logs/*.log
```
**预期结果**: 
- 日志文件存在
- 没有严重错误信息
- 服务启动日志正常

---

### 6️⃣ 浏览器访问测试
```bash
# 获取服务器IP
curl ifconfig.me
```

然后在浏览器中访问：
- **前端界面**: `http://YOUR_SERVER_IP:3000`
- **后端API**: `http://YOUR_SERVER_IP:5001`

**预期结果**: 
- 页面能正常加载
- 数据能正常显示
- 没有 CORS 或连接错误

---

## 🚨 常见问题自查

### 问题1: 服务没有启动
```bash
# 手动启动前后端服务
cd ~/Headache_trade-1
./start_services.sh

# 查看启动日志
tail -f logs/dashboard.log
tail -f logs/frontend.log
```

### 问题2: 端口被占用
```bash
# 查找占用端口的进程
lsof -i :5001
lsof -i :3000

# 杀死旧进程
pkill -f "dashboard/app.py"
pkill -f "next dev"

# 重新启动
./start_services.sh
```

### 问题3: Node.js 未安装
```bash
# 检查 Node.js
node --version
npm --version

# 如果未安装，安装 Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 安装前端依赖
cd ~/Headache_trade-1/frontend_dashboard
npm install
```

### 问题4: Python 依赖缺失
```bash
cd ~/Headache_trade-1
source venv/bin/activate
pip install -r requirements.txt
```

### 问题5: 防火墙阻止访问
```bash
# Ubuntu/Debian
sudo ufw allow 3000/tcp
sudo ufw allow 5001/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=3000/tcp --permanent
sudo firewall-cmd --add-port=5001/tcp --permanent
sudo firewall-cmd --reload
```

---

## 📊 完整健康检查脚本

创建一个快速检查脚本：

```bash
#!/bin/bash
# 保存为 ~/check_deployment.sh

echo "🔍 开始部署健康检查..."
echo "================================"

# 1. 检查代码版本
echo ""
echo "📝 最新提交:"
cd ~/Headache_trade-1 && git log -1 --oneline

# 2. 检查进程
echo ""
echo "🔄 进程状态:"
if pgrep -f "dashboard/app.py" > /dev/null; then
    echo "✅ 后端进程运行中"
else
    echo "❌ 后端进程未运行"
fi

if pgrep -f "next dev" > /dev/null; then
    echo "✅ 前端进程运行中"
else
    echo "❌ 前端进程未运行"
fi

# 3. 检查端口
echo ""
echo "🌐 端口监听:"
if netstat -tlnp 2>/dev/null | grep -q ":5001"; then
    echo "✅ 端口 5001 (后端) 正在监听"
else
    echo "❌ 端口 5001 (后端) 未监听"
fi

if netstat -tlnp 2>/dev/null | grep -q ":3000"; then
    echo "✅ 端口 3000 (前端) 正在监听"
else
    echo "❌ 端口 3000 (前端) 未监听"
fi

# 4. 检查日志错误
echo ""
echo "📋 最近错误:"
if [ -f ~/Headache_trade-1/logs/dashboard.log ]; then
    ERROR_COUNT=$(grep -i error ~/Headache_trade-1/logs/dashboard.log | tail -n 5 | wc -l)
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "⚠️  后端日志有 $ERROR_COUNT 条错误"
        grep -i error ~/Headache_trade-1/logs/dashboard.log | tail -n 3
    else
        echo "✅ 后端日志无错误"
    fi
else
    echo "⚠️  后端日志文件不存在"
fi

# 5. 网络测试
echo ""
echo "🌍 网络测试:"
SERVER_IP=$(curl -s ifconfig.me)
echo "服务器IP: $SERVER_IP"
echo "前端访问: http://$SERVER_IP:3000"
echo "后端访问: http://$SERVER_IP:5001"

echo ""
echo "================================"
echo "✅ 健康检查完成"
```

使用方法：
```bash
chmod +x ~/check_deployment.sh
~/check_deployment.sh
```

---

## 🎯 完美部署标准

一个成功的部署应该满足：

- ✅ 代码已更新到最新版本
- ✅ 虚拟环境正确配置
- ✅ 所有依赖已安装
- ✅ `.env` 配置文件正确
- ✅ 后端服务运行在端口 5001
- ✅ 前端服务运行在端口 3000
- ✅ 日志无严重错误
- ✅ 浏览器能访问界面
- ✅ API 接口响应正常

---

## 📞 仍有问题？

1. 查看详细日志：`tail -f ~/Headache_trade-1/logs/*.log`
2. 查看进程状态：`ps aux | grep -E "(trading_dashboard|next dev)"`
3. 查看端口占用：`netstat -tlnp | grep -E "(3000|5001)"`
4. 手动重启服务：`cd ~/Headache_trade-1 && ./start_services.sh`
5. 查看系统资源：`top` 或 `htop`

记住：**CI/CD 只负责部署代码和安装依赖，服务启动需要单独执行！**
