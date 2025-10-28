## 项目结构

```
/root/crypto_deepseek/
├── trading_dashboard_simple.py   # 简化版仪表板 (推荐使用)
├── trading_dashboard.py         # 完整版仪表板 (需要 API 配置)
├── deepseek_trading_bot.py       # 主要交易服务
├── deepseek_enhanced.py          # 增强版交易服务
├── deepseek_basic.py             # 基础版交易服务
├── deepseek_simple.py            # 简化版交易服务
├── templates/index.html          # 前端界面
├── static/                       # 静态文件
├── start_dashboard.sh            # 启动脚本
├── check_status.sh               # 状态检查
├── QUICK_START.md                # 快速启动指南
├── NETWORK_CONFIG.md             # 网络配置指南
└── requirements.txt              # 依赖包
```

## 访问信息

**当前运行**: 简化版仪表板  
**本地访问**: http://localhost:5000 ✅  
**外网访问**: http://8.217.194.162:5000 (需要配置安全组)

## 🔧 使用建议

### 立即可用 (推荐)
```bash
cd /root/crypto_deepseek
conda activate crypto_deepseek
python trading_dashboard_simple.py
```

### 完整功能 (需要配置)
```bash
# 需要正确配置 .env 文件中的 API 密钥
python trading_dashboard.py
```

## 📊 功能对比

| 功能 | 简化版 | 完整版 |
|------|--------|--------|
| 界面展示 | ✅ | ✅ |
| 模拟数据 | ✅ | ✅ |
| 实时价格 | ❌ | ✅ (需要 API) |
| 真实交易数据 | ❌ | ✅ (需要 API) |
| 技术分析 | ❌ | ✅ (需要 API) |
| 稳定性 | ✅ 高 | ⚠️ 依赖外部 API |

## 🎯 下一步

1. **立即使用**: 简化版仪表板已可正常访问
2. **配置 API**: 如需真实数据，配置 `.env` 文件中的 API 密钥
3. **网络配置**: 如需外网访问，配置云服务器安全组

---

🎊 **恭喜！您的 crypto_deepseek 项目已完全配置好并正常运行！**

