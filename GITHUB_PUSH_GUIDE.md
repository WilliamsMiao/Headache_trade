# GitHub 推送指南

## ✅ 项目已准备就绪！

所有文件已提交到本地Git仓库，现在需要推送到GitHub。

## 🔐 认证方式

你需要选择以下方式之一进行认证：

### 方式1：使用 Personal Access Token (推荐)

1. **创建Personal Access Token**
   - 访问：https://github.com/settings/tokens
   - 点击 "Generate new token" -> "Generate new token (classic)"
   - 勾选 `repo` 权限
   - 生成并复制token

2. **推送到GitHub**
   ```bash
   cd /root/crypto_deepseek
   git push -u origin main
   ```
   
3. **输入凭证**
   - Username: `WilliamsMiao`
   - Password: `粘贴你的Personal Access Token`

### 方式2：使用SSH密钥

1. **生成SSH密钥（如果还没有）**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   cat ~/.ssh/id_ed25519.pub
   ```

2. **添加SSH密钥到GitHub**
   - 访问：https://github.com/settings/keys
   - 点击 "New SSH key"
   - 粘贴公钥内容

3. **更改远程仓库URL为SSH**
   ```bash
   cd /root/crypto_deepseek
   git remote set-url origin git@github.com:WilliamsMiao/Headache_trade.git
   git push -u origin main
   ```

## 📋 快速推送命令

```bash
# 方式1：使用HTTPS + Token
cd /root/crypto_deepseek
git push -u origin main
# 然后输入你的用户名和Personal Access Token

# 方式2：使用SSH（需要先配置SSH密钥）
cd /root/crypto_deepseek
git remote set-url origin git@github.com:WilliamsMiao/Headache_trade.git
git push -u origin main
```

## 🔍 验证推送成功

推送成功后，访问你的仓库：
https://github.com/WilliamsMiao/Headache_trade

## ⚠️ 重要提醒

### 已保护的敏感信息：
- ✅ `.env` 文件（包含所有API密钥）已被 `.gitignore` 排除
- ✅ `myenv/` 和 `venv/` 虚拟环境已排除
- ✅ `data/` 运行时数据已排除
- ✅ 所有硬编码的API密钥已移至环境变量

### 已创建的文件：
- ✅ `.gitignore` - 保护敏感信息
- ✅ `.env.example` - 配置模板
- ✅ `start.sh` - 一键启动脚本

## 🚀 后续使用

其他人克隆你的项目后，需要：

1. **复制环境变量模板**
   ```bash
   cp .env.example .env
   ```

2. **填写自己的API密钥**
   ```bash
   nano .env
   ```

3. **安装依赖**
   ```bash
   python3 -m venv myenv
   source myenv/bin/activate
   pip install -r requirements.txt
   ```

4. **一键启动**
   ```bash
   ./start.sh
   ```

---

如有问题，请参考: https://docs.github.com/cn/authentication

