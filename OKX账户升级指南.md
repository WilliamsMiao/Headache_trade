# OKX账户模式升级指南

## 问题诊断结果

您的交易机器人无法执行交易的原因已找到：

**错误代码：51010**
**错误信息：** "You can't complete this request under your current account mode."

**根本原因：** 账户处于"简单交易模式"（acctLv=1），该模式不支持合约交易

---

## 解决方案：升级到统一账户模式

### 步骤1：登录OKX网站

1. 访问 https://www.okx.com
2. 登录您的账户（UID: 769054618755437881）

### 步骤2：切换到统一账户模式

#### 方法A：通过账户设置（推荐）

1. 点击右上角头像 → **账户** → **账户模式**
2. 选择 **"统一账户"模式**（Multi-currency Margin Mode）
3. 阅读并同意风险提示
4. 点击**确认升级**

#### 方法B：通过交易页面

1. 进入 **衍生品交易** → **永续合约**
2. 系统会提示您升级账户模式
3. 点击**升级到统一账户**
4. 完成升级流程

### 步骤3：验证升级是否成功

升级完成后，运行以下命令验证：

```bash
cd /root/crypto_deepseek
source myenv/bin/activate
python -c "
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()
exchange = ccxt.okx({
    'apiKey': os.getenv('OKX_API_KEY'),
    'secret': os.getenv('OKX_SECRET'),
    'password': os.getenv('OKX_PASSWORD'),
})

config = exchange.private_get_account_config()
acct_lv = config['data'][0]['acctLv']
print(f'当前账户级别: {acct_lv}')
if acct_lv == '3':
    print('✅ 统一账户模式已激活，可以交易合约了！')
elif acct_lv == '2':
    print('✅ 单币种保证金模式已激活，可以交易合约')
else:
    print('❌ 仍然是简单模式，请重新升级')
"
```

### 步骤4：重启交易机器人

```bash
# 停止当前机器人
pkill -f deepseek_trading_bot

# 重启机器人（已自动使用-u参数开启详细日志）
cd /root/crypto_deepseek
source myenv/bin/activate
nohup python -u trading_bots/deepseek_trading_bot.py > /tmp/trading_bot.log 2>&1 &

# 查看日志
tail -f /tmp/trading_bot.log
```

---

## 关于不同账户模式的说明

| 账户模式 | acctLv | 支持合约 | 特点 |
|---------|--------|---------|------|
| 简单交易模式 | 1 | ❌ | 只能现货交易 |
| 单币种保证金 | 2 | ✅ | 每个币种独立保证金 |
| **统一账户（推荐）** | 3 | ✅ | 跨币种保证金，资金利用率高 |
| 组合保证金 | 4 | ✅ | 专业交易者使用 |

**推荐使用统一账户模式（acctLv=3）**，这是OKX目前主推的模式，具有以下优势：
- ✅ 支持合约交易
- ✅ 多币种共享保证金
- ✅ 资金利用率更高
- ✅ 功能最全面

---

## 常见问题

### Q: 升级账户模式会影响现有资产吗？
A: 不会，升级只是切换交易模式，不会影响您的资产。

### Q: 升级后可以切换回简单模式吗？
A: 可以，但如果有未平仓的合约持仓，需要先平仓。

### Q: 升级需要额外验证吗？
A: 如果您的KYC已完成（当前是Lv2），通常可以直接升级。

---

## 已完成的修复

✅ 修复了日志缓冲问题（添加-u参数）
✅ 增强了交易执行的详细日志记录
✅ 诊断出51010错误的根本原因

现在只需要升级OKX账户模式，交易机器人就可以正常工作了！

